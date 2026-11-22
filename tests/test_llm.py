import pytest

from sentineldesk.llm import choose_provider_kind

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


def test_credentials_alone_keep_mock_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert choose_provider_kind() == "mock"


def test_api_key_selects_developer_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert choose_provider_kind() == "gemini"


def test_enterprise_flag_wins_over_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")

    assert choose_provider_kind() == "enterprise"


def test_explicit_choice_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "true")
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "mock")

    assert choose_provider_kind() == "mock"
