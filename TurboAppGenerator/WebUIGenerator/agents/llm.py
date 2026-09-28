"""
LLM client — LiteLLM proxy (primary) with AWS Bedrock fallback.
All LLM calls in TurboUIGen flow through chat() / chat_json() here.
"""

import json
import os
import ssl
import tempfile
import time
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
    "CLAUDE_SONNET_5_MODEL_ID",
    os.environ.get(
        "BEDROCK_MODEL_ID",
        "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/oonx9pzz8l4h",
    ),
)
BEDROCK_REGION   = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_PROFILE  = os.environ.get("AWS_PROFILE", "default")
# Its OWN env var, not a reuse of LITELLM_TIMEOUT: Bedrock is the fallback for
# exactly the case where the primary path is struggling, so it needs at least
# as much patience, not whatever short value LiteLLM happens to be tuned to.
# Reusing LITELLM_TIMEOUT here meant a low LiteLLM value (e.g. 120s, sized for
# a fast proxy) silently capped Bedrock's read timeout too, making the fallback
# itself time out on large streamed responses before ever reporting LiteLLM's
# real failure reason.
BEDROCK_TIMEOUT  = int(os.environ.get("BEDROCK_TIMEOUT", "600"))

# ── Model choice list (header picker + anything else that needs "every model
# this platform is configured to offer") ────────────────────────────────────
# The single source of truth for this list — API/server.py's own /api/models
# route imports these two constants rather than keeping a second copy, and
# pick_cheapest_reachable_model() below ranks LITELLM_MODEL_CHOICES by price.
LITELLM_MODEL_CHOICES = [
    {"id": os.environ.get("LITELLM_HAIKU_MODEL", "claude-haiku-4-5"), "label": "Haiku 4.5 (cheapest)"},
    {"id": os.environ.get("LITELLM_SONNET_45_MODEL", "claude-sonnet-4-5"), "label": "Sonnet 4.5"},
    {"id": os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6"), "label": "Sonnet 4.6"},
    {"id": os.environ.get("LITELLM_SONNET_5_MODEL", "claude-sonnet-5"), "label": "Sonnet 5"},
]
BEDROCK_MODEL_CHOICES = [
    c for c in [
        {"id": os.environ.get("CLAUDE_SONNET_5_MODEL_ID", ""), "label": "Bedrock Sonnet 5"},
        {"id": os.environ.get("CLAUDE_MODEL_ID", ""), "label": "Bedrock (lower-cost)"},
    ] if c["id"]
]

_client: Optional[OpenAI] = None
_bedrock_client = None
_using_fallback = False  # tracks whether we've switched to Bedrock this session
# json_mode used to rely purely on a prompt instruction ("respond with ONLY valid
# JSON") with nothing enforcing it at the API level — the model could, and
# occasionally did, emit a complete valid JSON value and then keep going,
# producing "Extra data" json.loads failures downstream in chat_json(). Tracked
# module-wide (not per-call) so a single incompatible response only pays the
# discovery cost once per process, not on every subsequent call.
_json_response_format_supported = True
# response_format=json_object turned out not to actually fix the "valid JSON
# followed by stray trailing content" failure — it's a soft hint LiteLLM passes
# along, but Claude has no native strict-JSON decoding mode behind it the way
# OpenAI's own models do, so it barely changed anything in practice. Forcing a
# tool call instead constrains the response at the API/decoding level (the
# provider validates the call against the tool's schema), which is the actual
# reliable mechanism for Claude. Tracked module-wide for the same reason as
# _json_response_format_supported: pay the discovery cost once, not per call.
_tool_json_supported = True
_JSON_TOOL_NAME = "return_json_result"
_JSON_TOOL_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": True}

# Shared retryable-exception set for every LiteLLM call path (chat(),
# chat_stream_with_usage(), chat_with_tools()) — one definition instead of
# three copies that could silently drift apart.
_RETRYABLE_LITELLM_ERRORS = (
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

# ── Token usage tracking (delegated to shared token_tracker module) ───────────
import token_tracker


def reset_usage(run_id: str = "default") -> None:
    token_tracker.reset(run_id)


def get_usage(run_id: str = "default") -> dict:
    return token_tracker.get(run_id)


def _record_usage(run_id: str, prompt_tokens: int, completion_tokens: int, model: str | None = None) -> None:
    token_tracker.record(run_id, prompt_tokens, completion_tokens, model=model)


def set_current_run_id(run_id: str) -> None:
    token_tracker.set_run_id(run_id)


def _get_current_run_id() -> str:
    return token_tracker.get_run_id()


# ── Global model selection (header picker) ──────────────────────────────────
# Shared across every generator via a small JSON file, not an in-memory
# global — the picker's choice also needs to reach FigmaMockupGenerator's
# separate LLM client (figma_agent_shared.py), which lives in a different
# `agents`-named package this module can't safely cross-import (only
# WebUIGenerator "owns" that package name on sys.path — see
# WebAPIGenerator/api_config.py's docstring). A shared file sidesteps that
# entirely and mirrors how both modules already independently load the same
# .env file by relative path.
_SELECTION_FILE = Path(__file__).resolve().parent.parent.parent / ".model_selection.json"
_selection_cache = {"mtime": None, "provider": "litellm", "model": MODEL_ID}


def _read_selection() -> tuple[str, str]:
    """Current (provider, model) chosen in the header, cached by the file's
    mtime so normal calls don't hit disk on every request."""
    try:
        mtime = _SELECTION_FILE.stat().st_mtime
    except FileNotFoundError:
        return _selection_cache["provider"], _selection_cache["model"]
    if mtime != _selection_cache["mtime"]:
        try:
            data = json.loads(_SELECTION_FILE.read_text(encoding="utf-8"))
            _selection_cache["provider"] = data.get("provider", "litellm")
            _selection_cache["model"] = data.get("model", MODEL_ID)
            _selection_cache["mtime"] = mtime
        except Exception:
            pass
    return _selection_cache["provider"], _selection_cache["model"]


def set_selected_model(provider: str, model: str) -> None:
    """Called from the header's model picker (via API/server.py). Resets the
    sticky fallback flags AND the sticky JSON-capability flags so a
    freshly-chosen model gets a clean slate instead of inheriting whatever
    fallback/downgrade state a previous, less-capable model latched (e.g. a
    model that rejected tool-forced JSON leaving _tool_json_supported=False
    stuck for every later model too, even a fully-capable one)."""
    global _using_fallback, _stream_using_fallback, _tools_using_fallback
    global _tool_json_supported, _json_response_format_supported
    tmp = _SELECTION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"provider": provider, "model": model}), encoding="utf-8")
    os.replace(tmp, _SELECTION_FILE)
    _using_fallback = False
    _stream_using_fallback = False
    _tools_using_fallback = False
    _tool_json_supported = True
    _json_response_format_supported = True
    _selection_cache["mtime"] = None  # force re-read on next call


