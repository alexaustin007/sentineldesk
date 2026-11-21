"""Convert a TriageResult into the console's response contract.

The contract is contracts/triage_response.example.json, and the field mapping is
documented in docs/UI_WORKFLOW.md (section 3.2).
"""

from typing import Any
from uuid import uuid4

from sentineldesk.config import LABEL_HEADS, SUPPORTED_LANGUAGES, TriageConfig
from sentineldesk.schemas import (
    AUTO_DRAFT_READY,
    ESCALATE_IMMEDIATELY,
    HUMAN_REVIEW,
    LabelDistribution,
    Precedent,
    TriageResult,
)
from sentineldesk.verification import CITATION_PATTERN

STATUS_CODES = {
    AUTO_DRAFT_READY: "auto_draft",
    HUMAN_REVIEW: "human_review",
    ESCALATE_IMMEDIATELY: "escalate",
}

# Reason prefix -> code that picks the console's icon for that reason.
REASON_CODES: list[tuple[str, str]] = [
    ("High-priority Incident", "HIGH_PRIORITY_INCIDENT"),
    ("Reviewer rated it a high-priority Incident", "HIGH_PRIORITY_INCIDENT"),
    ("Possible prompt injection", "PROMPT_INJECTION"),
    ("Unsupported language", "UNSUPPORTED_LANGUAGE"),
    ("No close historical precedent", "LOW_SIMILARITY"),
    ("Asks for", "UNSUPPORTED_REQUEST"),
    ("Draft failed", "VERIFICATION_FAILED"),
]


def reason_code(message: str) -> str:
    return next(
        (code for prefix, code in REASON_CODES if message.startswith(prefix)), "OTHER"
    )


def label_prediction(distribution: LabelDistribution) -> dict[str, Any]:
    """Label, confidence, margin over the runner-up, and the next two labels."""
    ranked = sorted(
        distribution.probabilities.items(), key=lambda item: item[1], reverse=True
    )
    others = [(label, score) for label, score in ranked if label != distribution.label]
    runner_up = others[0][1] if others else 0.0
    return {
        "label": distribution.label,
        "confidence": round(distribution.confidence, 4),
        "margin": round(max(distribution.confidence - runner_up, 0.0), 4),
        "alternatives": [
            {"label": label, "confidence": round(score, 4)}
            for label, score in others[:2]
        ],
    }


def precedent_record(precedent: Precedent) -> dict[str, Any]:
    return {
        "ticket_id": precedent.ticket_id,
        "similarity": round(precedent.similarity, 4),
        "language": precedent.language,
        "subject": precedent.subject,
        "type": precedent.type,
        "queue": precedent.queue,
        "priority": precedent.priority,
        "answer_snippet": precedent.answer_snippet(),
        "body": precedent.body,
        "answer": precedent.answer,
    }


def to_contract(result: TriageResult, config: TriageConfig) -> dict[str, Any]:
    unsupported = [reason for reason in result.reasons if reason.startswith("Asks for")]
    signals = result.injection_signals
    draft = result.draft_reply
    return {
        "request_id": f"req_{uuid4().hex[:12]}",
        "input": {
            "subject": result.ticket.subject or None,
            "body": result.ticket.body,
            "language_detected": result.language,
            "language_supported": result.language in SUPPORTED_LANGUAGES,
            "pii_counts": {
                label.lower(): count for label, count in result.pii_counts.items()
            },
        },
        "classification": {
            **{
                head: label_prediction(result.final_labels.head(head))
                for head in LABEL_HEADS
            },
            "critical_incident_risk": round(result.incident_risk, 4),
            "disagreements": [
                head
                for head in LABEL_HEADS
                if any(text.startswith(f"{head}:") for text in result.disagreements)
            ],
        },
        "escalation": {
            "status": STATUS_CODES.get(result.status, "escalate"),
            "reasons": [
                {"code": reason_code(reason), "message": reason}
                for reason in result.reasons
            ],
            "thresholds": {
                "confidence": config.min_head_confidence,
                "similarity": config.min_top_similarity,
                "critical_incident_risk": min(
                    config.min_classifier_incident_score,
                    config.min_incident_precedent_share,
                ),
            },
        },
        "route": {"path": result.route, "reasons": result.route_reasons},
        "guardrails": {
            "prompt_injection": {
                "flagged": bool(signals),
                "evidence": signals[0] if signals else None,
            },
            "unsupported_request": {
                "flagged": bool(unsupported),
                "evidence": unsupported[0] if unsupported else None,
            },
            "injection_signals": signals,
            "removed_claims": result.removed_claims,
            "verification_issues": result.verification_issues,
            "citations_valid": not any(
                "cite" in issue for issue in result.verification_issues
            ),
        },
        "precedents": [precedent_record(precedent) for precedent in result.precedents],
        "draft": (
            {
                "language": result.language,
                "text": draft,
                "citations": list(dict.fromkeys(CITATION_PATTERN.findall(draft))),
            }
            if draft
            else None
        ),
        "latency_ms": {
            "total": round(result.latency_ms, 1),
            **{
                stage: round(milliseconds, 1)
                for stage, milliseconds in result.stage_latency_ms.items()
            },
        },
        "usage": {
            "total_tokens": result.total_tokens,
            "estimated_cost_usd": round(result.estimated_cost_usd, 6),
        },
    }
