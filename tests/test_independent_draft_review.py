import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from samples import PASSWORD_BODY, PASSWORD_SUBJECT, TEST_CONFIG, OrchestratorFactory

from api import main
from sentineldesk.llm import (
    LLMRequest,
    LLMUnavailableError,
    MockLLMProvider,
    default_mock_responder,
)
from sentineldesk.orchestrator import StageTimer

BILLING = {
    "subject": "Doppelte Abbuchung der Rechnung",
    "body": "Uns wurde die Rechnung für April doppelt abgebucht.",
}
OUTAGE = {
    "subject": "VPN outage at all hospital sites",
    "body": "Since 7am no clinician can reach the EMR through the VPN.",
}
APPROVAL = {
    "grounded": True,
    "valid_citations": True,
    "unsupported_claims": [],
    "recommend_escalation": False,
    "rationale": "The cited resolution supports this reply.",
}


@pytest.mark.parametrize(
    ("scenario", "ticket", "expected"),
    [
        ("supported German reply", BILLING, "auto_draft"),
        ("unsupported promise", BILLING, "human_review"),
        ("same promise with review disabled", BILLING, "auto_draft"),
        ("invalid verdict", BILLING, "human_review"),
        ("review unavailable", BILLING, "human_review"),
        ("urgent incident", OUTAGE, "escalate"),
        (
            "insufficient time",
            {"subject": PASSWORD_SUBJECT, "body": PASSWORD_BODY},
            "human_review",
        ),
    ],
)
def test_review_through_live_api_route(
    scenario: str,
    ticket: dict[str, str],
    expected: str,
    make_orchestrator: OrchestratorFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def respond(request: LLMRequest) -> str:
        calls.append(request)
        if request.task == "draft_reply" and scenario in {
            "unsupported promise",
            "same promise with review disabled",
        }:
            return (
                "Hallo, wir erstatten Ihnen auch alle künftigen Zahlungen. [MOCK-0006]"
            )
        if request.task != "grounding_review":
            return default_mock_responder(request)
        if scenario == "review unavailable":
            raise LLMUnavailableError("review offline")
        if scenario == "invalid verdict":
            return '{"grounded":"maybe"}'
        if scenario == "unsupported promise":
            assert "künftigen Zahlungen" in request.user_prompt
            return json.dumps(
                {
                    **APPROVAL,
                    "grounded": False,
                    "unsupported_claims": ["future refunds"],
                    "recommend_escalation": True,
                }
            )
        return json.dumps(APPROVAL)

    if scenario == "insufficient time":
        monkeypatch.setattr(StageTimer, "elapsed_ms", lambda self: 26_500.0)
    config = replace(
        TEST_CONFIG,
        independent_draft_review=scenario != "same promise with review disabled",
    )
    orchestrator = make_orchestrator(
        provider=MockLLMProvider(responder=respond), config=config
    )
    monkeypatch.setattr(main, "get_orchestrator", lambda: orchestrator)
    with TestClient(main.app) as client:
        response = client.post("/api/triage", json=ticket)
    assert response.status_code == 200
    result = response.json()
    assert result["request_id"]
    assert isinstance(result["classification"]["critical_incident_risk"], (float, int))
    assert result["escalation"]["status"] == expected
    reviews = [c for c in calls if c.task == "grounding_review"]
    if scenario == "urgent incident":
        assert not calls and result["draft"] is None
    elif scenario == "same promise with review disabled":
        assert not reviews
        assert "künftigen Zahlungen" in result["draft"]["text"]
    elif scenario == "insufficient time":
        assert not reviews
        assert "ran out of time" in result["guardrails"]["verification_issues"][0]
    else:
        assert len(reviews) == 1
        assert reviews[0].timeout_ms > 0
        assert "grounding_review" in result["latency_ms"]
        if expected == "auto_draft":
            assert result["draft"]["language"] == "de"
            assert result["draft"]["citations"] == ["MOCK-0006"]
        else:
            assert result["guardrails"]["verification_issues"]
