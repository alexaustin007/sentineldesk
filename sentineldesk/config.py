"""Label names, thresholds, and routing settings for the triage workflow.

Every threshold is a starting point. Tune them on a validation slice taken from the
historical split, never on the holdout.
"""

from dataclasses import dataclass

LABEL_HEADS: tuple[str, ...] = ("type", "queue", "priority")

SUPPORTED_LANGUAGES: dict[str, str] = {"en": "English", "de": "German"}

# Higher means more urgent. Unknown priority labels count as medium.
PRIORITY_SEVERITY: dict[str, int] = {
    "very_low": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Label sets for the mock classifier until the real classifier is wired in.
DEFAULT_LABEL_OPTIONS: dict[str, tuple[str, ...]] = {
    "type": ("Incident", "Request", "Problem", "Change"),
    "queue": (
        "Technical Support",
        "Product Support",
        "Customer Service",
        "IT Support",
        "Billing and Payments",
        "Returns and Exchanges",
        "Sales and Pre-Sales",
        "Human Resources",
        "Service Outages and Maintenance",
        "General Inquiry",
    ),
    "priority": ("low", "medium", "high"),
}


def priority_severity(label: str) -> int:
    """Return how urgent a priority label is (higher is more urgent)."""
    return PRIORITY_SEVERITY.get(label.strip().lower(), PRIORITY_SEVERITY["medium"])


@dataclass(frozen=True)
class TriageConfig:
    """Routing thresholds for one orchestrator instance."""

    # Lowercase priority labels that trigger mandatory escalation. The dataset card
    # says "Critical" while the brief says "high", so both are accepted.
    high_priority_labels: tuple[str, ...] = ("high", "critical")
    incident_type_label: str = "Incident"

    # Retrieval: how many precedents vote, and how many are shown and cited.
    retrieval_top_k: int = 10
    precedents_shown: int = 5

    # Consensus: weight of the external classifier when blended with the RAG vote.
    classifier_weight: float = 0.6
    heads_that_must_agree: tuple[str, ...] = LABEL_HEADS

    # Fast-path requirements.
    min_head_confidence: float = 0.55
    min_top_similarity: float = 0.45
