from pathlib import Path

import pytest

from sentineldesk.data_interface import load_mock_historical_tickets
from sentineldesk.retrieval import PrecedentIndex, TfidfEmbedder
from sentineldesk.schemas import ticket_text


def test_search_returns_closest_precedent_first(
    precedent_index: PrecedentIndex,
) -> None:
    precedents = precedent_index.search(
        "I forgot my password and the reset email never arrives", top_k=3
    )

    assert precedents[0].ticket_id == "MOCK-0003"
    assert (
        precedents[0].similarity >= precedents[1].similarity >= precedents[2].similarity
    )


def test_saved_index_returns_the_same_results(
    precedent_index: PrecedentIndex, tmp_path: Path
) -> None:
    precedent_index.save(tmp_path)
    loaded_index = PrecedentIndex.load(tmp_path)
    query = "We were charged twice for the invoice"

    original_ids = [p.ticket_id for p in precedent_index.search(query, top_k=3)]
    loaded_ids = [p.ticket_id for p in loaded_index.search(query, top_k=3)]

    assert loaded_ids == original_ids


def test_holdout_tickets_cannot_be_indexed() -> None:
    with pytest.raises(ValueError, match="holdout"):
        PrecedentIndex.build(
            load_mock_historical_tickets(),
            TfidfEmbedder(),
            holdout_ticket_ids=["MOCK-0001"],
        )


def test_missing_subject_is_skipped() -> None:
    assert ticket_text(None, "Body text") == "Body text"
    assert ticket_text(float("nan"), "Body text") == "Body text"
    assert ticket_text("Subject", "Body text") == "Subject\nBody text"
