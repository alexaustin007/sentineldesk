from sentineldesk.schemas import Precedent
from sentineldesk.verification import verify_reply


def make_precedent(ticket_id: str, answer: str) -> Precedent:
    return Precedent(
        ticket_id=ticket_id,
        similarity=0.8,
        subject="",
        body="",
        answer=answer,
        type="Problem",
        queue="Billing and Payments",
        priority="medium",
        language="en",
    )


REFUND_EVIDENCE = [
    make_precedent(
        "MOCK-0005",
        "We confirmed the duplicate charge and issued a refund for the second "
        "payment. Refunds appear within 5-7 business days.",
    )
]
VPN_EVIDENCE = [
    make_precedent(
        "MOCK-0002", "Please reinstall the VPN client and restart your laptop."
    )
]


def test_grounded_reply_passes() -> None:
    draft = (
        "Hello,\n\nWe confirmed the duplicate charge and issued a refund. [MOCK-0005] "
        "It appears within 5-7 business days. [MOCK-0005]\n\nBest regards"
    )

    result = verify_reply(draft, REFUND_EVIDENCE, "en")

    assert result.passed, result.issues
    assert result.cleaned_reply == draft


def test_unsupported_promise_is_removed() -> None:
    draft = (
        "Please reinstall the VPN client and restart your laptop. [MOCK-0002] "
        "You are entitled to a $500 refund."
    )

    result = verify_reply(draft, VPN_EVIDENCE, "en")

    assert not result.passed
    assert result.removed_claims == ["You are entitled to a $500 refund."]
    assert "$500" not in result.cleaned_reply
    assert "[MOCK-0002]" in result.cleaned_reply


def test_citation_to_unretrieved_ticket_fails() -> None:
    draft = "Please reinstall the VPN client and restart your laptop. [TKT-99999]"

    result = verify_reply(draft, VPN_EVIDENCE, "en")

    assert not result.passed
    assert "Reply cites no retrieved historical ticket" in result.issues


def test_template_placeholder_is_removed() -> None:
    draft = (
        "Please reinstall the VPN client and restart your laptop. [MOCK-0002] "
        "Call us at <tel_num> if it fails."
    )

    result = verify_reply(draft, VPN_EVIDENCE, "en")

    assert not result.passed
    assert result.removed_claims == ["Call us at <tel_num> if it fails."]
    assert "<tel_num>" not in result.cleaned_reply


def test_grouped_citations_are_split_and_checked() -> None:
    evidence = REFUND_EVIDENCE + VPN_EVIDENCE
    draft = (
        "We confirmed the duplicate charge and issued a refund [MOCK-0005, MOCK-0002]."
    )

    result = verify_reply(draft, evidence, "en")

    assert result.passed, result.issues
    assert "[MOCK-0005] [MOCK-0002]" in result.cleaned_reply


def test_personal_data_in_reply_fails() -> None:
    draft = (
        "Please reinstall the VPN client and restart your laptop [MOCK-0002], "
        "then email admin@example.com."
    )

    result = verify_reply(draft, VPN_EVIDENCE, "en")

    assert not result.passed
    assert any("email" in issue for issue in result.issues)
