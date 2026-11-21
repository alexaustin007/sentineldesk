"""Agentic workflow: two triage agents, risk-based routing, and verified replies.

For each ticket:
1. Guardrails screen the input (language, prompt injection, PII masking).
2. Agent 1, the external classifier, predicts type, queue, and priority.
3. Agent 2, the RAG engine, retrieves precedents and, when they are genuinely
   similar, votes on the same labels.
4. A near-empty ticket goes to a human. A high-priority Incident from either agent
   escalates immediately.
5. Agreement, confidence, evidence, and low risk lead to the fast path (a Flash-Lite
   draft). Anything else takes the deep path (Flash adversarial review, then a
   Flash draft).
6. Every draft is verified for grounding and security before it can be approved.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from sentineldesk.adversarial_review import apply_review, run_adversarial_review
from sentineldesk.classifier_interface import TicketClassifier
from sentineldesk.config import TriageConfig
from sentineldesk.consensus import blend_predictions, find_disagreements
from sentineldesk.escalation import (
    choose_route,
    decide_status,
    find_mandatory_escalation,
    find_missing_detail,
    find_risk_signals,
    find_screening_issues,
    find_unsupported_requests,
    is_high_priority_incident,
)
from sentineldesk.guardrails import screen_ticket
from sentineldesk.llm import LLMProvider, LLMUnavailableError
from sentineldesk.precedent_vote import strongest_similarity, vote_on_labels
from sentineldesk.reply_generation import draft_reply
from sentineldesk.retrieval import PrecedentIndex
from sentineldesk.schemas import (
    Attachment,
    ScreeningResult,
    Ticket,
    TriageResult,
    clean_text,
)
from sentineldesk.verification import verify_reply


class StageTimer:
    """Measures each stage of the workflow and the total time."""

    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.durations_ms: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        stage_started = time.perf_counter()
        try:
            yield
        finally:
            self.durations_ms[name] = (time.perf_counter() - stage_started) * 1000

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000


@dataclass
class TriageOrchestrator:
    classifier: TicketClassifier
    precedent_index: PrecedentIndex
    llm_provider: LLMProvider
    config: TriageConfig = field(default_factory=TriageConfig)
    _label_options: dict[str, list[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._label_options = self.precedent_index.label_options()

    def triage(
        self,
        subject: str | None,
        body: str,
        attachments: Sequence[Attachment] = (),
    ) -> TriageResult:
        """Run the full workflow for one ticket. Only subject and body are needed."""
        timer = StageTimer()
        ticket = Ticket(subject=clean_text(subject), body=clean_text(body))

        with timer.stage("guardrails"):
            screening = screen_ticket(ticket)
        with timer.stage("classifier"):
            classifier_labels = self.classifier.predict(ticket.subject, ticket.body)
        with timer.stage("retrieval"):
            retrieved = self.precedent_index.search(
                ticket.text, top_k=self.config.retrieval_top_k
            )
        top_similarity = strongest_similarity(retrieved)
        has_evidence = top_similarity >= self.config.min_top_similarity
        # The precedent agent votes only when it found genuinely similar tickets;
        # otherwise its neighbors are unrelated and their labels are noise.
        voting_precedents = retrieved if has_evidence else []
        rag_labels = vote_on_labels(voting_precedents)
        combined_labels = blend_predictions(
            classifier_labels, rag_labels, self.config.classifier_weight
        )
        result = TriageResult(
            ticket=ticket,
            language=screening.language,
            classifier_labels=classifier_labels,
            rag_labels=rag_labels,
            final_labels=combined_labels,
            disagreements=find_disagreements(
                classifier_labels, rag_labels, self.config.heads_that_must_agree
            ),
            precedents=retrieved[: self.config.precedents_shown],
            pii_counts=screening.pii_counts,
            injection_signals=screening.injection_signals,
        )

        # A near-empty ticket gives neither agent anything to judge.
        missing_detail = find_missing_detail(screening, self.config)
        if missing_detail:
            return self._finish(result, timer, [], missing_detail)

        # Mandatory escalation: page the on-call engineer without any LLM call.
        escalation_reasons = find_mandatory_escalation(
            classifier_labels, voting_precedents, self.config
        )
        if escalation_reasons:
            return self._finish(result, timer, escalation_reasons, [])

        # Inputs that must not reach a model at all.
        review_reasons = find_screening_issues(screening)
        if review_reasons:
            return self._finish(result, timer, [], review_reasons)

        # Decide how much compute this ticket deserves.
        risk_signals = find_risk_signals(screening.masked_text)
        unsupported_requests = find_unsupported_requests(
            screening.masked_text, result.precedents
        )
        route = choose_route(
            combined_labels=combined_labels,
            disagreements=result.disagreements,
            top_similarity=top_similarity,
            risk_signals=risk_signals,
            unsupported_requests=unsupported_requests,
            has_attachments=bool(attachments),
            config=self.config,
        )
        result.route, result.route_reasons = route.route, route.reasons
        review_reasons.extend(unsupported_requests)
        if not has_evidence:
            review_reasons.append(
                "No close historical precedent, so no grounded reply can be drafted"
            )

        # Deep path: the adversarial agent challenges the triage before drafting.
        if route.route == "deep":
            with timer.stage("adversarial_review"):
                escalation_reasons, unresolved = self._review(
                    result, screening, risk_signals, attachments
                )
            review_reasons.extend(unresolved)
            if escalation_reasons:
                return self._finish(result, timer, escalation_reasons, review_reasons)

        if has_evidence:
            review_reasons.extend(self._draft_and_verify(result, timer, screening))
        return self._finish(result, timer, [], review_reasons)

    def _review(
        self,
        result: TriageResult,
        screening: ScreeningResult,
        risk_signals: Sequence[str],
        attachments: Sequence[Attachment],
    ) -> tuple[list[str], list[str]]:
        """Run the adversarial agent. Returns (escalation reasons, review reasons)."""
        try:
            review, record = run_adversarial_review(
                provider=self.llm_provider,
                screening=screening,
                classifier_labels=result.classifier_labels,
                rag_labels=result.rag_labels,
                combined_labels=result.final_labels,
                precedents=result.precedents,
                route_reasons=result.route_reasons,
                risk_signals=risk_signals,
                label_options=self._label_options,
                attachments=attachments,
            )
        except LLMUnavailableError as error:
            return [], [f"Adversarial safety review unavailable ({error})"]
        result.llm_calls.append(record)
        if review is None:
            return [], ["Adversarial reviewer returned an unusable answer"]

        result.final_labels, notes = apply_review(
            result.final_labels, review, self._label_options
        )
        result.adversarial_findings = [*review.findings, *notes]
        escalation_reasons = []
        if review.escalate:
            escalation_reasons.append(
                f"Adversarial reviewer escalated: {review.rationale}"
            )
        if is_high_priority_incident(result.final_labels, self.config):
            escalation_reasons.append("Reviewed labels are a high-priority Incident")
        return escalation_reasons, []

    def _draft_and_verify(
        self, result: TriageResult, timer: StageTimer, screening: ScreeningResult
    ) -> list[str]:
        """Draft a grounded reply and verify it. Returns review reasons, if any."""
        tier = "fast" if result.route == "fast" else "deep"
        try:
            with timer.stage("draft_reply"):
                draft = draft_reply(
                    self.llm_provider,
                    tier,
                    screening,
                    result.final_labels,
                    result.precedents,
                )
        except LLMUnavailableError as error:
            return [f"Reply drafting failed ({error})"]
        result.llm_calls.append(draft.record)

        with timer.stage("verification"):
            verification = verify_reply(
                draft.text, result.precedents, screening.language
            )
        result.draft_reply = verification.cleaned_reply
        result.removed_claims = verification.removed_claims
        result.verification_issues = verification.issues
        if verification.passed:
            return []
        return ["Draft failed grounding or security verification"]

    def _finish(
        self,
        result: TriageResult,
        timer: StageTimer,
        escalation_reasons: Sequence[str],
        review_reasons: Sequence[str],
    ) -> TriageResult:
        result.status = decide_status(escalation_reasons, review_reasons)
        result.reasons = [*escalation_reasons, *review_reasons]
        result.stage_latency_ms = timer.durations_ms
        result.latency_ms = timer.elapsed_ms()
        return result
