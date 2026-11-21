from samples import PASSWORD_BODY, PASSWORD_SUBJECT, TEST_CONFIG, OrchestratorFactory

from api.contract import reason_code, to_contract


def test_contract_has_every_field_the_console_requires(
    make_orchestrator: OrchestratorFactory,
) -> None:
    result = make_orchestrator().triage(PASSWORD_SUBJECT, PASSWORD_BODY)

    contract = to_contract(result, TEST_CONFIG)

    assert contract["escalation"]["status"] == "auto_draft"
    for head in ("type", "queue", "priority"):
        assert isinstance(contract["classification"][head]["label"], str)
        assert 0 <= contract["classification"][head]["confidence"] <= 1
    assert contract["precedents"][0]["ticket_id"] == "MOCK-0003"
    assert contract["precedents"][0]["answer"]
    assert contract["draft"]["citations"] == ["MOCK-0003"]
    assert contract["latency_ms"]["total"] > 0
    assert "final_labels" not in contract  # the console rejects the raw result


def test_reason_codes_follow_the_message_prefix() -> None:
    assert reason_code("High-priority Incident flagged by the classifier") == (
        "HIGH_PRIORITY_INCIDENT"
    )
    assert reason_code("Possible prompt injection: ignore all") == "PROMPT_INJECTION"
    assert reason_code("Something new") == "OTHER"
