import pytest

from sentineldesk.consensus import blend_predictions, find_disagreements
from sentineldesk.precedent_vote import vote_on_labels
from sentineldesk.schemas import LabelDistribution, Precedent, TicketLabels


def make_precedent(
    ticket_id: str, similarity: float, ticket_type: str = "Incident"
) -> Precedent:
    return Precedent(
        ticket_id=ticket_id,
        similarity=similarity,
        subject="",
        body="",
        answer="",
        type=ticket_type,
        queue="IT Support",
        priority="medium",
        language="en",
    )


def test_vote_is_weighted_by_similarity() -> None:
    labels = vote_on_labels(
        [
            make_precedent("A", 0.9),
            make_precedent("B", 0.8),
            make_precedent("C", 0.3, ticket_type="Request"),
        ]
    )

    assert labels is not None
    assert labels.type.label == "Incident"
    assert labels.type.confidence == pytest.approx(1.7 / 2.0)


def test_vote_without_usable_evidence_returns_none() -> None:
    assert vote_on_labels([]) is None
    assert vote_on_labels([make_precedent("A", -0.2)]) is None


def test_blend_and_disagreement() -> None:
    classifier = TicketLabels(
        source="classifier",
        type=LabelDistribution({"Incident": 0.8, "Request": 0.2}),
        queue=LabelDistribution({"IT Support": 1.0}),
        priority=LabelDistribution({"low": 1.0}),
    )
    precedents = TicketLabels(
        source="rag_vote",
        type=LabelDistribution({"Request": 1.0}),
        queue=LabelDistribution({"IT Support": 1.0}),
        priority=LabelDistribution({"low": 1.0}),
    )

    combined = blend_predictions(classifier, precedents, classifier_weight=0.6)
    disagreements = find_disagreements(
        classifier, precedents, heads=("type", "queue", "priority")
    )

    # Request: 0.6 * 0.2 + 0.4 * 1.0 = 0.52 beats Incident: 0.6 * 0.8 = 0.48.
    assert combined.type.label == "Request"
    assert combined.type.confidence == pytest.approx(0.52)
    assert len(disagreements) == 1
    assert disagreements[0].startswith("type:")


def test_reviewer_choice_overrides_label_but_keeps_probabilities() -> None:
    distribution = LabelDistribution({"low": 0.7, "high": 0.3}, chosen_label="high")

    assert distribution.label == "high"
    assert distribution.confidence == pytest.approx(0.3)
