"""Five-stage workflow: guardrails, parallel evidence, policy, draft, verification.

For each ticket:
1. Guardrails screen the input (language, prompt injection, PII masking).
2. Agent 1, the external classifier, predicts type, queue, and priority.
3. Agent 2, the RAG engine, independently retrieves and votes on precedents.
4. Deterministic policy gates stop uncertain, unsupported, unsafe, or critical work.
5. Every generated draft passes Python checks and an independent grounding review.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock

from sentineldesk.adversarial_review import apply_review, run_adversarial_review
from sentineldesk.audit import emit_audit_event
from sentineldesk.classifier_interface import TicketClassifier
from sentineldesk.config import TriageConfig
from sentineldesk.consensus import find_disagreements
from sentineldesk.escalation import (
    choose_route,
    decide_status,
    find_mandatory_escalation,
    find_missing_detail,
    find_model_uncertainty,
    find_risk_signals,
    find_screening_issues,
    find_unsupported_requests,
    is_high_priority_incident,
)
from sentineldesk.grounding_review import run_grounding_review
from sentineldesk.guardrails import (
    normalize_untrusted_text,
    screen_ticket,
    validate_attachments,
    validate_ticket_input,
)
from sentineldesk.llm import LLMProvider, LLMUnavailableError
from sentineldesk.precedent_vote import (
    credible_precedents,
    strongest_similarity,
    vote_on_labels,
)
from sentineldesk.reply_generation import draft_reply
from sentineldesk.retrieval import PrecedentIndex
from sentineldesk.schemas import (
    Attachment,
    LabelDistribution,
    ScreeningResult,
    Ticket,
    TicketLabels,
    TriageResult,
    clean_text,
)
from sentineldesk.verification import verify_reply


class StageTimer:
    """Measures each stage of the workflow and the total time."""

    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.durations_ms: dict[str, float] = {}
        self._lock = Lock()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        stage_started = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - stage_started) * 1000
            with self._lock:
                self.durations_ms[name] = duration_ms

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
        raw_ticket = Ticket(subject=clean_text(subject), body=clean_text(body))

        # Reject malformed or excessive input before classifier, retrieval, or LLM
        # work. Stable event codes can be logged without copying attacker text.
        with timer.stage("input_validation"):
            input_issues = [
                *validate_ticket_input(raw_ticket),
                *validate_attachments(attachments),
            ]
        if input_issues:
            result = self._stopped_result(
                raw_ticket,
                security_events=[issue.code for issue in input_issues],
            )
            return self._finish(
                result, timer, [], [issue.message for issue in input_issues]
            )

        ticket = Ticket(
            subject=normalize_untrusted_text(raw_ticket.subject),
            body=normalize_untrusted_text(raw_ticket.body),
        )

        with timer.stage("guardrails"):
            screening = screen_ticket(ticket)
        security_events = []
        if screening.pii_counts:
            security_events.append("PII_REDACTED")
        if screening.injection_signals:
            security_events.append("PROMPT_INJECTION_DETECTED")

        # Near-empty or unsafe input does not reach either model branch.
        review_reasons = [
            *find_missing_detail(screening, self.config),
            *find_screening_issues(screening),
        ]
        if review_reasons:
            result = self._stopped_result(
                ticket,
                screening=screening,
                security_events=security_events,
            )
            return self._finish(result, timer, [], review_reasons)

        # Classification and retrieval are independent and run in parallel.
        try:
            with ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="sentineldesk"
            ) as pool:
                classifier_future = pool.submit(self._classify, timer, ticket)
                retrieval_future = pool.submit(self._retrieve, timer, ticket)
                classifier_labels = classifier_future.result()
                retrieved = retrieval_future.result()
        except ValueError:
            result = self._stopped_result(
                ticket,
                screening=screening,
                security_events=[*security_events, "MODEL_OUTPUT_INVALID"],
            )
            return self._finish(
                result,
                timer,
                [],
                ["A model returned invalid output; human review is required"],
            )
        except RuntimeError:
            result = self._stopped_result(
                ticket,
                screening=screening,
                security_events=[*security_events, "INFERENCE_UNAVAILABLE"],
            )
            return self._finish(
                result,
                timer,
                [],
                [
                    "Classifier or retrieval inference is unavailable; human review is required"
                ],
            )

        top_similarity = strongest_similarity(retrieved)
        # Only genuinely similar tickets may vote, justify a commitment, enter a
        # prompt, or be cited. A single good hit must not drag weak neighbors in.
        voting_precedents = credible_precedents(
            retrieved, self.config.min_top_similarity
        )
        has_evidence = bool(voting_precedents)
        rag_labels = vote_on_labels(voting_precedents)
        result = TriageResult(
            ticket=ticket,
            language=screening.language,
            classifier_labels=classifier_labels,
            rag_labels=rag_labels,
            # RAG is independent evidence; it never changes calibrated confidence.
            final_labels=classifier_labels,
            disagreements=find_disagreements(
                classifier_labels, rag_labels, self.config.heads_that_must_agree
            ),
            precedents=voting_precedents[: self.config.precedents_shown],
            pii_counts=screening.pii_counts,
            injection_signals=screening.injection_signals,
            evidence_sufficient=has_evidence,
            top_similarity=top_similarity,
            security_events=security_events,
            runtime_backends=self._runtime_backends(),
        )

        # Mandatory escalation: page the on-call engineer without any LLM call.
        escalation_reasons = find_mandatory_escalation(
            classifier_labels, voting_precedents, self.config
        )
        if escalation_reasons:
            return self._finish(result, timer, escalation_reasons, [])

        # Uncertainty is a deterministic human-review gate, not an invitation for
        # an LLM to manufacture confidence.
        uncertainty_reasons = find_model_uncertainty(classifier_labels, self.config)
        if uncertainty_reasons:
            return self._finish(result, timer, [], uncertainty_reasons)

        # Collect every deterministic evidence failure so the dashboard explains
        # the full decision, then stop before spending tokens.
        risk_signals = find_risk_signals(screening.masked_text)
        unsupported_requests = find_unsupported_requests(
            screening.masked_text, result.precedents
        )
        evidence_review_reasons = list(unsupported_requests)
        if not has_evidence:
            evidence_review_reasons.insert(
                0,
                "No close historical precedent, so no grounded reply can be drafted",
            )
        if evidence_review_reasons:
            return self._finish(result, timer, [], evidence_review_reasons)

        # Decide how much compute this ticket deserves.

        route = choose_route(
            classifier_labels=classifier_labels,
            disagreements=result.disagreements,
            top_similarity=top_similarity,
            risk_signals=risk_signals,
            unsupported_requests=unsupported_requests,
            has_attachments=bool(attachments),
            config=self.config,
        )
        result.route, result.route_reasons = route.route, route.reasons
        review_reasons = []

        # Deep path: the adversarial agent challenges the triage before drafting.
        if route.route == "deep":
            with timer.stage("adversarial_review"):
                escalation_reasons, unresolved = self._review(
                    result, screening, risk_signals, attachments
                )
            review_reasons.extend(unresolved)
            if escalation_reasons:
                return self._finish(result, timer, escalation_reasons, review_reasons)
            if unresolved:
                return self._finish(result, timer, [], review_reasons)

        review_reasons.extend(self._draft_and_verify(result, timer, screening))
        return self._finish(result, timer, [], review_reasons)

    def _classify(self, timer: StageTimer, ticket: Ticket) -> TicketLabels:
        with timer.stage("classifier"):
            return self.classifier.predict(ticket.subject, ticket.body)

    def _retrieve(self, timer: StageTimer, ticket: Ticket):
        with timer.stage("retrieval"):
            return self.precedent_index.search(
                ticket.text, top_k=self.config.retrieval_top_k
            )

    def _stopped_result(
        self,
        ticket: Ticket,
        screening: ScreeningResult | None = None,
        security_events: Sequence[str] = (),
    ) -> TriageResult:
        """Build a transparent result when policy stops before model inference."""
        labels = _not_run_labels()
        return TriageResult(
            ticket=ticket,
            language=screening.language if screening else "unknown",
            classifier_labels=labels,
            rag_labels=None,
            final_labels=labels,
            disagreements=[],
            precedents=[],
            pii_counts=screening.pii_counts if screening else {},
            injection_signals=screening.injection_signals if screening else [],
            security_events=list(security_events),
            runtime_backends=self._runtime_backends(),
        )

    def _runtime_backends(self) -> dict[str, str]:
        return {
            "classifier": type(self.classifier).__name__,
            "retrieval": f"FAISS/{self.precedent_index.embedder.name}",
            "llm": self.llm_provider.name,
        }

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
        except LLMUnavailableError:
            # Provider diagnostics may contain request details; keep the public
            # result stable and send protected diagnostics to internal telemetry.
            return [], ["Adversarial safety review unavailable"]
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
        except LLMUnavailableError:
            return ["Reply drafting failed safely; human review is required"]
        result.llm_calls.append(draft.record)
        result.draft_citations = list(draft.cited_ticket_ids)

        with timer.stage("verification"):
            verification = verify_reply(
                draft.text, result.precedents, screening.language
            )
        result.draft_reply = verification.cleaned_reply
        result.removed_claims = verification.removed_claims
        result.verification_issues = verification.issues
        if not verification.passed:
            return ["Draft failed deterministic grounding or security verification"]

        try:
            with timer.stage("grounding_review"):
                verdict, record = run_grounding_review(
                    self.llm_provider,
                    screening,
                    verification.cleaned_reply,
                    result.precedents,
                )
        except LLMUnavailableError:
            return ["Independent grounding review unavailable"]
        result.llm_calls.append(record)
        if verdict is None:
            return ["Independent grounding reviewer returned an invalid verdict"]

        result.grounding_review = verdict.model_dump()
        if (
            not verdict.grounded
            or not verdict.valid_citations
            or verdict.unsupported_claims
            or verdict.recommend_escalation
        ):
            return ["Independent grounding review rejected the draft"]
        return []

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
        emit_audit_event(result)
        return result


def _not_run_labels() -> TicketLabels:
    """Empty distributions make a pre-model stop explicit in the result schema."""
    return TicketLabels(
        source="not_run",
        type=LabelDistribution({}),
        queue=LabelDistribution({}),
        priority=LabelDistribution({}),
    )
