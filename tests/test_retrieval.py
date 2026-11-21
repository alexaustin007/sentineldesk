from pathlib import Path

import pytest

from sentineldesk.data_interface import load_mock_historical_tickets
from sentineldesk.retrieval import PrecedentIndex, TfidfEmbedder, mix_languages
from sentineldesk.schemas import Precedent, ticket_text


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


def make_precedent(ticket_id: str, language: str, similarity: float) -> Precedent:
    return Precedent(
        ticket_id=ticket_id,
        similarity=similarity,
        subject="",
        body="",
        answer="",
        type="Incident",
        queue="IT Support",
        priority="medium",
        language=language,
    )


def test_german_ticket_keeps_strong_english_precedents() -> None:
    candidates = [
        make_precedent("DE-1", "de", 0.9),
        make_precedent("DE-2", "de", 0.8),
        make_precedent("DE-3", "de", 0.7),
        make_precedent("EN-1", "en", 0.6),
        make_precedent("EN-2", "en", 0.3),  # too weak to count as evidence
    ]

    chosen = mix_languages(
        candidates, count=3, language="de", min_other_language=2, min_similarity=0.5
    )

    assert [precedent.ticket_id for precedent in chosen] == ["DE-1", "DE-2", "EN-1"]


def test_missing_subject_is_skipped() -> None:
    assert ticket_text(None, "Body text") == "Body text"
    assert ticket_text(float("nan"), "Body text") == "Body text"
    assert ticket_text("Subject", "Body text") == "Subject\nBody text"
