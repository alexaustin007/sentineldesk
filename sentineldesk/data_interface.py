"""Temporary data-loading interface for the RAG index.

Ivy owns the official 80/20 split and the ticket IDs, so this module never creates a
split of its own. Until her module is merged, `load_historical_tickets` serves a
small mock knowledge base so the RAG engine and the agent workflow can be built and
tested. When the official split lands, return its historical (training) DataFrame
from `load_historical_tickets`. Nothing else in the pipeline has to change.
"""

from collections.abc import Iterable

import pandas as pd

from sentineldesk.mock_data import MOCK_HISTORICAL_TICKETS
from sentineldesk.schemas import clean_text

REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticket_id",
    "subject",
    "body",
    "answer",
    "type",
    "queue",
    "priority",
    "language",
)


def load_historical_tickets() -> pd.DataFrame:
    """Return the historical tickets the RAG index is allowed to use.

    Integration point: replace the mock data with the historical split from Ivy's
    module, and keep the call to `validate_historical_tickets`.
    """
    return validate_historical_tickets(pd.DataFrame(MOCK_HISTORICAL_TICKETS))


def validate_historical_tickets(
    tickets: pd.DataFrame, holdout_ticket_ids: Iterable[str] = ()
) -> pd.DataFrame:
    """Check the columns and ticket IDs the index relies on, and block holdout leakage.

    Pass the holdout ticket IDs whenever they are available. Indexing a holdout
    ticket is a leakage violation, so this raises instead of continuing. Rows
    without an answer are dropped because they cannot ground a reply.
    """
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in tickets.columns
    ]
    if missing_columns:
        raise ValueError(f"Historical tickets are missing columns: {missing_columns}")

    ticket_ids = tickets["ticket_id"].astype(str)
    if ticket_ids.duplicated().any():
        raise ValueError("Ticket IDs must be unique so each citation names one ticket.")

    leaked_ids = set(ticket_ids) & {str(ticket_id) for ticket_id in holdout_ticket_ids}
    if leaked_ids:
        raise ValueError(
            f"{len(leaked_ids)} holdout tickets are in the historical set. "
            "Refusing to index them."
        )

    has_answer = tickets["answer"].map(clean_text) != ""
    return tickets.assign(ticket_id=ticket_ids).loc[has_answer].reset_index(drop=True)
