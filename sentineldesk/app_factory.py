"""Assemble the triage workflow for the console and the demo in one call."""

from pathlib import Path

from sentineldesk.classifier_interface import (
    MockClassifier,
    TicketClassifier,
    load_team_classifier,
)
from sentineldesk.config import INDEX_DIR, TriageConfig
from sentineldesk.data_interface import load_historical_tickets
from sentineldesk.llm import create_llm_provider
from sentineldesk.orchestrator import TriageOrchestrator
from sentineldesk.retrieval import PrecedentIndex, create_embedder


def load_precedent_index(index_dir: Path = INDEX_DIR) -> PrecedentIndex:
    """Load the saved index, or build one from the available data (slower)."""
    if (index_dir / "index.faiss").exists():
        return PrecedentIndex.load(index_dir)
    print("No saved index found; building one now. Run sentineldesk.build_index once.")
    return PrecedentIndex.build(load_historical_tickets(), create_embedder())


def load_classifier() -> TicketClassifier:
    """The team's trained classifier, or the keyword mock until it is trained."""
    classifier = load_team_classifier()
    if classifier is None:
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
) -> TriageOrchestrator:
    """The full workflow: trained classifier, saved index, and LLM from the environment.

    Build this once and reuse it (for example with Streamlit's st.cache_resource).
    """
    return TriageOrchestrator(
        classifier=classifier or load_classifier(),
        precedent_index=load_precedent_index(index_dir),
        llm_provider=create_llm_provider(),
        config=config or TriageConfig(),
    )
