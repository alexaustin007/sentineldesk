"""Shared fixtures: the mock knowledge base, TF-IDF retrieval, and mock agents."""

import pytest
from samples import TEST_CONFIG, OrchestratorFactory

from sentineldesk.classifier_interface import MockClassifier, TicketClassifier
from sentineldesk.config import TriageConfig
from sentineldesk.data_interface import load_historical_tickets
from sentineldesk.llm import LLMProvider, MockLLMProvider
from sentineldesk.orchestrator import TriageOrchestrator
from sentineldesk.retrieval import PrecedentIndex, TfidfEmbedder


@pytest.fixture(scope="session")
def precedent_index() -> PrecedentIndex:
    return PrecedentIndex.build(load_historical_tickets(), TfidfEmbedder())


@pytest.fixture
def make_orchestrator(precedent_index: PrecedentIndex) -> OrchestratorFactory:
    def factory(
        classifier: TicketClassifier | None = None,
        provider: LLMProvider | None = None,
        config: TriageConfig = TEST_CONFIG,
    ) -> TriageOrchestrator:
        return TriageOrchestrator(
            classifier=classifier or MockClassifier(),
            precedent_index=precedent_index,
            llm_provider=provider or MockLLMProvider(),
            config=config,
        )

    return factory
