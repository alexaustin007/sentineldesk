from pathlib import Path

import pandas as pd
import pytest

from sentineldesk.data_interface import (
    load_historical_tickets,
    load_holdout_ticket_ids,
)


def write_prepared_files(directory: Path, holdout_ids: list[str]) -> None:
    """Fake files with the same columns as scripts/prepare_data.py writes."""
    pd.DataFrame(
        {
            "ticket_id": ["TKT-00001", "TKT-00002"],
            "subject": ["VPN down", ""],
            "body": ["Nobody can connect.", "Charged twice."],
            "answer": ["We renewed the certificate.", "We issued a refund."],
            "language": ["en", "en"],
        }
    ).to_csv(directory / "knowledge_base.csv", index=False)
    pd.DataFrame(
        {
            "ticket_id": ["TKT-00001", "TKT-00002", "TKT-00003"],
            "subject": ["VPN down", "", "No answer yet"],
            "body": ["Nobody can connect.", "Charged twice.", "Still open."],
            "type": ["Incident", "Problem", "Request"],
            "queue": ["IT Support", "Billing and Payments", "Customer Service"],
            "priority": ["high", "medium", "low"],
            "language": ["en", "en", "en"],
        }
    ).to_csv(directory / "train.csv", index=False)
    pd.DataFrame(
        {"ticket_id": holdout_ids, "subject": "", "body": "Holdout text"}
    ).to_csv(directory / "holdout_inputs.csv", index=False)


def test_prepared_split_joins_answers_with_labels(tmp_path: Path) -> None:
    write_prepared_files(tmp_path, holdout_ids=["TKT-00009"])

    tickets = load_historical_tickets(tmp_path)

    assert tickets["ticket_id"].tolist() == ["TKT-00001", "TKT-00002"]
    assert tickets["priority"].tolist() == ["high", "medium"]
    assert tickets.loc[1, "subject"] == ""  # blank subjects stay blank
    assert load_holdout_ticket_ids(tmp_path) == {"TKT-00009"}


def test_holdout_overlap_is_refused(tmp_path: Path) -> None:
    write_prepared_files(tmp_path, holdout_ids=["TKT-00002"])

    with pytest.raises(ValueError, match="holdout"):
        load_historical_tickets(tmp_path)


def test_mock_tickets_are_used_without_prepared_data(tmp_path: Path) -> None:
    tickets = load_historical_tickets(tmp_path)

    assert tickets["ticket_id"].str.startswith("MOCK-").all()
