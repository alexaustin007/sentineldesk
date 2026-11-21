"""Constants shared by the tests."""

from collections.abc import Callable

from sentineldesk.config import TriageConfig
from sentineldesk.orchestrator import TriageOrchestrator

# TF-IDF similarities on the tiny mock corpus run lower than sentence embeddings.
TEST_CONFIG = TriageConfig(min_top_similarity=0.3)

PASSWORD_SUBJECT = "Forgot my password"
PASSWORD_BODY = (
    "I forgot my password for the customer portal and the reset email never arrives."
)

OrchestratorFactory = Callable[..., TriageOrchestrator]
