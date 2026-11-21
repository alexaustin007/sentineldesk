from sentineldesk.classifier_interface import labels_from_choices
from sentineldesk.config import TriageConfig
from sentineldesk.escalation import find_mandatory_escalation
from sentineldesk.schemas import Precedent

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
