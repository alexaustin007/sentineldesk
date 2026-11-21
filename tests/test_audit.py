import json

from samples import PASSWORD_BODY, PASSWORD_SUBJECT, OrchestratorFactory

from sentineldesk.audit import build_audit_event


def test_audit_event_contains_codes_and_counts_but_no_customer_text(
    make_orchestrator: OrchestratorFactory,
) -> None:
    secret = "private.person@example.com"
    result = make_orchestrator().triage(
        PASSWORD_SUBJECT, PASSWORD_BODY + f" Contact {secret}."
    )

    encoded = json.dumps(build_audit_event(result))

    assert "EMAIL" in encoded
    assert secret not in encoded
    assert PASSWORD_BODY not in encoded
