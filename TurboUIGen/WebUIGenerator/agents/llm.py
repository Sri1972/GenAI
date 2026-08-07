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
LITELLM_TIMEOUT  = int(os.environ.get("LITELLM_TIMEOUT", "600"))
MODEL_ID         = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

_client: Optional[OpenAI] = None

# ── Token usage tracking (delegated to shared token_tracker module) ───────────
import token_tracker


def reset_usage(run_id: str = "default") -> None:
    token_tracker.reset(run_id)


def get_usage(run_id: str = "default") -> dict:
    return token_tracker.get(run_id)


def _record_usage(run_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    token_tracker.record(run_id, prompt_tokens, completion_tokens)


def set_current_run_id(run_id: str) -> None:
    token_tracker.set_run_id(run_id)


def _get_current_run_id() -> str:
    return token_tracker.get_run_id()


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
            timeout=httpx.Timeout(
                connect=30.0,
                read=float(LITELLM_TIMEOUT),
                write=60.0,
                pool=30.0,
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=120,
            ),
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
    temperature: float = 0.2,  # kept for call-site compatibility, not sent to Claude 4+
    json_mode: bool = False,
) -> str:
    """
    Call Claude via LiteLLM proxy and return the text response.

    Args:
        messages:    List of {"role": "user"|"assistant", "content": str|list}
        system:      System prompt string
        max_tokens:  Max completion tokens
        temperature: Kept for call-site compatibility
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

    import time as _time

    _RETRYABLE = (
        httpx.RemoteProtocolError,
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.CloseError,
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            stream = client.chat.completions.create(
                model=MODEL_ID,
                max_tokens=max_tokens,
                messages=full_messages,
                stream=True,
                stream_options={"include_usage": True},
            )

            chunks = []
            usage_data = None
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_data = chunk.usage

            # Record token usage
            run_id = _get_current_run_id()
            if usage_data:
                _record_usage(
                    run_id,
                    getattr(usage_data, "prompt_tokens", 0),
                    getattr(usage_data, "completion_tokens", 0),
                )
            else:
                est_input = sum(len(str(m.get("content", ""))) for m in full_messages) // 4
                est_output = sum(len(c) for c in chunks) // 4
                _record_usage(run_id, est_input, est_output)

            return "".join(chunks)

        except _RETRYABLE as e:
            # Reset the client to force a fresh connection on retry
            global _client
            _client = None
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                print(f"[llm.chat] Stream interrupted ({type(e).__name__}), retrying in {wait}s (attempt {attempt+1}/{max_retries})...", flush=True)
                _time.sleep(wait)
                client = _get_client()
            else:
                raise RuntimeError(
                    f"LLM stream failed after {max_retries} attempts: {e}. "
                    "The LiteLLM proxy may be overloaded or the request is too large."
                ) from e


def chat_json(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 64000,
    temperature: float = 0.1,
) -> dict:
    """Call Claude and parse the response as JSON. Retries once on truncation/parse failure."""
    for attempt in range(2):
        text = chat(messages, system=system, max_tokens=max_tokens,
                    temperature=temperature, json_mode=True)
        text = text.strip()
        if not text:
            print(f"[chat_json] attempt {attempt+1}: empty response from model", flush=True)
            if attempt == 0:
                continue
            raise RuntimeError(
                "Model returned an empty response. The request may be too large "
                "or the context window was exceeded. Try breaking the request into smaller steps."
            )
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try fixing invalid escape sequences (LLM often writes \' or bare \n in strings)
            if "Invalid \\escape" in str(e) or "invalid escape" in str(e).lower():
                import re as _re_esc
                fixed_text = _re_esc.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
                try:
                    return json.loads(fixed_text)
                except json.JSONDecodeError:
                    pass  # fall through to normal retry logic
            print(f"[chat_json] attempt {attempt+1}: JSON parse error: {e}", flush=True)
            print(f"[chat_json] raw response (first 500 chars): {text[:500]}", flush=True)
            if attempt == 0:
                # Detect truncation (response ends mid-string) vs other parse errors.
                # Truncation: the model hit max_tokens mid-response.
                # Strategy: send the truncated text back as the assistant turn and ask
                # the model to complete the JSON from exactly where it stopped.
                is_truncation = (
                    "Unterminated string" in str(e)
                    or "Expecting" in str(e)
                    or len(text) > max_tokens * 2  # rough heuristic
                )
                if is_truncation:
                    print("[chat_json] detected truncated JSON — asking model to continue", flush=True)
                    # Guard: if the truncated text is already very large (>100k chars),
                    # sending it back as context will exceed Bedrock's input limit and return
                    # an empty response.  In that case, skip the continuation attempt and
                    # let the caller's two-pass fallback handle it.
                    if len(text) > 100_000:
                        print(
                            f"[chat_json] truncated text too large ({len(text)} chars) for continuation — "
                            "raising so caller can use two-pass generation",
                            flush=True,
                        )
                        raise RuntimeError(
                            f"Model response truncated (response was {len(text):,} chars, too large to repair). "
                            "Switching to two-pass generation."
                        ) from e

                    continuation_messages = messages + [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": (
                            "Your response was cut off mid-way through the JSON. "
                            "Continue the JSON from EXACTLY where you stopped — "
                            "do NOT restart, do NOT repeat any part already written. "
                            "Output ONLY the continuation (the remaining JSON text). "
                            "No explanation, no markdown fences."
                        )},
                    ]
                    continuation = chat(
                        continuation_messages,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=False,  # continuation is raw text, not a fresh JSON call
                    ).strip()
                    if not continuation:
                        print("[chat_json] continuation returned empty — raising for two-pass fallback", flush=True)
                        raise RuntimeError(
                            f"Model response truncated and continuation was empty "
                            f"(likely context-window overflow). Switching to two-pass generation."
                        ) from e
                    merged = text + continuation
                    # Strip any trailing markdown fence the model may have added
                    if merged.rstrip().endswith("```"):
                        merged = merged.rstrip()[:-3].rstrip()
                    try:
                        return json.loads(merged)
                    except json.JSONDecodeError as e2:
                        # Try fixing invalid escape sequences in merged text
                        if "Invalid \\escape" in str(e2) or "invalid escape" in str(e2).lower():
                            import re as _re_esc2
                            fixed_merged = _re_esc2.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', merged)
                            try:
                                return json.loads(fixed_merged)
                            except json.JSONDecodeError:
                                pass
                        print(f"[chat_json] merged continuation still invalid: {e2}", flush=True)
                        raise RuntimeError(
                            f"Model response truncated and continuation did not repair the JSON. "
                            f"Last error: {e2}. Switching to two-pass generation."
                        ) from e2
                else:
                    # Not truncation — ask model to re-emit valid JSON
                    messages = messages + [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": (
                            "Your previous response was not valid JSON. "
                            "Return ONLY a valid JSON object with key 'files'. No explanation, no markdown."
                        )},
                    ]
                    continue
            raise RuntimeError(
                f"Model returned invalid JSON after 2 attempts. Last error: {e}\n"
                f"Response started with: {text[:200]}"
            ) from e
    raise RuntimeError("chat_json: exhausted retries")


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
