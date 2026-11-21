"""Provider-agnostic LLM access with usage, latency, and cost tracking.

Two tiers keep compute proportional to risk:
- "fast": Gemini Flash-Lite drafts routine replies.
- "deep": Gemini Flash runs the adversarial review, complex drafts, and attachments.

Model names and prices come from environment variables, so they can change without
code edits. Without an API key, `create_llm_provider` returns the offline mock.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from sentineldesk.schemas import Attachment, LLMCallRecord

ModelTier = Literal["fast", "deep"]


@dataclass(frozen=True)
class ModelSettings:
    model_name: str
    input_price_per_million: float
    output_price_per_million: float

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_price_per_million
            + output_tokens * self.output_price_per_million
        ) / 1_000_000


def load_model_settings() -> dict[str, ModelSettings]:
    """Read model names and USD prices per million tokens from the environment.

    Defaults follow the Gemini models and pricing pages as of 2026-11-21.
    Check them before quoting cost numbers.
    """
    return {
        "fast": ModelSettings(
            model_name=os.getenv("SENTINEL_FAST_MODEL", "gemini-3.5-flash-lite"),
            input_price_per_million=float(
                os.getenv("SENTINEL_FAST_INPUT_PRICE", "0.30")
            ),
            output_price_per_million=float(
                os.getenv("SENTINEL_FAST_OUTPUT_PRICE", "2.50")
            ),
        ),
        "deep": ModelSettings(
            model_name=os.getenv("SENTINEL_DEEP_MODEL", "gemini-3.8-flash"),
            input_price_per_million=float(
                os.getenv("SENTINEL_DEEP_INPUT_PRICE", "0.75")
            ),
            output_price_per_million=float(
                os.getenv("SENTINEL_DEEP_OUTPUT_PRICE", "3.75")
            ),
        ),
    }


@dataclass(frozen=True)
class LLMRequest:
    task: str
    tier: ModelTier
    system_prompt: str
    user_prompt: str
    # Ask for JSON that matches this schema (used by the adversarial review).
    response_schema: type[BaseModel] | None = None
    attachments: tuple[Attachment, ...] = ()
    # Structured inputs behind the prompt. The mock provider builds answers from them.
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    record: LLMCallRecord


class LLMUnavailableError(RuntimeError):
    """The provider could not return a usable answer. Callers must not auto-approve."""


class LLMProvider(Protocol):
    name: str

    def generate(self, request: LLMRequest) -> LLMResponse: ...


class GeminiProvider:
    """Gemini through the official Google Gen AI SDK (`google-genai`)."""

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        settings: dict[str, ModelSettings] | None = None,
    ) -> None:
        from google import genai  # imported here so mock mode works without the SDK

        self._client = genai.Client(api_key=api_key)
        self._settings = settings or load_model_settings()

    def generate(self, request: LLMRequest) -> LLMResponse:
        from google.genai import types

        settings = self._settings[request.tier]
        config = types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            response_mime_type="application/json" if request.response_schema else None,
            response_schema=request.response_schema,
        )
        contents: list[types.Part | str] = [
            types.Part.from_bytes(data=attachment.data, mime_type=attachment.mime_type)
            for attachment in request.attachments
        ]
        contents.append(request.user_prompt)

        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=settings.model_name, contents=contents, config=config
            )
        except Exception as error:  # any provider failure means the step did not run
            raise LLMUnavailableError(f"Gemini call failed: {error}") from error
        latency_ms = (time.perf_counter() - started) * 1000

        if not response.text:
            raise LLMUnavailableError(
                "Gemini returned no text (it may have been blocked)."
            )
        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        # Thinking tokens are billed as output tokens.
        output_tokens = (
            (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
            if usage
            else 0
        )
        return LLMResponse(
            text=response.text,
            record=LLMCallRecord(
                task=request.task,
                tier=request.tier,
                model=settings.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=settings.estimate_cost(input_tokens, output_tokens),
            ),
        )


class MockLLMProvider:
    """Offline stand-in with deterministic answers and the same usage records.

    Token counts are estimated from text length, and costs use the configured
    prices, so the console shows roughly what the real call would cost.
    """

    name = "mock"

    def __init__(
        self,
        responder: Callable[[LLMRequest], str] | None = None,
        settings: dict[str, ModelSettings] | None = None,
    ) -> None:
        self._responder = responder or default_mock_responder
        self._settings = settings or load_model_settings()

    def generate(self, request: LLMRequest) -> LLMResponse:
        settings = self._settings[request.tier]
        started = time.perf_counter()
        text = self._responder(request)
        latency_ms = (time.perf_counter() - started) * 1000
        input_tokens = estimate_tokens(request.system_prompt + request.user_prompt)
        output_tokens = estimate_tokens(text)
        return LLMResponse(
            text=text,
            record=LLMCallRecord(
                task=request.task,
                tier=request.tier,
                model=f"mock/{settings.model_name}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=settings.estimate_cost(input_tokens, output_tokens),
            ),
        )


def create_llm_provider() -> LLMProvider:
    """Gemini when GEMINI_API_KEY (or GOOGLE_API_KEY) is set, otherwise the mock.

    Set SENTINEL_LLM_PROVIDER to "mock" or "gemini" to force a choice.
    """
    choice = os.getenv("SENTINEL_LLM_PROVIDER", "auto").lower()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if choice == "mock" or (choice == "auto" and not api_key):
        return MockLLMProvider()
    if choice in {"auto", "gemini"}:
        return GeminiProvider(api_key=api_key)
    raise ValueError(
        f"Unknown SENTINEL_LLM_PROVIDER '{choice}'. Use auto, gemini, or mock."
    )


def estimate_tokens(text: str) -> int:
    """Rough token count, about four characters per token."""
    return max(1, len(text) // 4)


def default_mock_responder(request: LLMRequest) -> str:
    """Build a plausible offline answer from the request context."""
    if request.task == "adversarial_review":
        return _mock_review(request.context)
    if request.task == "draft_reply":
        return _mock_reply(request.context)
    return ""


def _mock_review(context: dict[str, Any]) -> str:
    """Agree with the proposed labels; escalate only on outage, security, or data loss."""
    labels = dict(context.get("proposed_labels", {}))
    risk_signals = list(context.get("risk_signals", []))
    severe_signals = {"service outage", "security incident", "data loss"} & set(
        risk_signals
    )
    if severe_signals:
        labels["priority"] = context.get("highest_priority", labels.get("priority"))
    return json.dumps(
        {
            **labels,
            "escalate": bool(severe_signals),
            "findings": [f"Risk signal: {signal}" for signal in risk_signals],
            "rationale": "Mock review: escalates only on outage, security, or data-loss signals.",
        }
    )


def _mock_reply(context: dict[str, Any]) -> str:
    """Template reply that reuses the top precedent's resolution and cites it."""
    citation = context.get("top_ticket_id", "")
    sentences = re.split(r"(?<=[.!?])\s+", str(context.get("top_answer", "")).strip())
    resolution = " ".join(sentences[:2])
    if context.get("language") == "de":
        return (
            f"Hallo,\n\nvielen Dank für Ihre Nachricht. {resolution} [{citation}]\n\n"
            "Falls das Problem weiterhin besteht, antworten Sie bitte auf diese Nachricht.\n\n"
            "Mit freundlichen Grüßen\nIhr SentinelDesk-Support"
        )
    return (
        f"Hello,\n\nThank you for contacting us. {resolution} [{citation}]\n\n"
        "If the issue persists, please reply to this message and we will follow up.\n\n"
        "Best regards,\nSentinelDesk Support"
    )