def get_selected_model() -> dict:
    provider, model = _read_selection()
    return {"provider": provider, "model": model}


def is_using_fallback() -> bool:
    return _using_fallback or _stream_using_fallback or _tools_using_fallback


def check_model_reachable(provider: str, model: str) -> tuple[bool, str]:
    """Real 1-token probe against the exact provider/model, bypassing the
    retry/fallback wrapper entirely — run right after a header selection so
    the UI can report a genuine yes/no instead of just accepting the pick."""
    try:
        if provider == "bedrock":
            client = _get_bedrock_client()
            client.messages.create(model=model, max_tokens=1, messages=[{"role": "user", "content": "hi"}])
        else:
            client = _get_client()
            client.chat.completions.create(model=model, max_tokens=1, messages=[{"role": "user", "content": "hi"}])
        return True, ""
    except Exception as e:
        return False, str(e)


_cheapest_model_cache: dict = {"ts": 0.0, "result": None}
_CHEAPEST_MODEL_CACHE_TTL = 120.0  # seconds


def pick_cheapest_reachable_model() -> dict | None:
    """Rank LITELLM_MODEL_CHOICES cheapest-first (using token_tracker's real
    per-model $/mtok rates) and return the first one that actually answers a
    live 1-token probe right now.

    Built for Product Forge's Draft Mode: rather than hardcoding "Haiku" —
    which silently goes stale the moment pricing changes, a cheaper model
    ships, or Haiku itself is down — this picks whatever is genuinely
    cheapest AND online at call time. Falls back to the cheapest candidate
    on the list (unprobed) if none answer, so a draft run can still proceed
    instead of blocking outright on a probe failure.

    Cached briefly (a Product Forge run makes ~20+ calls; probing before
    every single one would add real latency for no benefit).
    """
    now = time.time()
    cached = _cheapest_model_cache["result"]
    if cached and (now - _cheapest_model_cache["ts"]) < _CHEAPEST_MODEL_CACHE_TTL:
        return cached

    if not LITELLM_MODEL_CHOICES:
        return None
    ranked = sorted(LITELLM_MODEL_CHOICES, key=lambda c: sum(token_tracker.rate_for_model(c["id"])))

    chosen = None
    for c in ranked:
        ok, _ = check_model_reachable("litellm", c["id"])
        if ok:
            chosen = {"provider": "litellm", "model": c["id"], "label": c["label"]}
            break
    if chosen is None:
        c = ranked[0]
        chosen = {"provider": "litellm", "model": c["id"], "label": c["label"]}

    _cheapest_model_cache["ts"] = now
    _cheapest_model_cache["result"] = chosen
    return chosen


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
    """Lazy-init Bedrock client using the anthropic SDK's native Bedrock support.
    Cached for the process's lifetime -- AnthropicBedrock resolves AWS
    credentials once, at construction, and never re-checks disk for a
    refreshed SSO token on its own. _is_expired_credentials_error /
    _invalidate_bedrock_client below exist so a mid-session `aws sso login`
    can be picked up by recreating this client on its next use, instead of
    requiring the whole process to restart."""
    global _bedrock_client
    if _bedrock_client is None:
        from anthropic import AnthropicBedrock
        _bedrock_client = AnthropicBedrock(
            aws_profile=BEDROCK_PROFILE,
            aws_region=BEDROCK_REGION,
            http_client=httpx.Client(
                verify=_get_ssl_context(),
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=float(BEDROCK_TIMEOUT),
                    write=60.0,
                    pool=30.0,
                ),
            ),
        )
    return _bedrock_client


