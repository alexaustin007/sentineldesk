"""Label names, thresholds, and routing settings for the triage workflow.

Every threshold is a starting point. Tune them on a validation slice taken from the
historical split, never on the holdout.
"""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Written by scripts/prepare_data.py (the official 80/20 split).
PREPARED_DATA_DIR = PROJECT_ROOT / "data" / "prepared"
# Written by `python -m sentineldesk.build_index`, loaded by the console.
INDEX_DIR = PROJECT_ROOT / "artifacts" / "precedent_index"

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
    # Escalate when high-priority Incident precedents cast at least this share of
    # the similarity-weighted vote. On a 500-ticket historical validation slice,
    # 0.4 caught 65% of high-priority incidents at 57% precision (0.3: 78% / 49%,
    # 0.5: 44% / 77%). The classifier can escalate on its own as well.
    min_incident_precedent_share: float = 0.4

    # Tickets shorter than this go to a human instead of an automated reply.
    min_ticket_words: int = 2

    # Retrieval: how many precedents vote, and how many are shown and cited.
    retrieval_top_k: int = 10
    precedents_shown: int = 5

    # The classifier probabilities and historical vote shares are deliberately
    # kept separate. A RAG vote share is useful evidence, but it is not a
    # calibrated model probability and must not be averaged into one.
    heads_that_must_agree: tuple[str, ...] = LABEL_HEADS

    # Classifier uncertainty gates. These apply to the raw calibrated classifier
    # distributions before RAG evidence or an LLM can influence the decision.
    # Tune both values on validation data and record the chosen operating point.
    min_classifier_confidence: float = 0.55
    min_classifier_margin: float = 0.10
    # Below this best-match similarity there is no grounded answer. With the
    # multilingual index, 95% of historical validation tickets score above 0.77,
    # short realistic tickets 0.63 to 0.85, and off-topic text 0.22 to 0.32.
    min_top_similarity: float = 0.5

    @property
    def min_head_confidence(self) -> float:
        """Compatibility alias for callers migrating to the explicit name."""
        return self.min_classifier_confidence
