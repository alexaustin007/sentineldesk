"""Data loading for the RAG index: the official historical split, or mock tickets.

scripts/prepare_data.py owns the 80/20 split and the ticket IDs. This module never
splits data itself. It reads the historical files that script writes:
`knowledge_base.csv` has the answers and `train.csv` has the labels, so the two are
joined on ticket_id. Holdout IDs are read only to prove no holdout ticket is indexed.
"""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from sentineldesk.config import LABEL_HEADS, PREPARED_DATA_DIR
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


def has_prepared_data(prepared_dir: Path = PREPARED_DATA_DIR) -> bool:
    """True once scripts/prepare_data.py has written the knowledge base."""
    return (prepared_dir / "knowledge_base.csv").exists()


def load_historical_tickets(prepared_dir: Path = PREPARED_DATA_DIR) -> pd.DataFrame:
    """Return the historical tickets the RAG index may use.

    Uses the official split when it exists, and the mock tickets otherwise.
    """
    if not has_prepared_data(prepared_dir):
        return load_mock_historical_tickets()
    knowledge_base = _read_csv(prepared_dir / "knowledge_base.csv")
    labels = _read_csv(prepared_dir / "train.csv")[["ticket_id", *LABEL_HEADS]]
    tickets = knowledge_base.merge(
        labels, on="ticket_id", how="inner", validate="one_to_one"
    )
    if len(tickets) != len(knowledge_base):
        raise ValueError("Every knowledge-base ticket needs labels in train.csv.")
    return validate_historical_tickets(tickets, load_holdout_ticket_ids(prepared_dir))


def load_mock_historical_tickets() -> pd.DataFrame:
    """The 16 hand-written tickets, for tests and offline demos."""
    return validate_historical_tickets(pd.DataFrame(MOCK_HISTORICAL_TICKETS))


def load_holdout_ticket_ids(prepared_dir: Path = PREPARED_DATA_DIR) -> set[str]:
    """Holdout ticket IDs only (no text or labels), used to block leakage."""
    path = prepared_dir / "holdout_inputs.csv"
    if not path.exists():
        return set()
    return set(_read_csv(path, columns=["ticket_id"])["ticket_id"])


def validate_historical_tickets(
    tickets: pd.DataFrame, holdout_ticket_ids: Iterable[str] = ()
) -> pd.DataFrame:
    """Check the columns and ticket IDs the index relies on, and block holdout leakage.

    Indexing a holdout ticket is a leakage violation, so this raises instead of
    continuing. Rows without an answer are dropped because they cannot ground a
    reply.
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


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    # Read everything as text so blank subjects stay "" instead of becoming NaN.
    return pd.read_csv(path, dtype=str, keep_default_na=False, usecols=columns)
