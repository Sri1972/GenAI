"""
SDK Client — shared Anthropic client for all agents.

Primary:  LiteLLM proxy via Anthropic SDK (same transport as legacy llm.py)
Fallback: AWS Bedrock via AnthropicBedrock + streaming (activated when LiteLLM is down)

Once fallback is activated, all subsequent calls go directly to Bedrock
(same sticky-fallback behavior as the legacy code).
"""

import json
import os
import logging
import threading
import time as _time
from pathlib import Path

import httpx
from anthropic import Anthropic, AnthropicBedrock
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

# Primary: LiteLLM
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "")
LITELLM_TIMEOUT = int(os.environ.get("LITELLM_TIMEOUT", "600"))
MODEL_ID = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

# Fallback: Bedrock (same config as legacy llm.py)
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/ighsdreux5fs",
)
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_PROFILE = os.environ.get("AWS_PROFILE", "default")

MAX_TOOL_ROUNDS = 10
MAX_RETRIES = 3

# ── Token tracking ───────────────────────────────────────────────────────────
import token_tracker

_litellm_client = None
_bedrock_client = None
_using_fallback = False

# Module-level progress callback — set by the orchestrator before each stage
_progress_fn = None


def set_progress(fn):
    """Set the progress callback for heartbeat messages."""
    global _progress_fn
    _progress_fn = fn


def _get_ssl_context():
    """Reuse SSL setup from llm.py — loads the LiteLLM corporate cert."""
    from agents.llm import _get_ssl_context as _legacy_ssl
    return _legacy_ssl()


def _get_litellm_client() -> Anthropic:
    """Lazy-init Anthropic client pointed at LiteLLM proxy."""
    global _litellm_client
    if _litellm_client is None:
        _litellm_client = Anthropic(
            api_key=LITELLM_API_KEY,
            base_url=LITELLM_API_BASE,
            http_client=httpx.Client(
                verify=_get_ssl_context(),
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=float(LITELLM_TIMEOUT),
                    write=60.0,
                    pool=30.0,
                ),
            ),
        )
    return _litellm_client


