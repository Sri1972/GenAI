"""
LLM Client for Product Forge — Connects to S&P Global's LiteLLM proxy.
Supports both blocking and streaming completions with token cost tracking.

Two-tier model strategy:
- DRAFT_MODEL (Haiku): Used for discussion rounds — fast and cheap
- ARTIFACT_MODEL (Sonnet): Used for final artifact generation — higher quality
"""

import os
from pathlib import Path
from typing import Generator

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

API_BASE = os.getenv("LITELLM_API_BASE")
API_KEY = os.getenv("LITELLM_API_KEY")
TIMEOUT = int(os.getenv("LITELLM_TIMEOUT", "300"))

DRAFT_MODEL = os.getenv("LITELLM_HAIKU_MODEL", "claude-haiku-4-5")
ARTIFACT_MODEL = os.getenv("LITELLM_SONNET_45_MODEL", "claude-sonnet-4-5")

# Cost per 1M tokens (USD) — adjust based on your LiteLLM proxy pricing
MODEL_COSTS = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
}

DEFAULT_MAX_TOKENS_DISCUSSION = 4096
DEFAULT_MAX_TOKENS_ARTIFACT = 16384


def get_openai_client() -> OpenAI:
    http_client = httpx.Client(verify=False, timeout=TIMEOUT)
    return OpenAI(
        api_key=API_KEY,
        base_url=f"{API_BASE}/v1",
        http_client=http_client,
    )


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = MODEL_COSTS.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * costs["input"] / 1_000_000) + (output_tokens * costs["output"] / 1_000_000)


def chat_completion(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 4096,
) -> str:
    client = get_openai_client()
    resolved_model = model or ARTIFACT_MODEL
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=resolved_model,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content


def chat_completion_stream(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Stream chat completion tokens as they arrive."""
    client = get_openai_client()
    resolved_model = model or ARTIFACT_MODEL
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    stream = client.chat.completions.create(
        model=resolved_model,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_completion_with_usage(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict:
    """Returns response text plus token usage and cost."""
    client = get_openai_client()
    resolved_model = model or ARTIFACT_MODEL
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=resolved_model,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    cost = calculate_cost(resolved_model, input_tokens, output_tokens)
    return {
        "content": response.choices[0].message.content,
        "model": resolved_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
    }


def chat_completion_stream_with_usage(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 4096,
) -> tuple[Generator[str, None, None], dict]:
    """Stream tokens and collect usage stats. Returns (generator, usage_ref).

    usage_ref is a mutable dict that gets populated after the stream completes.
    Access usage_ref['input_tokens'], ['output_tokens'], ['cost_usd'] after consuming the generator.
    """
    client = get_openai_client()
    resolved_model = model or ARTIFACT_MODEL
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    usage_ref = {"model": resolved_model, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    def _stream():
        try:
            stream = client.chat.completions.create(
                model=resolved_model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception:
            stream = client.chat.completions.create(
                model=resolved_model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True,
            )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if hasattr(chunk, 'usage') and chunk.usage:
                usage_ref["input_tokens"] = getattr(chunk.usage, 'prompt_tokens', 0) or 0
                usage_ref["output_tokens"] = getattr(chunk.usage, 'completion_tokens', 0) or 0
                usage_ref["cost_usd"] = calculate_cost(
                    resolved_model, usage_ref["input_tokens"], usage_ref["output_tokens"]
                )

    return _stream(), usage_ref
