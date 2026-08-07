"""
LLM Client — Connects to S&P Global's LiteLLM proxy.
"""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = os.getenv("LITELLM_API_BASE")
API_KEY = os.getenv("LITELLM_API_KEY")
TIMEOUT = int(os.getenv("LITELLM_TIMEOUT", "120"))

DEFAULT_MODEL = os.getenv("LITELLM_SONNET_45_MODEL", "claude-sonnet-4-5")


def get_openai_client() -> OpenAI:
    """Create an OpenAI client configured for the LiteLLM proxy."""
    http_client = httpx.Client(
        verify=False,
        timeout=TIMEOUT,
    )

    return OpenAI(
        api_key=API_KEY,
        base_url=f"{API_BASE}/v1",
        http_client=http_client,
    )


def chat_completion(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send a chat completion request through the LiteLLM proxy."""
    client = get_openai_client()

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )

    return response.choices[0].message.content
