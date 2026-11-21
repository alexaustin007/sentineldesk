from collections.abc import Iterable, Mapping

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

from sentineldesk.classifier_interface import SklearnClassifierAdapter

TRAINING_TICKETS = [
    {"subject": "VPN down", "body": "Nobody can connect to the VPN."},
    {"subject": "VPN outage", "body": "The VPN gateway is down for everyone."},
    {"subject": "Invoice", "body": "We were charged twice for the invoice."},
    {"subject": "Billing", "body": "Please correct the invoice amount."},
]
TRAINING_LABELS = {
    "type": ["Incident", "Incident", "Problem", "Problem"],
    "queue": [
        "IT Support",
        "IT Support",
        "Billing and Payments",
        "Billing and Payments",
    ],
    "priority": ["high", "high", "medium", "medium"],
}


def records_to_text(tickets: Iterable[Mapping[str, str]]) -> list[str]:
    """Same input format as the team's make_ticket_features() pipeline."""
    return [f"{ticket['subject']}\n{ticket['body']}" for ticket in tickets]


def test_adapter_sends_ticket_records_to_the_pipeline() -> None:
    models = {
        head: make_pipeline(
            FunctionTransformer(records_to_text),
            TfidfVectorizer(),
            LogisticRegression(),
        ).fit(TRAINING_TICKETS, labels)
        for head, labels in TRAINING_LABELS.items()
    }

    labels = SklearnClassifierAdapter(models).predict(
        "VPN not working", "The VPN is down again."
    )

    assert labels.source == "classifier"
    assert labels.type.label == "Incident"
    assert labels.queue.label == "IT Support"
    assert sum(labels.priority.probabilities.values()) == pytest.approx(1.0)


class InvalidProbabilityModel:
    classes_ = ("a", "b")

    def predict_proba(self, _inputs: object) -> list[list[float]]:
        return [[0.8, 0.8]]


def test_adapter_rejects_non_normalized_probabilities() -> None:
    models = {head: InvalidProbabilityModel() for head in TRAINING_LABELS}

    with pytest.raises(ValueError, match="probabilities sum"):
        SklearnClassifierAdapter(models).predict("subject", "body")
