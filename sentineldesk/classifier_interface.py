"""Integration interface for the external ticket classifier.

Teammates train the classifier. This module only defines the contract the workflow
expects, an adapter for scikit-learn style models, and a keyword mock for
development. It does not train anything.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from sentineldesk.config import DEFAULT_LABEL_OPTIONS, LABEL_HEADS
from sentineldesk.schemas import LabelDistribution, TicketLabels, ticket_text


class TicketClassifier(Protocol):
    """Anything that can label a ticket. The orchestrator depends only on this."""

    def predict(self, subject: str, body: str) -> TicketLabels:
        """Return label probabilities for type, queue, and priority."""
        ...


class ProbabilisticModel(Protocol):
    """A fitted scikit-learn style model, such as a TF-IDF + logistic regression pipeline."""

    classes_: Sequence[Any]

    def predict_proba(self, texts: Sequence[str]) -> Any: ...


class SklearnClassifierAdapter:
    """Wrap one fitted model per head so it satisfies `TicketClassifier`.

    `build_text` must match how the models were trained. The default joins the
    subject and body with a newline and skips a missing subject.
    """

    def __init__(
        self,
        models_by_head: Mapping[str, ProbabilisticModel],
        build_text: Callable[[str, str], str] = ticket_text,
    ) -> None:
        missing_heads = [head for head in LABEL_HEADS if head not in models_by_head]
        if missing_heads:
            raise ValueError(f"Missing models for heads: {missing_heads}")
        self._models_by_head = dict(models_by_head)
        self._build_text = build_text

    def predict(self, subject: str, body: str) -> TicketLabels:
        text = self._build_text(subject, body)
        distributions = {}
        for head in LABEL_HEADS:
            model = self._models_by_head[head]
            probabilities = model.predict_proba([text])[0]
            distributions[head] = LabelDistribution(
                {
                    str(label): float(probability)
                    for label, probability in zip(model.classes_, probabilities)
                }
            )
        return TicketLabels(source="classifier", **distributions)


# (keywords, type, queue, priority), checked in order. The first match wins.
_MOCK_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    (
        ("outage", "is down", "ausgefallen", "ausfall", "breach", "nicht erreichbar"),
        "Incident",
        "Technical Support",
        "high",
    ),
    (("vpn",), "Incident", "IT Support", "medium"),
    (("password", "passwort"), "Request", "Customer Service", "low"),
    (
        ("invoice", "charged", "refund", "rechnung", "abbuchung"),
        "Problem",
        "Billing and Payments",
        "medium",
    ),
    (("integration", "pricing", "demo"), "Request", "Sales and Pre-Sales", "low"),
]


class MockClassifier:
    """Keyword stand-in so the workflow runs before the real classifier is ready."""

    def __init__(
        self, match_confidence: float = 0.75, default_confidence: float = 0.4
    ) -> None:
        self.match_confidence = match_confidence
        self.default_confidence = default_confidence

    def predict(self, subject: str, body: str) -> TicketLabels:
        text = ticket_text(subject, body).lower()
        for keywords, ticket_type, queue, priority in _MOCK_RULES:
            if any(keyword in text for keyword in keywords):
                return labels_from_choices(
                    ticket_type, queue, priority, self.match_confidence
                )
        return labels_from_choices(
            "Request", "General Inquiry", "low", self.default_confidence
        )


def labels_from_choices(
    ticket_type: str,
    queue: str,
    priority: str,
    confidence: float,
    source: str = "classifier",
) -> TicketLabels:
    """Build labels that put `confidence` on each chosen label."""
    chosen = {"type": ticket_type, "queue": queue, "priority": priority}
    return TicketLabels(
        source=source,
        **{
            head: peaked_distribution(
                DEFAULT_LABEL_OPTIONS[head], chosen[head], confidence
            )
            for head in LABEL_HEADS
        },
    )


def peaked_distribution(
    options: Sequence[str], chosen: str, confidence: float
) -> LabelDistribution:
    """Put `confidence` on the chosen label and spread the rest evenly."""
    others = [label for label in options if label != chosen]
    remainder = (1.0 - confidence) / len(others) if others else 0.0
    return LabelDistribution({chosen: confidence, **dict.fromkeys(others, remainder)})