def _get_bedrock_client() -> AnthropicBedrock:
    """Lazy-init Bedrock client (same setup as legacy llm.py)."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = AnthropicBedrock(
            aws_profile=BEDROCK_PROFILE,
            aws_region=BEDROCK_REGION,
            http_client=httpx.Client(
                verify=_get_ssl_context(),
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=float(LITELLM_TIMEOUT),
                    write=60.0,
                    pool=30.0,
                ),
            ),
        )
    return _bedrock_client


# ── Retryable errors ─────────────────────────────────────────────────────────
from anthropic import InternalServerError, APITimeoutError, APIConnectionError

_RETRYABLE = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
    InternalServerError,
    APITimeoutError,
    APIConnectionError,
)


class _Heartbeat:
    """Emits periodic progress messages during long-running LLM calls."""

    def __init__(self, interval: int = 30):
        self._interval = interval
        self._start = _time.time()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.wait(self._interval):
            elapsed = int(_time.time() - self._start)
            msg = f"crew:    ...still generating ({elapsed}s elapsed)"
            if _progress_fn:
                _progress_fn(msg)
            else:
                print(f"    ...still generating ({elapsed}s elapsed)", flush=True)


def _call_litellm(kwargs: dict) -> object:
    """Call LiteLLM with streaming to avoid gateway timeouts on large responses."""
    client = _get_litellm_client()
    heartbeat = _Heartbeat(interval=30)
    heartbeat.start()
    try:
        with client.messages.stream(**kwargs) as stream:
            return stream.get_final_message()
    finally:
        heartbeat.stop()


def _call_bedrock_streaming(kwargs: dict) -> object:
    """
    Call Bedrock via streaming (same approach as legacy llm.py).
    Streaming avoids read timeouts on large responses.
    """
    client = _get_bedrock_client()
    bedrock_kwargs = {
        "model": BEDROCK_MODEL_ID,
        "max_tokens": kwargs["max_tokens"],
        "messages": kwargs["messages"],
    }
    if "system" in kwargs:
        bedrock_kwargs["system"] = kwargs["system"]
    if "tools" in kwargs:
        bedrock_kwargs["tools"] = kwargs["tools"]

    heartbeat = _Heartbeat(interval=30)
    heartbeat.start()
    try:
        with client.messages.stream(**bedrock_kwargs) as stream:
            response = stream.get_final_message()
    finally:
        heartbeat.stop()
    return response


def _call_with_fallback(kwargs: dict) -> object:
    """
    Try LiteLLM with retries, fall back to Bedrock if unavailable.
    Once fallback is activated, all subsequent calls go to Bedrock.
    """
    global _using_fallback, _litellm_client

    if _using_fallback:
        return _call_bedrock_streaming(kwargs)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return _call_litellm(kwargs)
        except _RETRYABLE as e:
            last_error = e
            _litellm_client = None  # reset client on connection issues
            if attempt < MAX_RETRIES - 1:
                wait = 3 * (attempt + 1)
                print(
                    f"[sdk_client] LiteLLM failed ({type(e).__name__}), "
                    f"retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})...",
                    flush=True,
                )
                _time.sleep(wait)
            else:
                _using_fallback = True
                print(
                    f"\n{'='*60}\n"
                    f"[SDK FALLBACK] LiteLLM proxy unavailable after {MAX_RETRIES} retries.\n"
                    f"               Switching to AWS Bedrock ({BEDROCK_MODEL_ID}).\n"
                    f"               Last error: {last_error}\n"
                    f"{'='*60}\n",
                    flush=True,
                )

    # Bedrock fallback
    try:
        return _call_bedrock_streaming(kwargs)
    except Exception as bedrock_err:
        raise RuntimeError(
            f"Both LiteLLM and Bedrock failed.\n"
            f"  LiteLLM error: {last_error}\n"
            f"  Bedrock error: {bedrock_err}"
        ) from bedrock_err


def run_agent(
    system: str,
    messages: list[dict],
    tools: list | None = None,
    output_schema: dict | None = None,
    max_tokens: int = 32000,
    model: str | None = None,
) -> dict | str:
    """
    Unified agent runner — replaces chat() and chat_json() from llm.py.

    If output_schema is provided → returns a validated dict (structured output).
    If tools are provided → runs a manual tool-use loop.
    Otherwise → simple call, returns text.

    Tools should be a list of ToolDef objects (from sdk_tools.py) — each has
    .schema (the JSON dict for the API) and .fn (the callable to execute).
    """
    effective_model = model or MODEL_ID

    # Convert ToolDef objects to API schema format
    tool_schemas = [t.schema for t in tools] if tools else None
    tool_map = {t.schema["name"]: t.fn for t in tools} if tools else {}

    # When structured output is needed, inject a short JSON instruction into the
    # system prompt (LiteLLM proxy strips output_config). Keep this minimal to
    # avoid inflating input tokens — the prompt itself already describes the shape.
    effective_system = system
    if output_schema:
        effective_system = (
            system
            + "\n\nIMPORTANT: Respond with ONLY valid JSON. "
            + "No markdown fences, no explanation, no emojis, no text before or after the JSON."
        )

    kwargs = {
        "model": effective_model,
        "max_tokens": max_tokens,
        "system": effective_system,
        "messages": list(messages),
    }

    if tool_schemas:
        kwargs["tools"] = tool_schemas

    total_input_tokens = 0
    total_output_tokens = 0

    # ── Tool-use loop ────────────────────────────────────────────────────────
    for _round in range(MAX_TOOL_ROUNDS):
        response = _call_with_fallback(kwargs)

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            break

        # Execute each tool_use block
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                fn = tool_map.get(block.name)
                if fn:
                    try:
                        result = fn(**block.input)
                    except Exception as e:
                        result = f"Tool error: {e}"
                        logger.warning(f"Tool '{block.name}' raised: {e}")
                else:
                    result = f"Unknown tool: {block.name}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        # Append assistant response + tool results for next iteration
        kwargs["messages"].append({"role": "assistant", "content": response.content})
        kwargs["messages"].append({"role": "user", "content": tool_results})
    else:
        logger.warning(f"Tool loop hit max rounds ({MAX_TOOL_ROUNDS})")

    # ── Record token usage ───────────────────────────────────────────────────
    run_id = token_tracker.get_run_id()
    token_tracker.record(run_id, total_input_tokens, total_output_tokens)

    # ── Extract result ───────────────────────────────────────────────────────
    for block in reversed(response.content):
        if block.type != "text":
            continue
        text = getattr(block, "text", "") or ""
        text = text.strip()
        if not text:
            continue

        if output_schema:
            return _extract_json(text)
        return text

    logger.error(f"No text block in response. Blocks: {[b.type for b in response.content]}")
    return ""


def _extract_json(text: str) -> dict:
    """
    Extract JSON from model response — handles fences, preamble, and trailing text.
    Same robustness as legacy chat_json() but simpler (no retry loop needed).
    """
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    if "```" in text:
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Find first { to last } (the JSON object may have preamble/trailing text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract JSON from response (length={len(text)}). "
        f"First 200 chars: {text[:200]}"
    )
