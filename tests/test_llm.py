import pytest

from sentineldesk.classifier_interface import labels_from_choices
from sentineldesk.llm import (
    LLMUnavailableError,
    MockLLMProvider,
    choose_provider_kind,
)
from sentineldesk.reply_generation import DraftPayload, draft_reply
from sentineldesk.schemas import Precedent, ScreeningResult

PROVIDER_VARIABLES = (
    "SENTINEL_LLM_PROVIDER",
    "GOOGLE_GENAI_USE_ENTERPRISE",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in PROVIDER_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_mock_without_credentials() -> None:
    assert choose_provider_kind() == "mock"


def test_api_key_selects_developer_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert choose_provider_kind() == "gemini"


def test_enterprise_flag_wins_over_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")

    assert choose_provider_kind() == "enterprise"


def test_explicit_choice_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "mock")

    assert choose_provider_kind() == "mock"


def test_mock_draft_uses_strict_structured_output() -> None:
    precedent = Precedent(
        ticket_id="MOCK-0002",
        similarity=0.9,
        subject="VPN",
        body="Cannot connect",
        answer="Please reinstall the VPN client and restart your laptop.",
        type="Problem",
        queue="IT Support",
        priority="medium",
        language="en",
    )
    screening = ScreeningResult(
        language="en",
        language_supported=True,
        masked_subject="VPN",
        masked_body="Cannot connect",
        pii_counts={},
        injection_signals=[],
    )

    result = draft_reply(
        MockLLMProvider(),
        "fast",
        screening,
        labels_from_choices("Problem", "IT Support", "medium", 0.9),
        [precedent],
    )

    assert result.evidence_sufficient
    assert result.cited_ticket_ids == ("MOCK-0002",)
    assert "[MOCK-0002]" in result.text


def test_invalid_structured_draft_fails_closed() -> None:
    precedent = Precedent(
        ticket_id="MOCK-0002",
        similarity=0.9,
        subject="VPN",
        body="Cannot connect",
        answer="Reinstall the VPN client.",
        type="Problem",
        queue="IT Support",
        priority="medium",
        language="en",
    )
    screening = ScreeningResult(
        language="en",
        language_supported=True,
        masked_subject="VPN",
        masked_body="Cannot connect",
        pii_counts={},
        injection_signals=[],
    )

    def invalid_response(_request: object) -> str:
        return '{"draft": "No structured safety fields"}'

    with pytest.raises(LLMUnavailableError, match="invalid structured response"):
        draft_reply(
            MockLLMProvider(responder=invalid_response),
            "fast",
            screening,
            labels_from_choices("Problem", "IT Support", "medium", 0.9),
            [precedent],
        )


def test_draft_payload_forbids_unexpected_fields() -> None:
    with pytest.raises(ValueError):
        DraftPayload.model_validate(
            {
                "draft": "Restart the VPN client. [MOCK-0002]",
                "cited_ticket_ids": ["MOCK-0002"],
                "evidence_sufficient": True,
                "auto_approve": True,
            }
        )
