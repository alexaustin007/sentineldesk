"""Send one tiny request to each model tier to confirm the LLM setup works.

    python -m sentineldesk.check_llm

It prints the provider, then the model, latency, tokens, and estimated cost for the
fast tier (Flash-Lite) and the deep tier (Flash).
"""

from sentineldesk.llm import LLMRequest, LLMUnavailableError, create_llm_provider


def main() -> None:
    provider = create_llm_provider()
    print(f"Provider: {provider.name}")
    for tier in ("fast", "deep"):
        request = LLMRequest(
            task="connectivity_check",
            tier=tier,
            system_prompt="Reply with one short sentence.",
            user_prompt="Say hello from SentinelDesk.",
        )
        try:
            response = provider.generate(request)
        except LLMUnavailableError as error:
            print(f"{tier}: FAILED. {error}")
            continue
        record = response.record
        print(
            f"{tier}: {record.model} answered in {record.latency_ms:.0f} ms "
            f"({record.input_tokens} in / {record.output_tokens} out tokens, "
            f"about ${record.estimated_cost_usd:.6f}): {response.text.strip()[:80]}"
        )


if __name__ == "__main__":
    main()