def _is_expired_credentials_error(e: Exception) -> bool:
    """Same check _friendly_error() (API/server.py) uses to recognize this
    case for its user-facing message -- kept in sync deliberately, since
    they're recognizing the exact same underlying AWS error."""
    text = str(e).lower()
    return "security token" in text and "expired" in text


def _invalidate_bedrock_client() -> None:
    global _bedrock_client
    _bedrock_client = None


def _call_bedrock(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 32000,
    json_mode: bool = False,
    model: str = BEDROCK_MODEL_ID,
) -> str:
    """Call Claude on Bedrock via the Anthropic SDK (streaming to avoid timeouts).
    `model` defaults to the safety-net fallback ARN, but a caller in the
    provider="bedrock" (explicit header selection) branch passes its own
    chosen ARN instead."""
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
                        if url.startswith("data:image/"):
                            header, b64_data = url.split(",", 1)
                            media_type = header.split(";")[0].replace("data:", "")
                            parts.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_data,
                                },
                            })
            anthropic_messages.append({"role": role, "content": parts})

    kwargs = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
    }
    if system_content:
        kwargs["system"] = system_content
    if json_mode:
        # Force a tool call instead of asking the model to freehand a JSON
        # blob in plain text — Anthropic constrains tool-call input against
        # the tool's schema at the decoding level, which is what actually
        # prevents "valid JSON followed by stray trailing content" (a plain
        # prompt instruction doesn't enforce anything, it's just a hint).
        kwargs["tools"] = [{
            "name": _JSON_TOOL_NAME,
            "description": "Return the requested result as a single JSON object.",
            "input_schema": _JSON_TOOL_SCHEMA,
        }]
        kwargs["tool_choice"] = {"type": "tool", "name": _JSON_TOOL_NAME}

    # Use streaming to avoid read timeouts on large responses. text_stream
    # yields nothing when the response is entirely a tool_use block (no text
    # content), which is expected and fine here.
    def _stream_once(c):
        parts = []
        with c.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                parts.append(text)
        return parts, stream.get_final_message()

    try:
        chunks, response = _stream_once(client)
    except Exception as e:
        if not _is_expired_credentials_error(e):
            raise
        # The cached client's AWS credentials were resolved once, at
        # construction, and this process never re-checked disk since -- an
        # `aws sso login` refresh elsewhere doesn't reach it until a new
        # client is built. Recreate once and retry before giving up, so a
        # mid-session credential refresh doesn't require restarting the app.
        _invalidate_bedrock_client()
        client = _get_bedrock_client()
        chunks, response = _stream_once(client)
    run_id = _get_current_run_id()
    _record_usage(
        run_id,
        response.usage.input_tokens,
        response.usage.output_tokens,
        model=model,
    )

    if json_mode:
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == _JSON_TOOL_NAME:
                # block.input is already a parsed dict (Anthropic validates it
                # against input_schema before handing it back) — round-trip
                # through json.dumps so this function's return contract stays
                # "a string chat_json() parses", unchanged for every caller.
                return json.dumps(block.input)
        # Model didn't call the tool despite tool_choice forcing it — fall
        # through to whatever text it did produce so chat_json()'s existing
        # repair/retry logic still gets a chance instead of a bare crash.

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
    provider, sel_model = _read_selection()
    if provider == "bedrock":
        return _call_bedrock(messages, system=system, max_tokens=max_tokens, json_mode=json_mode, model=sel_model)

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

    max_retries = 3
    last_error = None
    global _json_response_format_supported, _tool_json_supported
    for attempt in range(max_retries):
        try:
            create_kwargs = dict(
                model=sel_model,
                max_tokens=max_tokens,
                messages=full_messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            use_tool_json = json_mode and _tool_json_supported
            if use_tool_json:
                create_kwargs["tools"] = [{
                    "type": "function",
                    "function": {
                        "name": _JSON_TOOL_NAME,
                        "description": "Return the requested result as a single JSON object.",
                        "parameters": _JSON_TOOL_SCHEMA,
                    },
                }]
                create_kwargs["tool_choice"] = {"type": "function", "function": {"name": _JSON_TOOL_NAME}}
            elif json_mode and _json_response_format_supported:
                create_kwargs["response_format"] = {"type": "json_object"}
            stream = client.chat.completions.create(**create_kwargs)

            chunks = []
            tool_arg_chunks = []
            usage_data = None
            for chunk in stream:
                if not chunk.choices:
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage_data = chunk.usage
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    chunks.append(delta.content)
                if getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        if tc.function and tc.function.arguments:
                            tool_arg_chunks.append(tc.function.arguments)
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_data = chunk.usage

            # Record token usage
            run_id = _get_current_run_id()
            if usage_data:
                _record_usage(
                    run_id,
                    getattr(usage_data, "prompt_tokens", 0),
                    getattr(usage_data, "completion_tokens", 0),
                    model=sel_model,
                )
            else:
                # chunks alone misses everything when json_mode forced a tool
                # call (the common case) — the model's entire answer streams
                # in as tool_arg_chunks instead, with delta.content empty the
                # whole time. Without this, a proxy that omits the usage
                # chunk for a tool-forced stream (observed on several
                # OpenAI-compatible proxies) recorded a multi-KB JSON
                # response as ~0 output tokens.
                est_input = sum(len(str(m.get("content", ""))) for m in full_messages) // 4
                est_output = (sum(len(c) for c in chunks) + sum(len(c) for c in tool_arg_chunks)) // 4
                _record_usage(run_id, est_input, est_output, model=sel_model)

            # Tool-call arguments take priority when tool_choice forced one —
            # content is normally empty in that turn anyway, but prefer the
            # tool result explicitly rather than relying on that always holding.
            return "".join(tool_arg_chunks) if tool_arg_chunks else "".join(chunks)

        except _RETRYABLE_LITELLM_ERRORS as e:
            last_error = e
            _client = None
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                print(f"[llm.chat] LiteLLM failed ({type(e).__name__}), retrying in {wait}s (attempt {attempt+1}/{max_retries})...", flush=True)
                time.sleep(wait)
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

        except APIStatusError as e:
            # Not every model/proxy behind LiteLLM accepts tools/tool_choice or
            # response_format at all — some reject the request outright (400)
            # rather than silently ignoring an unsupported field. Cascade down
            # to a weaker mode and retry immediately rather than failing the
            # whole call; each flag is module-wide so this discovery cost is
            # paid at most once per process. Checked AFTER _RETRYABLE_LITELLM_ERRORS (which
            # InternalServerError — a 500 — is already part of) so a real
            # server error still gets retried/falls back to Bedrock instead of
            # being swallowed here.
            if getattr(e, "status_code", None) == 400:
                if json_mode and _tool_json_supported:
                    _tool_json_supported = False
                    print("[llm.chat] tools/tool_choice rejected by model/proxy — "
                          "falling back to response_format=json_object", flush=True)
                    continue
                if json_mode and _json_response_format_supported:
                    _json_response_format_supported = False
                    print("[llm.chat] response_format=json_object rejected by model/proxy — "
                          "falling back to prompt-only JSON mode", flush=True)
                    continue
            raise

    # ── Fallback to Bedrock ──────────────────────────────────────────────────
    try:
        return _call_bedrock(messages, system=system, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as bedrock_err:
        raise RuntimeError(
            f"Both LiteLLM and Bedrock failed.\n"
            f"  LiteLLM error: {last_error}\n"
            f"  Bedrock error: {bedrock_err}"
        ) from bedrock_err


_stream_using_fallback = False  # sticky, same rationale as chat()'s own _using_fallback — tracked
# separately since this is a structurally different call path (a live generator, not chat()'s
# own fully-buffered one), not a thin wrapper around chat()'s retry loop.


def chat_stream_with_usage(
    messages: list[dict],
    system: str = "",
    model: str | None = None,
    max_tokens: int = 32000,
    temperature: float = 0.2,
    force_model: tuple[str, str] | None = None,
):
    """
    Streaming variant of chat() — yields tokens as they arrive instead of
    buffering the whole response, for callers that need to relay live
    progress (e.g. Product Forge's per-token SSE updates; chat()'s own
    internal `for chunk in stream:` loop has no way to expose that to a
    caller, only the final joined string).

    Deliberately does NOT retry the same provider on failure the way chat()
    does: chat() can safely retry because nothing is exposed to its caller
    until a full attempt succeeds, but this generator yields tokens to the
    caller in real time — if a failure happens after some tokens were
    already yielded (and, for a caller like Product Forge, already shown
    to a user and appended to a running transcript), retrying the same
    request from scratch would duplicate/corrupt what's already gone out.
    So: try LiteLLM once, and on ANY failure that looks like unavailability
    (matches chat()'s own retryable exception types, or a 503/connection-
    style message), fall back to Bedrock once — which naturally starts a
    fresh response rather than replaying a partial one. Sticky across
    calls, same as chat()'s own fallback flag.

    Returns (generator, usage_ref) — usage_ref is a mutable dict
    (model/input_tokens/output_tokens/finish_reason) populated as the
    stream is consumed; read it only AFTER the generator is exhausted.
    Deliberately has no cost_usd: this module has no notion of per-model
    dollar pricing (chat() doesn't return one either — see token_tracker
    for this platform's own usage accounting); a caller that needs a cost
    figure applies its own pricing table to the token counts here.

    force_model: an explicit (provider, model) override that wins even over
    the header's global selection — unlike the ignored `model=` tier hint
    above, this is a real, intentional override, for the one caller that
    needs to deliberately step outside the header picker's choice: Product
    Forge's Draft Mode, which wants "whatever's cheapest and reachable right
    now" (see pick_cheapest_reachable_model()) regardless of what the user
    has selected in the header for their own manual runs.
    """
    global _stream_using_fallback
    if force_model:
        provider, resolved_model = force_model
    else:
        # The header's global model selection wins over a caller-supplied
        # `model=` (e.g. Product Forge's own draft/artifact tier choice) —
        # the picker is meant to be a hard override, not just a fallback
        # default, for every caller that doesn't explicitly opt out via
        # force_model above.
        provider, resolved_model = _read_selection()
    usage_ref = {"model": resolved_model, "input_tokens": 0, "output_tokens": 0, "finish_reason": None}

    full_messages: list[dict] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    def _bedrock_gen(bedrock_model: str = BEDROCK_MODEL_ID):
        client = _get_bedrock_client()
        anthropic_messages = []
        system_content = system
        for msg in messages:
            if msg["role"] == "system":
                system_content = (system_content + "\n\n" + msg["content"]) if system_content else msg["content"]
                continue
            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
        kwargs = {"model": bedrock_model, "messages": anthropic_messages, "max_tokens": max_tokens}
        if system_content:
            kwargs["system"] = system_content
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
        response = stream.get_final_message()
        usage_ref["input_tokens"] = response.usage.input_tokens
        usage_ref["output_tokens"] = response.usage.output_tokens
        usage_ref["model"] = f"bedrock:{bedrock_model.split('/')[-1]}"
        usage_ref["finish_reason"] = response.stop_reason
        _record_usage(_get_current_run_id(), usage_ref["input_tokens"], usage_ref["output_tokens"], model=bedrock_model)

    def _gen():
        global _stream_using_fallback, _client
        if provider == "bedrock":
            yield from _bedrock_gen(bedrock_model=resolved_model)
            return
        if _stream_using_fallback:
            yield from _bedrock_gen()
            return

        try:
            client = _get_client()
            stream = client.chat.completions.create(
                model=resolved_model, max_tokens=max_tokens, messages=full_messages,
                temperature=temperature, stream=True, stream_options={"include_usage": True},
            )
            for chunk in stream:
                if not chunk.choices:
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage_ref["input_tokens"] = getattr(chunk.usage, "prompt_tokens", 0) or 0
                        usage_ref["output_tokens"] = getattr(chunk.usage, "completion_tokens", 0) or 0
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
                if chunk.choices[0].finish_reason:
                    usage_ref["finish_reason"] = chunk.choices[0].finish_reason
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_ref["input_tokens"] = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    usage_ref["output_tokens"] = getattr(chunk.usage, "completion_tokens", 0) or 0
            _record_usage(_get_current_run_id(), usage_ref["input_tokens"], usage_ref["output_tokens"], model=resolved_model)
        except Exception as e:
            _client = None
            is_retryable_type = isinstance(e, _RETRYABLE_LITELLM_ERRORS)
            error_str = str(e).lower()
            looks_unavailable = any(x in error_str for x in ["503", "service unavailable", "connection", "timed out", "refused"])
            if is_retryable_type or looks_unavailable:
                print(f"[llm.chat_stream_with_usage] LiteLLM unavailable ({e}) — falling back to Bedrock", flush=True)
                _stream_using_fallback = True
                yield from _bedrock_gen()
            else:
                raise

    return _gen(), usage_ref


_tools_using_fallback = False  # sticky, same rationale as chat()'s own _using_fallback


def chat_with_tools(messages: list[dict], tools: list[dict], system: str = "",
                     max_tokens: int = 4096) -> dict:
    """
    A single non-streaming turn of real OpenAI-style function-calling — the
    caller passes an arbitrary tool list (e.g. converted from an MCP server's
    own tools/list) and gets back either a final text reply or a list of tool
    calls to execute and feed back as role="tool" messages before calling
    again. Used by MCPGenerator's chat tester (mcp_agents/mcp_chat.py) to let
    an LLM answer questions against a generated MCP server's real tools.

    Deliberately separate from chat()/chat_json() above rather than extending
    them — those two are on the hot path of every generation pipeline in this
    platform, and their retry/fallback logic already carries real
    capability-detection complexity (see _tool_json_supported); adding a third
    calling convention to that surface risked destabilizing something every
    other feature depends on for a feature that isn't in that hot path at all.

    Falls back to Bedrock (Anthropic-native tool use, via
    _call_bedrock_with_tools) on the same sticky basis as chat() — once
    LiteLLM has failed here, every subsequent chat_with_tools() call in this
    process goes straight to Bedrock instead of re-paying 3 retries against a
    proxy that's known to be down (observed directly: this platform's shared
    LiteLLM proxy had a real outage while this feature was being built).
    """
    global _client, _tools_using_fallback
    provider, sel_model = _read_selection()
    if provider == "bedrock":
        return _call_bedrock_with_tools(messages, tools, system=system, max_tokens=max_tokens, model=sel_model)

    if _tools_using_fallback:
        return _call_bedrock_with_tools(messages, tools, system=system, max_tokens=max_tokens)

    client = _get_client()
    full_messages: list[dict] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=sel_model, max_tokens=max_tokens, messages=full_messages,
                tools=tools, tool_choice="auto",
            )
            choice = completion.choices[0]
            usage = getattr(completion, "usage", None)
            run_id = _get_current_run_id()
            if usage:
                _record_usage(run_id, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0), model=sel_model)

            tool_calls = []
            for tc in (choice.message.tool_calls or []):
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
            return {"content": choice.message.content, "tool_calls": tool_calls}

        except _RETRYABLE_LITELLM_ERRORS as e:
            last_error = e
            if attempt < max_retries - 1:
                _client = None
                time.sleep(2 * (attempt + 1))
                client = _get_client()
            else:
                _tools_using_fallback = True
                print(
                    f"\n{'='*60}\n"
                    f"[FALLBACK] chat_with_tools: LiteLLM unavailable after {max_retries} retries.\n"
                    f"           Switching to AWS Bedrock ({BEDROCK_MODEL_ID}).\n"
                    f"           Last error: {last_error}\n"
                    f"{'='*60}\n",
                    flush=True,
                )

    try:
        return _call_bedrock_with_tools(messages, tools, system=system, max_tokens=max_tokens)
    except Exception as bedrock_err:
        raise RuntimeError(
            f"Both LiteLLM and Bedrock failed.\n"
            f"  LiteLLM error: {last_error}\n"
            f"  Bedrock error: {bedrock_err}"
        ) from bedrock_err


