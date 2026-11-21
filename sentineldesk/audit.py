"""Redacted, structured audit events for triage and security monitoring."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sentineldesk.schemas import TriageResult

AUDIT_LOGGER = logging.getLogger("sentineldesk.audit")


def configure_audit_file(path: str | Path) -> None:
    """Write one JSON object per line to an explicitly configured durable sink."""
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == destination.resolve()
        for handler in AUDIT_LOGGER.handlers
    ):
        return
    handler = logging.FileHandler(destination, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    AUDIT_LOGGER.addHandler(handler)
    AUDIT_LOGGER.setLevel(logging.INFO)
    AUDIT_LOGGER.propagate = False


def build_audit_event(result: TriageResult) -> dict[str, Any]:
    """Return operational evidence without raw customer or historical text."""
    return {
        "event": "ticket_triage_completed",
        "status": result.status,
        "route": result.route,
        "reason_count": len(result.reasons),
        "security_events": list(result.security_events),
        "pii_counts": dict(result.pii_counts),
        "language": result.language,
        "classifier_labels": {
            head: result.classifier_labels.head(head).label
            for head in ("type", "queue", "priority")
        },
        "evidence_sufficient": result.evidence_sufficient,
        "top_similarity": round(result.top_similarity, 4),
        "llm_call_count": len(result.llm_calls),
        "latency_ms": round(result.latency_ms, 1),
    }


def emit_audit_event(result: TriageResult) -> None:
    """Write one JSON event through the standard logging configuration."""
    AUDIT_LOGGER.info(json.dumps(build_audit_event(result), sort_keys=True))


if audit_path := os.getenv("SENTINEL_AUDIT_LOG"):
    configure_audit_file(audit_path)
