from sentineldesk.classifier_interface import labels_from_choices
from sentineldesk.config import TriageConfig
from sentineldesk.escalation import (
    choose_route,
    find_mandatory_escalation,
    find_model_uncertainty,
    probability_margin,
)
from sentineldesk.schemas import LabelDistribution, Precedent, TicketLabels

ROUTINE_CLASSIFIER = labels_from_choices("Request", "IT Support", "medium", 0.9)


def make_precedent(ticket_type: str, priority: str, similarity: float) -> Precedent:
    return Precedent(
        ticket_id=f"MOCK-{ticket_type}-{priority}",
        similarity=similarity,
        subject="",
        body="",
        answer="",
        type=ticket_type,
        queue="Technical Support",
        priority=priority,
        language="en",
    )


def test_mixed_precedents_do_not_raise_a_false_alarm() -> None:
    # Separate votes would read "high" + "Incident", but no precedent was both.
    precedents = [
        make_precedent("Request", "high", 0.9),
        make_precedent("Incident", "medium", 0.8),
    ]

    assert (
        find_mandatory_escalation(ROUTINE_CLASSIFIER, precedents, TriageConfig()) == []
    )


def test_high_priority_incident_precedents_escalate() -> None:
    precedents = [
        make_precedent("Incident", "high", 0.9),
        make_precedent("Request", "low", 0.3),
    ]

    reasons = find_mandatory_escalation(ROUTINE_CLASSIFIER, precedents, TriageConfig())

    assert reasons == ["High-priority Incident flagged by 75% of the precedent vote"]


def test_classifier_alone_can_escalate() -> None:
    classifier = labels_from_choices("Incident", "Technical Support", "high", 0.8)

    reasons = find_mandatory_escalation(classifier, [], TriageConfig())

    assert reasons == ["High-priority Incident flagged by the classifier"]


def test_low_classifier_confidence_and_margin_require_human_review() -> None:
    classifier = TicketLabels(
        source="classifier",
        type=LabelDistribution({"Incident": 0.54, "Request": 0.46}),
        queue=LabelDistribution({"IT Support": 0.9, "Billing": 0.1}),
        priority=LabelDistribution({"medium": 0.8, "low": 0.2}),
    )

    reasons = find_model_uncertainty(classifier, TriageConfig())

    assert reasons == [
        "Low classifier confidence: type (0.54 < 0.55)",
        "Ambiguous classifier margin: type (0.08 < 0.10)",
    ]


def test_uncertainty_threshold_boundaries_are_accepted() -> None:
    classifier = TicketLabels(
        source="classifier",
        type=LabelDistribution({"Incident": 0.55, "Request": 0.45}),
        queue=LabelDistribution({"IT Support": 0.75, "Billing": 0.25}),
        priority=LabelDistribution({"medium": 0.8, "low": 0.2}),
    )

    assert find_model_uncertainty(classifier, TriageConfig()) == []


def test_probability_margin_handles_empty_and_single_label_distributions() -> None:
    assert probability_margin(LabelDistribution({})) == 0.0
    assert probability_margin(LabelDistribution({"Incident": 0.8})) == 0.8


def test_routing_does_not_treat_low_confidence_as_an_llm_problem() -> None:
    classifier = TicketLabels(
        source="classifier",
        type=LabelDistribution({"Request": 0.51, "Incident": 0.49}),
        queue=LabelDistribution({"IT Support": 0.51, "Billing": 0.49}),
        priority=LabelDistribution({"medium": 0.51, "low": 0.49}),
    )

    decision = choose_route(
        classifier_labels=classifier,
        disagreements=[],
        top_similarity=0.9,
        risk_signals=[],
        unsupported_requests=[],
        has_attachments=False,
        config=TriageConfig(),
    )

    assert find_model_uncertainty(classifier, TriageConfig())
    assert decision.route == "fast"
    assert decision.reasons == []