def _openai_tools_to_anthropic(tools_openai: list[dict]) -> list[dict]:
    """MCP tools are fetched once as OpenAI-style function-calling schemas
    (the primary LiteLLM/OpenAI-SDK path) — Bedrock's native tool-use format
    is structurally the same information, just renamed/flattened."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in tools_openai
    ]


def _openai_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Converts the OpenAI-shape conversation chat_with_tools() maintains
    (role: user/assistant/tool, tool_calls with JSON-string arguments) into
    Anthropic's content-block shape (tool_use/tool_result blocks) — done here,
    not by the caller, so mcp_chat.py's loop stays provider-agnostic exactly
    like every other chat_with_tools() caller."""
    anthropic_messages = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            anthropic_messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m.get("content") or ""}],
            })
        elif role == "assistant" and m.get("tool_calls"):
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                fn = tc["function"]
                try:
                    args = json.loads(fn["arguments"]) if fn["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                blocks.append({"type": "tool_use", "id": tc["id"], "name": fn["name"], "input": args})
            anthropic_messages.append({"role": "assistant", "content": blocks})
        else:
            anthropic_messages.append({"role": role, "content": m.get("content") or ""})
    return anthropic_messages


def _call_bedrock_with_tools(messages: list[dict], tools: list[dict], system: str = "",
                              max_tokens: int = 4096, model: str = BEDROCK_MODEL_ID) -> dict:
    """Anthropic-native tool-use call on Bedrock — the fallback path for
    chat_with_tools(), and also its direct path when the header has an
    explicit Bedrock model selected. Takes/returns the same OpenAI-ish shape
    as chat_with_tools() itself; the Anthropic-specific conversion is
    entirely internal to this function."""
    client = _get_bedrock_client()
    anthropic_tools = _openai_tools_to_anthropic(tools)
    anthropic_messages = _openai_messages_to_anthropic(messages)

    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": anthropic_messages, "tools": anthropic_tools}
    if system:
        kwargs["system"] = system
    try:
        response = client.messages.create(**kwargs)
    except Exception as e:
        if not _is_expired_credentials_error(e):
            raise
        # Same reasoning as _call_bedrock's own retry -- see there.
        _invalidate_bedrock_client()
        client = _get_bedrock_client()
        response = client.messages.create(**kwargs)

    text_parts = [b.text for b in response.content if b.type == "text"]
    tool_calls = [
        {"id": b.id, "name": b.name, "arguments": b.input}
        for b in response.content if b.type == "tool_use"
    ]
    return {"content": "".join(text_parts) or None, "tool_calls": tool_calls}


def _unwrap_stray_json_key(obj):
    """Tool-forced JSON extraction (_JSON_TOOL_SCHEMA has no defined
    properties, so the model is free to shape its "arguments" object however
    it wants) occasionally wraps the entire real answer one level too deep
    under a single key literally named "json" — e.g.
    {"json": {"entities": [...], "endpoints": [...]}} instead of
    {"entities": [...], "endpoints": [...]} directly. Confirmed in practice:
    an API architecture call returned exactly this shape, so every caller
    reading arch_result["entities"] etc. silently saw an empty list and every
    downstream per-entity stage (models, seed data, backend code) generated
    nothing — no error, just a backend with zero entities.

    Loops rather than unwrapping once, so a model that nests it twice
    ({"json": {"json": {...}}} — seen as a real possibility, not just this
    one bug) is still fully recovered, not left one layer short.

    Deliberately scoped to the literal key "json" only, not "any single-key
    dict" — that would also strip a call site whose schema genuinely expects
    exactly one top-level key (e.g. api_orchestrator.py's file-generation
    calls, which legitimately return {"files": {...}}); "json" is safe
    because no real caller's schema anywhere in this codebase ever expects
    a top-level field literally named "json". A different stray key name
    (e.g. "result", "response") would NOT be caught here — that's guarded
    per-caller instead, at the specific call sites that know their own
    expected shape well enough to detect and recover from it safely (see
    api_orchestrator.py's _recover_expected_shape for the architecture call).
    """
    seen = 0
    while isinstance(obj, dict) and len(obj) == 1 and isinstance(obj.get("json"), dict):
        obj = obj["json"]
        seen += 1
        if seen > 10:  # pathological/cyclic input — stop rather than loop forever
            break
    return obj


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
            return _unwrap_stray_json_key(json.loads(text, strict=False))
        except json.JSONDecodeError as e:
            # "Extra data" means the model wrote one complete, valid JSON value
            # and then kept going — not malformed JSON, just more content
            # after it. json.loads() is just being strict about demanding the
            # whole string be exactly one value; parse just the first complete
            # value and discard whatever trails it instead of treating this as
            # a failure at all. Deterministic, so it doesn't cost a retry or
            # another model call — the fix is being a more lenient reader, not
            # fixing the model's output.
            if "Extra data" in str(e):
                try:
                    obj, end = json.JSONDecoder(strict=False).raw_decode(text)
                    trailing = len(text) - end
                    print(f"[chat_json] response had {trailing} trailing char(s) after a "
                          f"complete JSON value — discarded, not treated as an error", flush=True)
                    return _unwrap_stray_json_key(obj)
                except json.JSONDecodeError:
                    pass  # genuinely malformed even from the start — fall through below

            # Try fixing invalid escape sequences (LLM often writes \' or bare \n in strings)
            if "Invalid \\escape" in str(e) or "invalid escape" in str(e).lower():
                import re as _re_esc
                fixed_text = _re_esc.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
                try:
                    return _unwrap_stray_json_key(json.loads(fixed_text, strict=False))
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
                        return _unwrap_stray_json_key(json.loads(merged, strict=False))
                    except json.JSONDecodeError as e2:
                        if "Invalid \\escape" in str(e2) or "invalid escape" in str(e2).lower():
                            import re as _re_esc2
                            fixed_merged = _re_esc2.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', merged)
                            try:
                                return _unwrap_stray_json_key(json.loads(fixed_merged, strict=False))
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
    return _read_selection()[1]


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
