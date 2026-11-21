"""Assemble the triage workflow for the console and the demo in one call."""

from pathlib import Path

from sentineldesk.classifier_interface import (
    MockClassifier,
    TicketClassifier,
    load_team_classifier,
)
from sentineldesk.config import INDEX_DIR, TriageConfig
from sentineldesk.data_interface import (
    has_prepared_data,
    load_historical_tickets,
    load_mock_historical_tickets,
)
from sentineldesk.llm import create_llm_provider
from sentineldesk.orchestrator import TriageOrchestrator
from sentineldesk.retrieval import PrecedentIndex, create_embedder


def load_precedent_index(
    index_dir: Path = INDEX_DIR, *, allow_mock: bool = True
) -> PrecedentIndex:
    """Load the saved index, with an explicit mock-only development fallback.

    A real prepared dataset is never embedded on an app request. That work can be
    large and belongs in the one-time build command before a demo.
    """
    if not allow_mock and not has_prepared_data():
        raise RuntimeError(
            "Judge mode requires the prepared dataset. Run "
            "`python scripts/prepare_data.py --dataset full`."
        )
    if (index_dir / "index.faiss").exists():
        index = PrecedentIndex.load(index_dir)
        if not allow_mock:
            _validate_judge_index(index)
        return index
    if has_prepared_data():
        raise RuntimeError(
            "Prepared data exists but the saved precedent index is missing. "
            "Run `python -m sentineldesk.build_index` before starting the app."
        )
    if not allow_mock:
        raise RuntimeError(
            "No real precedent index is available. Prepare the dataset and run "
            "`python -m sentineldesk.build_index`."
        )
    print("No saved index found; using the 16-ticket mock knowledge base.")
    return PrecedentIndex.build(
        load_mock_historical_tickets(), create_embedder("tfidf")
    )


def _validate_judge_index(index: PrecedentIndex) -> None:
    """Prove the saved index matches the current prepared historical split."""
    expected = load_historical_tickets()
    expected_ids = set(expected["ticket_id"].astype(str))
    actual_ids = set(index.tickets["ticket_id"].astype(str))
    if index.index.ntotal != len(index.tickets) or actual_ids != expected_ids:
        raise RuntimeError(
            "The saved precedent index is stale or built from different data. "
            "Rebuild it with `python -m sentineldesk.build_index`."
        )
    expected_embedder = create_embedder("sentence-transformers").name
    if index.embedder.name != expected_embedder:
        raise RuntimeError(
            "Judge mode requires an index built with the configured multilingual "
            f"embedder ({expected_embedder}). Rebuild the index."
        )


def load_classifier(*, allow_mock: bool = True) -> TicketClassifier:
    """Load the trained classifier or an explicitly allowed development mock."""
    classifier = load_team_classifier()
    if classifier is None:
        if not allow_mock:
            raise RuntimeError(
                "Trained classifier artifacts are missing. Run "
                "`python classification/classify.py` before starting judge mode."
            )
        print(
            "Trained classifier not found; using the keyword mock. "
            "Run `python classification/classify.py` to train it."
        )
        return MockClassifier()
    return classifier


def create_orchestrator(
    classifier: TicketClassifier | None = None,
    config: TriageConfig | None = None,
    index_dir: Path = INDEX_DIR,
    *,
    allow_mock: bool = True,
) -> TriageOrchestrator:
    """The full workflow: trained classifier, saved index, and LLM from the environment.

    Build this once and reuse it (for example with Streamlit's st.cache_resource).
    """
    selected_classifier = classifier or load_classifier(allow_mock=allow_mock)
    precedent_index = load_precedent_index(index_dir, allow_mock=allow_mock)
    provider = create_llm_provider()
    if not allow_mock and provider.name == "mock":
        raise RuntimeError(
            "Judge mode requires Gemini credentials. Configure GEMINI_API_KEY or "
            "Google Cloud Application Default Credentials."
        )
    return TriageOrchestrator(
        classifier=selected_classifier,
        precedent_index=precedent_index,
        llm_provider=provider,
        config=config or TriageConfig(),
    )
