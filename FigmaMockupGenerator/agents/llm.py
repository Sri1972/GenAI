"""
LLM client — LiteLLM proxy (OpenAI-compatible)
Provides a drop-in replacement for the AWS Bedrock client used throughout TurboUIGen.
"""

import json
import os
import ssl
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "")
LITELLM_API_KEY  = os.environ.get("LITELLM_API_KEY", "")
LITELLM_SSL_CERT = os.environ.get("LITELLM_SSL_CERT", "")
LITELLM_TIMEOUT  = int(os.environ.get("LITELLM_TIMEOUT", "120"))
MODEL_ID         = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

_client: Optional[OpenAI] = None


def _get_ssl_context() -> ssl.SSLContext:
    """Return an SSL context with the system CA store + LiteLLM certificate."""
    ctx = ssl.create_default_context()
    if LITELLM_SSL_CERT:
        cert_content = LITELLM_SSL_CERT.replace("\\n", "\n")
        ctx.load_verify_locations(cadata=cert_content)
    return ctx


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        http_client = httpx.Client(
            verify=_get_ssl_context(),
            timeout=httpx.Timeout(LITELLM_TIMEOUT),
        )
        base_url = LITELLM_API_BASE.rstrip("/") + "/v1"
        _client = OpenAI(
            base_url=base_url,
            api_key=LITELLM_API_KEY,
            http_client=http_client,
        )
    return _client


def chat(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 32000,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """
    Call Claude via LiteLLM proxy and return the text response.

    Args:
        messages:    List of {"role": "user"|"assistant", "content": str|list}
        system:      System prompt string
        max_tokens:  Max completion tokens
        temperature: Sampling temperature (kept for call-site compatibility)
        json_mode:   If True, instructs Claude to return valid JSON only

    Returns:
        Response text string
    """
    client = _get_client()

    # Build system prompt
    system_content = system
    if json_mode and system:
        system_content = system + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no explanation."
    elif json_mode:
        system_content = "Respond with ONLY valid JSON. No markdown, no explanation."

    # Prepend system message if provided
    full_messages: list[dict] = []
    if system_content:
        full_messages.append({"role": "system", "content": system_content})
    full_messages.extend(messages)

    response = _get_client().chat.completions.create(
        model=MODEL_ID,
        max_tokens=max_tokens,
        messages=full_messages,
    )

    return response.choices[0].message.content or ""


def chat_json(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 32000,
    temperature: float = 0.1,
) -> dict:
    """Call Claude and parse the response as JSON. Raises on invalid JSON."""
    text = chat(messages, system=system, max_tokens=max_tokens,
                temperature=temperature, json_mode=True)
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def model_id() -> str:
    return MODEL_ID


def build_vision_message(text: str, images_b64: list[str]) -> list[dict]:
    """
    Build a user message with text + images for Claude's vision API (OpenAI format).
    images_b64: list of base64-encoded PNG strings
    """
    content: list[dict] = []
    if text:
        content.append({"type": "text", "text": text})
    for b64 in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
            },
        })
    return [{"role": "user", "content": content}]
