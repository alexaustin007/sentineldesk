"""Escalation and routing rules: when to page a human, and how much compute to spend."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sentineldesk.config import LABEL_HEADS, TriageConfig, priority_severity
from sentineldesk.policy_patterns import COMMITMENT_TOPICS, RISK_SIGNALS
from sentineldesk.precedent_vote import similarity_weights
from sentineldesk.schemas import (
    AUTO_DRAFT_READY,
    ESCALATE_IMMEDIATELY,
    HUMAN_REVIEW,
    Precedent,
    ScreeningResult,
    TicketLabels,
)


def is_high_priority_incident(labels: TicketLabels, config: TriageConfig) -> bool:
    return (
        labels.priority.label.lower() in config.high_priority_labels
        and labels.type.label == config.incident_type_label
    )


def high_priority_incident_share(
    precedents: Sequence[Precedent], config: TriageConfig
) -> float:
    """Share of the similarity-weighted vote cast by high-priority Incident precedents.

    Each precedent must be both high priority and an Incident. Voting on the two
    labels separately could add "high" from some neighbors to "Incident" from
    others and raise a false alarm.
    """
    weights = similarity_weights(precedents)
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    incident_weight = sum(
        weight
        for precedent, weight in zip(precedents, weights)
        if precedent.priority.lower() in config.high_priority_labels
        and precedent.type == config.incident_type_label
    )
    return incident_weight / total_weight


def find_mandatory_escalation(
    classifier_labels: TicketLabels,
    precedents: Sequence[Precedent],
    config: TriageConfig,
) -> list[str]:
    """High-priority incidents always go to the on-call engineer.

    Either agent is enough. This favors recall on purpose: a missed outage costs
    far more than an extra page.
    """
    sources = []
    if is_high_priority_incident(classifier_labels, config):
        sources.append("the classifier")
    incident_share = high_priority_incident_share(precedents, config)
    if incident_share >= config.min_incident_precedent_share:
        sources.append(f"{incident_share:.0%} of the precedent vote")
    if not sources:
        return []
    return [f"High-priority Incident flagged by {' and '.join(sources)}"]


def find_missing_detail(screening: ScreeningResult, config: TriageConfig) -> list[str]:
    """A near-empty ticket gives neither agent anything to judge."""
    word_count = len(re.findall(r"\w+", screening.masked_text))
    if word_count < config.min_ticket_words:
        return [f"Too little detail to triage automatically ({word_count} words)"]
    return []


def find_screening_issues(screening: ScreeningResult) -> list[str]:
    """Input problems that rule out sending the ticket to a model."""
    issues = []
    if not screening.language_supported:
        issues.append(
            f"Unsupported language '{screening.language}': only English and German "
            "are answered automatically"
        )
    if screening.injection_signals:
        issues.append(
            "Possible prompt injection: " + "; ".join(screening.injection_signals)
        )
    return issues


def find_risk_signals(text: str) -> list[str]:
    """Names of the risk cues found in the ticket text."""
    return [name for name, pattern in RISK_SIGNALS if pattern.search(text)]


def find_unsupported_requests(text: str, precedents: Sequence[Precedent]) -> list[str]:
    """Commitments the customer asks for that no retrieved resolution covers."""
    evidence = "\n".join(precedent.answer for precedent in precedents)
    return [
        f"Asks for {topic}, but no retrieved resolution covers it"
        for topic, pattern in COMMITMENT_TOPICS
        if pattern.search(text) and not pattern.search(evidence)
    ]


@dataclass(frozen=True)
class RouteDecision:
    route: str  # "fast" (Flash-Lite draft) or "deep" (Flash adversarial review first)
    reasons: list[str]  # why the deep path was needed; empty on the fast path


def choose_route(
    combined_labels: TicketLabels,
    disagreements: Sequence[str],
    top_similarity: float,
    risk_signals: Sequence[str],
    unsupported_requests: Sequence[str],
    has_attachments: bool,
    config: TriageConfig,
) -> RouteDecision:
    """Fast path only when the agents agree, are confident, have evidence, and see no risk."""
    reasons = [f"Agents disagree on {disagreement}" for disagreement in disagreements]
    low_confidence_heads = [
        head
        for head in LABEL_HEADS
        if combined_labels.head(head).confidence < config.min_head_confidence
    ]
    if low_confidence_heads:
        reasons.append("Low blended confidence on " + ", ".join(low_confidence_heads))
    if top_similarity < config.min_top_similarity:
        reasons.append(
            f"Weak evidence: best precedent similarity {top_similarity:.2f} "
            f"is below {config.min_top_similarity:.2f}"
        )
    if priority_severity(combined_labels.priority.label) >= priority_severity("high"):
        reasons.append("High predicted priority")
    reasons.extend(f"Risk signal: {signal}" for signal in risk_signals)
    reasons.extend(unsupported_requests)
    if has_attachments:
        reasons.append("Attachments need multimodal analysis")
    return RouteDecision(route="deep" if reasons else "fast", reasons=reasons)


def decide_status(
    escalation_reasons: Sequence[str], review_reasons: Sequence[str]
) -> str:
    """Escalation beats human review, and human review beats auto-approval."""
    if escalation_reasons:
        return ESCALATE_IMMEDIATELY
    if review_reasons:
        return HUMAN_REVIEW
    return AUTO_DRAFT_READY
