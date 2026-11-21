import json

import pytest

from sentineldesk.grounding_review import GroundingVerdict, run_grounding_review
from sentineldesk.llm import LLMRequest, MockLLMProvider
from sentineldesk.schemas import Precedent, ScreeningResult


def make_screening() -> ScreeningResult:
    return ScreeningResult(
        language="en",
        language_supported=True,
        masked_subject="VPN unavailable",
        masked_body="The client cannot connect.",
        pii_counts={},
        injection_signals=[],
    )


def make_precedent() -> Precedent:
    return Precedent(
        ticket_id="MOCK-0002",
        similarity=0.9,
        subject="VPN connection",
        body="The VPN client fails to connect.",
        answer="Please reinstall the VPN client and restart your laptop.",
        type="Problem",
        queue="IT Support",
        priority="medium",
        language="en",
    )


def test_mock_grounding_review_accepts_retrieved_citations() -> None:
    verdict, record = run_grounding_review(
        MockLLMProvider(),
        make_screening(),
        "Please reinstall the VPN client. [MOCK-0002]",
        [make_precedent()],
    )

    assert verdict is not None
    assert verdict.grounded
    assert verdict.valid_citations
    assert not verdict.recommend_escalation
    assert record.task == "grounding_review"
    assert record.tier == "deep"


def test_invalid_grounding_schema_fails_closed() -> None:
    def invalid_response(_request: LLMRequest) -> str:
        return json.dumps(
            {
                "grounded": True,
                "valid_citations": True,
                "unsupported_claims": [],
                "recommend_escalation": False,
                "rationale": "Looks fine.",
                "auto_send": True,
            }
        )

    verdict, record = run_grounding_review(
        MockLLMProvider(responder=invalid_response),
        make_screening(),
        "Please reinstall the VPN client. [MOCK-0002]",
        [make_precedent()],
    )

    assert verdict is None
    assert record.task == "grounding_review"


def test_grounding_verdict_forbids_unexpected_fields() -> None:
    with pytest.raises(ValueError):
        GroundingVerdict.model_validate(
            {
                "grounded": True,
                "valid_citations": True,
                "unsupported_claims": [],
                "recommend_escalation": False,
                "rationale": "Supported.",
                "send_to_customer": True,
            }
        )


def test_grounding_verdict_rejects_inconsistent_approval() -> None:
    with pytest.raises(ValueError):
        GroundingVerdict.model_validate(
            {
                "grounded": True,
                "valid_citations": True,
                "unsupported_claims": ["Invented refund"],
                "recommend_escalation": False,
                "rationale": "Contradictory output.",
            }
        )
