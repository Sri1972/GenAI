"""
LLM client — LiteLLM proxy (primary) with AWS Bedrock fallback.
All LLM calls in TurboUIGen flow through chat() / chat_json() here.
"""

import json
import os
import ssl
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI, InternalServerError, APIStatusError, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ── Primary: LiteLLM proxy ───────────────────────────────────────────────────
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "")
LITELLM_API_KEY  = os.environ.get("LITELLM_API_KEY", "")
LITELLM_SSL_CERT = os.environ.get("LITELLM_SSL_CERT", "")
LITELLM_TIMEOUT  = int(os.environ.get("LITELLM_TIMEOUT", "600"))
MODEL_ID         = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

# ── Fallback: AWS Bedrock ────────────────────────────────────────────────────
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/ighsdreux5fs",
)
BEDROCK_REGION   = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_PROFILE  = os.environ.get("AWS_PROFILE", "default")

_client: Optional[OpenAI] = None
_bedrock_client = None
_using_fallback = False  # tracks whether we've switched to Bedrock this session

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


def _get_bedrock_client():
    """Lazy-init Bedrock client using the anthropic SDK's native Bedrock support."""
    global _bedrock_client
    if _bedrock_client is None:
        from anthropic import AnthropicBedrock
        _bedrock_client = AnthropicBedrock(
            aws_profile=BEDROCK_PROFILE,
            aws_region=BEDROCK_REGION,
            timeout=httpx.Timeout(
                connect=30.0,
                read=float(LITELLM_TIMEOUT),
                write=60.0,
                pool=30.0,
            ),
        )
    return _bedrock_client


def _call_bedrock(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 32000,
    json_mode: bool = False,
) -> str:
    """Call Claude on Bedrock via the Anthropic SDK (streaming to avoid timeouts)."""
    client = _get_bedrock_client()

    system_content = system
    if json_mode and system:
        system_content = system + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no explanation."
    elif json_mode:
        system_content = "Respond with ONLY valid JSON. No markdown, no explanation."

    # Convert OpenAI-style messages to Anthropic format
    anthropic_messages = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            system_content = (system_content + "\n\n" + msg["content"]) if system_content else msg["content"]
            continue
        content = msg["content"]
        if isinstance(content, str):
            anthropic_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append({"type": "text", "text": item})
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"type": "text", "text": item["text"]})
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:image/png;base64,"):
                            b64_data = url.split(",", 1)[1]
                            parts.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64_data,
                                },
                            })
            anthropic_messages.append({"role": role, "content": parts})

    kwargs = {
        "model": BEDROCK_MODEL_ID,
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
    }
    if system_content:
        kwargs["system"] = system_content

    # Use streaming to avoid read timeouts on large responses
    chunks = []
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            chunks.append(text)

    # Get final message for usage stats
    response = stream.get_final_message()
    run_id = _get_current_run_id()
    _record_usage(
        run_id,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    return "".join(chunks)


def chat(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 32000,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """
    Call Claude via LiteLLM proxy (primary) with Bedrock fallback.
    Falls back to Bedrock if LiteLLM is unavailable after retries.
    Once fallback is activated, all subsequent calls go directly to Bedrock.
    """
    global _using_fallback, _client
    if _using_fallback:
        return _call_bedrock(messages, system=system, max_tokens=max_tokens, json_mode=json_mode)

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
        InternalServerError,
        APIConnectionError,
        APITimeoutError,
    )

    max_retries = 3
    last_error = None
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
            last_error = e
            _client = None
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                print(f"[llm.chat] LiteLLM failed ({type(e).__name__}), retrying in {wait}s (attempt {attempt+1}/{max_retries})...", flush=True)
                _time.sleep(wait)
                client = _get_client()
            else:
                _using_fallback = True
                print(
                    f"\n{'='*60}\n"
                    f"[FALLBACK] LiteLLM proxy unavailable after {max_retries} retries.\n"
                    f"           Switching to AWS Bedrock ({BEDROCK_MODEL_ID}).\n"
                    f"           Last error: {last_error}\n"
                    f"{'='*60}\n",
                    flush=True,
                )

    # ── Fallback to Bedrock ──────────────────────────────────────────────────
    try:
        return _call_bedrock(messages, system=system, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as bedrock_err:
        raise RuntimeError(
            f"Both LiteLLM and Bedrock failed.\n"
            f"  LiteLLM error: {last_error}\n"
            f"  Bedrock error: {bedrock_err}"
        ) from bedrock_err


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
                is_truncation = (
                    "Unterminated string" in str(e)
                    or "Expecting" in str(e)
                    or len(text) > max_tokens * 2
                )
                if is_truncation:
                    print("[chat_json] detected truncated JSON — asking model to continue", flush=True)
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
                        json_mode=False,
                    ).strip()
                    if not continuation:
                        print("[chat_json] continuation returned empty — raising for two-pass fallback", flush=True)
                        raise RuntimeError(
                            f"Model response truncated and continuation was empty "
                            f"(likely context-window overflow). Switching to two-pass generation."
                        ) from e
                    merged = text + continuation
                    if merged.rstrip().endswith("```"):
                        merged = merged.rstrip()[:-3].rstrip()
                    try:
                        return json.loads(merged)
                    except json.JSONDecodeError as e2:
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
