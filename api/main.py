"""HTTP API for the triage console.

    uvicorn api.main:app --port 8000

The console's dev server forwards /api to this port. The workflow (classifier,
precedent index, and Gemini) is built once at startup and reused for every ticket.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.contract import to_contract
from sentineldesk.app_factory import create_orchestrator
from sentineldesk.orchestrator import TriageOrchestrator


class TriageRequest(BaseModel):
    subject: str | None = None
    body: str


@lru_cache(maxsize=1)
def get_orchestrator() -> TriageOrchestrator:
    return create_orchestrator()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load the index, classifier, and LLM, and run one search so the embedding
    # model is in memory before the first real ticket (it otherwise adds ~7 s).
    get_orchestrator().precedent_index.search("warm-up", top_k=1)
    yield


app = FastAPI(title="SentinelDesk triage API", lifespan=lifespan)

# Locally the console's dev server proxies /api, so no cross-origin access is needed.
# A hosted console (for example on Vercel) that calls this API directly must be
# listed here, comma-separated: SENTINEL_ALLOWED_ORIGINS=https://your-app.vercel.app
allowed_origins = [
    origin.strip()
    for origin in os.getenv("SENTINEL_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "ngrok-skip-browser-warning"],
    )


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


@app.post("/api/triage")
def triage(request: TriageRequest) -> JSONResponse:
    if not request.body.strip():
        return error_response(400, "EMPTY_BODY", "The ticket body is required.")
    orchestrator = get_orchestrator()
    result = orchestrator.triage(request.subject, request.body)
    return JSONResponse(to_contract(result, orchestrator.config))


@app.exception_handler(Exception)
async def unexpected_error(_: Request, error: Exception) -> JSONResponse:
    """Report failures to the console as a readable error instead of a bare 500."""
    return error_response(500, "TRIAGE_FAILED", str(error))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": get_orchestrator().llm_provider.name}
