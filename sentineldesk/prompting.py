"""Prompt-building helpers shared by the agents. Ticket text is always PII-masked."""

from collections.abc import Sequence

from sentineldesk.config import LABEL_HEADS
from sentineldesk.guardrails import mask_pii
from sentineldesk.schemas import Precedent, ScreeningResult, TicketLabels


def format_ticket(screening: ScreeningResult) -> str:
    """The masked ticket, wrapped in tags that mark it as untrusted input."""
    return "\n".join(
        [
            f'<ticket language="{screening.language}">',
            f"Subject: {screening.masked_subject or '(no subject)'}",
            f"Body: {screening.masked_body}",
            "</ticket>",
        ]
    )


def format_labels(labels: TicketLabels | None) -> str:
    if labels is None:
        return "no prediction"
    return ", ".join(
        f"{head}={labels.head(head).label} ({labels.head(head).confidence:.2f})"
        for head in LABEL_HEADS
    )


def format_precedents(precedents: Sequence[Precedent]) -> str:
    blocks = []
    for precedent in precedents:
        subject, _ = mask_pii(precedent.subject)
        answer, _ = mask_pii(precedent.answer.replace("<br>", " "))
        blocks.append(
            f"[{precedent.ticket_id}] similarity {precedent.similarity:.2f} | "
            f"{precedent.type} / {precedent.queue} / {precedent.priority} | "
            f"language {precedent.language}\n"
            f"Subject: {subject or '(no subject)'}\n"
            f"Resolution: {answer}"
        )
    return "\n\n".join(blocks)
