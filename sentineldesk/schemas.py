"""Data shapes shared by the agents, the orchestrator, and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from sentineldesk.config import LABEL_HEADS

# Escalation status badges shown in the console.
AUTO_DRAFT_READY = "AUTO_DRAFT_READY"
HUMAN_REVIEW = "HUMAN_REVIEW"
ESCALATE_IMMEDIATELY = "ESCALATE_IMMEDIATELY"


def clean_text(value: object) -> str:
    """Return stripped text, treating None, NaN, and pandas NA as empty."""
    if value is None:
        return ""
    if not isinstance(value, str) and pd.isna(value):
        return ""
    return str(value).strip()


def ticket_text(subject: object, body: object) -> str:
    """Join subject and body into one text. A missing subject is skipped."""
    return "\n".join(part for part in (clean_text(subject), clean_text(body)) if part)


@dataclass(frozen=True)
class Ticket:
    # Raw customer text is deliberately hidden from dataclass reprs so an
    # accidental ``logger.info(ticket)`` cannot become a PII leak.
    subject: str = field(repr=False)
    body: str = field(repr=False)

    @property
    def text(self) -> str:
        return ticket_text(self.subject, self.body)


@dataclass(frozen=True)
class LabelDistribution:
    """Probabilities over the labels of one head (type, queue, or priority)."""

    probabilities: dict[str, float]
    # Set when the adversarial reviewer overrides the most likely label.
    chosen_label: str | None = None

    @property
    def label(self) -> str:
        if self.chosen_label:
            return self.chosen_label
        if not self.probabilities:
            return ""
        return max(self.probabilities.items(), key=lambda item: item[1])[0]

    @property
    def confidence(self) -> float:
        return self.probabilities.get(self.label, 0.0)

    @property
    def margin(self) -> float:
        """Difference between the two most likely labels.

        Confidence and margin are kept separate because a calibrated top score
        can still be ambiguous when the runner-up is almost as likely.
        """
        ranked = sorted(self.probabilities.values(), reverse=True)
        if not ranked:
            return 0.0
        if len(ranked) == 1:
            return ranked[0]
        return ranked[0] - ranked[1]


@dataclass(frozen=True)
class TicketLabels:
    """One agent's prediction for all three heads."""

    source: str
    type: LabelDistribution
    queue: LabelDistribution
    priority: LabelDistribution

    def head(self, name: str) -> LabelDistribution:
        return getattr(self, name)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "label": self.head(name).label,
                "confidence": round(self.head(name).confidence, 3),
                "margin": round(self.head(name).margin, 3),
                "probabilities": {
                    label: round(probability, 3)
                    for label, probability in sorted(
                        self.head(name).probabilities.items()
                    )
                },
            }
            for name in LABEL_HEADS
        }


@dataclass(frozen=True)
class Precedent:
    """A historical ticket retrieved as evidence."""

    ticket_id: str
    similarity: float
    subject: str
    body: str
    answer: str
    type: str
    queue: str
    priority: str
    language: str

    def answer_snippet(self, max_characters: int = 280) -> str:
        if len(self.answer) <= max_characters:
            return self.answer
        return self.answer[:max_characters].rsplit(" ", 1)[0] + " …"


@dataclass(frozen=True)
class ScreeningResult:
    """What the input guardrails found before any model sees the ticket."""

    language: str
    language_supported: bool
    masked_subject: str
    masked_body: str
    pii_counts: dict[str, int]
    injection_signals: list[str]

    @property
    def masked_text(self) -> str:
        return ticket_text(self.masked_subject, self.masked_body)


@dataclass(frozen=True)
class Attachment:
    """An image or video attached to a ticket. Only the deep model tier sees it."""

    data: bytes
    mime_type: str


@dataclass(frozen=True)
class LLMCallRecord:
    """Usage of one LLM call, for latency and cost tracking."""

    task: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float


@dataclass
class TriageResult:
    """Everything the console needs to show for one ticket."""

    ticket: Ticket
    language: str
    classifier_labels: TicketLabels
    rag_labels: TicketLabels | None
    final_labels: TicketLabels
    disagreements: list[str]
    precedents: list[Precedent]
    pii_counts: dict[str, int]
    injection_signals: list[str]
    evidence_sufficient: bool = False
    top_similarity: float = 0.0
    security_events: list[str] = field(default_factory=list)
    route: str = "none"  # "fast", "deep", or "none" when stopped before routing
    route_reasons: list[str] = field(default_factory=list)
    status: str = HUMAN_REVIEW
    reasons: list[str] = field(default_factory=list)
    adversarial_findings: list[str] = field(default_factory=list)
    draft_reply: str | None = None
    removed_claims: list[str] = field(default_factory=list)
    verification_issues: list[str] = field(default_factory=list)
    grounding_review: dict[str, Any] | None = None
    draft_citations: list[str] = field(default_factory=list)
    runtime_backends: dict[str, str] = field(default_factory=dict)
    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    stage_latency_ms: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return sum(call.input_tokens + call.output_tokens for call in self.llm_calls)

    @property
    def estimated_cost_usd(self) -> float:
        return sum(call.estimated_cost_usd for call in self.llm_calls)

    def to_dict(self) -> dict[str, Any]:
        """Plain dictionary for the trusted UI.

        Use :func:`sentineldesk.audit.build_audit_event` for operational logs;
        this richer view intentionally includes draft and matched security text.
        """
        return {
            "status": self.status,
            "reasons": self.reasons,
            "route": self.route,
            "route_reasons": self.route_reasons,
            "language": self.language,
            "final_labels": self.final_labels.to_dict(),
            "classifier_labels": self.classifier_labels.to_dict(),
            "rag_labels": self.rag_labels.to_dict() if self.rag_labels else None,
            "disagreements": self.disagreements,
            "adversarial_findings": self.adversarial_findings,
            "precedents": [
                {
                    "ticket_id": precedent.ticket_id,
                    "similarity": round(precedent.similarity, 3),
                    "labels": {
                        "type": precedent.type,
                        "queue": precedent.queue,
                        "priority": precedent.priority,
                    },
                    "answer_snippet": precedent.answer_snippet(),
                }
                for precedent in self.precedents
            ],
            "draft_reply": self.draft_reply,
            "removed_claims": self.removed_claims,
            "verification_issues": self.verification_issues,
            "pii_counts": self.pii_counts,
            "injection_signals": self.injection_signals,
            "security_events": self.security_events,
            "evidence_sufficient": self.evidence_sufficient,
            "top_similarity": round(self.top_similarity, 3),
            "grounding_review": self.grounding_review,
            "draft_citations": self.draft_citations,
            "runtime_backends": self.runtime_backends,
            "latency_ms": round(self.latency_ms, 1),
            "stage_latency_ms": {
                stage: round(milliseconds, 1)
                for stage, milliseconds in self.stage_latency_ms.items()
            },
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "llm_calls": [asdict(call) for call in self.llm_calls],
        }
