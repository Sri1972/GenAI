"""
SDK Client — shared Anthropic client for all agents.

Primary:  AWS Bedrock via AnthropicBedrock + streaming
Fallback: LiteLLM proxy via Anthropic SDK (activated when Bedrock is unavailable)

Bedrock is primary rather than LiteLLM because the LiteLLM QA proxy has proven
unreliable (repeated weekend outages) — direct Bedrock access doesn't depend on
that proxy's uptime at all. Once fallback is activated, all subsequent calls in
this process go directly to LiteLLM (sticky fallback, same as before the swap).
"""

import json
import os
import re
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

# Temperature for custom (no-skill-match) page/component generation. Low but
# not 0: a page built with no pre-built skill template gets a fresh
# from-scratch implementation every time it's generated (fresh app, or a
# refine that touches it) - at the API's default temperature that varies
# meaningfully run to run (different layout choices, different structure)
# even for the identical prompt. 0 would maximize repeatability but full
# greedy decoding can occasionally lock into a repetitive/degraded pattern
# on long generations; 0.2 keeps generation close to deterministic without
# that risk. Callers opt in explicitly via run_agent(temperature=...) -
# this is not a global default, since stages that benefit from creative
# exploration (e.g. the UX Architect designing page layout) should keep the
# API's normal temperature.
CUSTOM_GEN_TEMPERATURE = float(os.environ.get("CUSTOM_GEN_TEMPERATURE", "0.2"))

# Fallback: Bedrock (same config as legacy llm.py)
BEDROCK_MODEL_ID = os.environ.get(
    "CLAUDE_SONNET_5_MODEL_ID",
    os.environ.get(
        "BEDROCK_MODEL_ID",
        "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/oonx9pzz8l4h",
    ),
)
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_PROFILE = os.environ.get("AWS_PROFILE", "default")
# Deliberately its OWN env var, not a reuse of LITELLM_TIMEOUT: Bedrock is the
# fallback for exactly the case where the primary path is struggling, so it
# needs at least as much patience, not whatever short value LiteLLM happens to
# be tuned to. Reusing LITELLM_TIMEOUT here meant a low LiteLLM value (e.g. 120s,
# sized for a fast proxy) silently capped Bedrock's read timeout too, making the
# fallback itself time out on large streamed responses before ever reporting
# LiteLLM's real failure reason.
BEDROCK_TIMEOUT = int(os.environ.get("BEDROCK_TIMEOUT", "600"))

MAX_TOOL_ROUNDS = 10
MAX_RETRIES = 3

# ── Token tracking ───────────────────────────────────────────────────────────
import token_tracker

_litellm_client = None
_bedrock_client = None
_using_fallback = False
# Discovered once per process, same pattern as agents/llm.py's
# _tool_json_supported: whether the model behind BEDROCK_MODEL_ID needs the
# current "adaptive" thinking shape instead of the older "enabled"+
# budget_tokens one. Starts False (try the existing shape first, since it's
# still correct for some models, e.g. Haiku 4.5) and flips permanently once
# a real 400 confirms it — see _call_with_fallback's non-retryable branch.
# BEDROCK_MODEL_ID is frequently an opaque application-inference-profile ARN
# with no model name in it, so this can't be decided from the model string
# up front; it has to be discovered from the API's own response.
_bedrock_needs_adaptive_thinking = False
# Same pattern, same reason (opaque inference-profile ARN — can't be decided
# from the model string, only discovered from a real 400): whether the model
# behind BEDROCK_MODEL_ID has dropped the `temperature` parameter entirely.
# Starts False (send it as before) and flips permanently once a real 400
# confirms it — see _call_with_fallback's non-retryable branch.
_bedrock_rejects_temperature = False

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
                    read=float(BEDROCK_TIMEOUT),
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
        self._details: list[str] = []

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def add_detail(self, detail: str):
        self._details.append(detail)

    def _run(self):
        last_detail_idx = 0
        while not self._stop_event.wait(self._interval):
            elapsed = int(_time.time() - self._start)
            # Show discovered details (e.g. table names, file names) if available
            if self._details and len(self._details) > last_detail_idx:
                new_details = self._details[last_detail_idx:]
                last_detail_idx = len(self._details)
                for d in new_details:
                    detail_msg = f"crew:    ↳ {d}"
                    if _progress_fn:
                        _progress_fn(detail_msg)
                    else:
                        print(f"    ↳ {d}", flush=True)
            else:
                msg = f"crew:    ...still generating ({elapsed}s elapsed)"
                if _progress_fn:
                    _progress_fn(msg)
                else:
                    print(f"    ...still generating ({elapsed}s elapsed)", flush=True)


def _extract_stream_details(text_so_far: str, heartbeat: _Heartbeat, _seen: set):
    """Extract meaningful progress info from partial streamed text."""
    # Detect CREATE TABLE statements (data architect)
    for m in re.finditer(r'CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)', text_so_far):
        table = m.group(1)
        if table not in _seen:
            _seen.add(table)
            heartbeat.add_detail(f"Designing table: {table}")
    # Detect file names in {"files": {"filename": ...}} pattern
    for m in re.finditer(r'"([^"]+\.(sql|tsx|ts|py|json|css))":\s*"', text_so_far):
        fname = m.group(1)
        if fname not in _seen:
            _seen.add(fname)
            heartbeat.add_detail(f"Generating: {fname}")
    # Detect INSERT INTO (seed data)
    for m in re.finditer(r'INSERT INTO\s+(\w+)', text_so_far):
        table = m.group(1)
        key = f"seed_{table}"
        if key not in _seen:
            _seen.add(key)
            heartbeat.add_detail(f"Seeding data: {table}")


def _call_litellm(kwargs: dict) -> object:
    """Call LiteLLM with streaming to avoid gateway timeouts on large responses."""
    client = _get_litellm_client()
    heartbeat = _Heartbeat(interval=30)
    heartbeat.start()
    try:
        collected_text = ""
        seen: set = set()
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                collected_text += text
                if len(collected_text) % 2000 < len(text):
                    _extract_stream_details(collected_text, heartbeat, seen)
            return stream.get_final_message()
    finally:
        heartbeat.stop()


def _call_bedrock_streaming(kwargs: dict, model_override: str | None = None) -> object:
    """
    Call Bedrock via streaming (same approach as legacy llm.py).
    Streaming avoids read timeouts on large responses.

    model_override: an explicit model/ARN the caller (via run_agent's own
    `model=` param) asked for, honored on Bedrock too instead of always
    forcing BEDROCK_MODEL_ID. Deliberately NOT `kwargs.get("model")` — that
    key holds whatever _run_agent_once resolved for the LiteLLM path
    (`model or MODEL_ID`, defaulting to a LiteLLM model string that is not a
    valid Bedrock model/ARN), which would break every call with no explicit
    override instead of just the ones that actually asked for one.
    """
    client = _get_bedrock_client()
    bedrock_kwargs = {
        "model": model_override or BEDROCK_MODEL_ID,
        "max_tokens": kwargs["max_tokens"],
        "messages": kwargs["messages"],
    }
    if "system" in kwargs:
        bedrock_kwargs["system"] = kwargs["system"]
    if "tools" in kwargs:
        bedrock_kwargs["tools"] = kwargs["tools"]
    if "thinking" in kwargs:
        # Without this, the thinking-budget cap computed in _run_agent_once
        # (see its comment) never reaches Bedrock - a big/complex task (e.g.
        # a multi-table schema + 200+ row seed) can then burn the entire
        # max_tokens budget on internal reasoning with zero actual output,
        # which is exactly the failure this cap exists to prevent.
        # Once _bedrock_needs_adaptive_thinking is discovered True, the
        # {"type": "enabled", "budget_tokens": N} shape computed above is
        # rejected outright by this model with a 400 — swap in the current
        # {"type": "adaptive"} shape instead of forwarding it as-is.
        if _bedrock_needs_adaptive_thinking:
            bedrock_kwargs["thinking"] = {"type": "adaptive"}
        else:
            bedrock_kwargs["thinking"] = kwargs["thinking"]
    if "temperature" in kwargs and not _bedrock_rejects_temperature:
        # Same forwarding gap as "thinking" above - without this, a caller's
        # custom temperature (e.g. CUSTOM_GEN_TEMPERATURE for consistent
        # custom-page generation) is silently dropped on the Bedrock path.
        # Once _bedrock_rejects_temperature is discovered True, this model
        # has dropped the parameter entirely (400: "`temperature` is
        # deprecated for this model") — omit it rather than send a value
        # it'll reject outright; there's no replacement shape to swap in
        # the way "thinking" has adaptive, so the caller's requested
        # temperature is simply not honorable on this model.
        bedrock_kwargs["temperature"] = kwargs["temperature"]

    heartbeat = _Heartbeat(interval=30)
    heartbeat.start()
    try:
        collected_text = ""
        seen: set = set()
        with client.messages.stream(**bedrock_kwargs) as stream:
            for text in stream.text_stream:
                collected_text += text
                if len(collected_text) % 2000 < len(text):
                    _extract_stream_details(collected_text, heartbeat, seen)
            response = stream.get_final_message()
    finally:
        heartbeat.stop()
    return response


def _call_with_fallback(kwargs: dict, model_override: str | None = None) -> object:
    """
    Try Bedrock with retries, fall back to LiteLLM if unavailable.
    Once fallback is activated, all subsequent calls go to LiteLLM.
    """
    global _using_fallback, _bedrock_client, _bedrock_needs_adaptive_thinking, _bedrock_rejects_temperature

    if _using_fallback:
        return _call_litellm(kwargs)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return _call_bedrock_streaming(kwargs, model_override=model_override)
        except _RETRYABLE as e:
            last_error = e
            _bedrock_client = None  # reset client on connection issues
            if attempt < MAX_RETRIES - 1:
                wait = 3 * (attempt + 1)
                print(
                    f"[sdk_client] Bedrock failed ({type(e).__name__}), "
                    f"retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})...",
                    flush=True,
                )
                _time.sleep(wait)
            else:
                _using_fallback = True
                print(
                    f"\n{'='*60}\n"
                    f"[SDK FALLBACK] AWS Bedrock unavailable after {MAX_RETRIES} retries.\n"
                    f"               Switching to LiteLLM proxy.\n"
                    f"               Last error: {last_error}\n"
                    f"{'='*60}\n",
                    flush=True,
                )
        except Exception as e:
            # A wrong-shape "thinking" param (see _bedrock_needs_adaptive_thinking's
            # docstring) is a fixable request bug, not a real Bedrock outage — the
            # generic handler below treats every non-retryable error as "Bedrock is
            # broken" and permanently routes every future call to LiteLLM, which
            # papers over the mistake instead of fixing it and silently switches the
            # provider the user explicitly selected (the header keeps showing
            # "Bedrock" while every call actually goes to LiteLLM). Recognize this
            # one specific, self-describing 400 and retry ONCE on Bedrock itself
            # with the corrected shape before falling back to the generic handling.
            # NOTE: deliberately NOT gated on "not _bedrock_needs_adaptive_thinking"
            # (nor the temperature check below on its own flag) — _run_pages
            # generates multiple pages concurrently via a thread pool, so several
            # calls can be in-flight with the OLD (doomed) request shape at once.
            # Gating the retry on the flag meant only the FIRST thread to hit this
            # error ever got the fix: it would set the flag and recover, but any
            # OTHER thread already in its own exception handler for the SAME error
            # would find the flag already True by the time it checked — "not True"
            # is False, so it skipped the retry entirely and fell straight through
            # to the generic give-up-on-Bedrock path, even though the correction
            # was already known and would have trivially worked for it too.
            # Every call that hits this specific error retries once, unconditionally;
            # the flag itself (still set here, unconditionally/idempotently) only
            # exists so FUTURE calls in _call_bedrock_streaming proactively build
            # the corrected request the first time, without needing to fail first.
            if "thinking.type.adaptive" in str(e):
                _bedrock_needs_adaptive_thinking = True
                print(
                    f"[sdk_client] Bedrock model requires adaptive thinking, not "
                    f"budget_tokens — retrying on Bedrock with thinking.type=adaptive "
                    f"instead of falling back to LiteLLM.",
                    flush=True,
                )
                try:
                    return _call_bedrock_streaming(kwargs, model_override=model_override)
                except Exception as retry_err:
                    e = retry_err  # fall through to the generic handling below

            # Same reasoning as the thinking-shape case above — a dropped
            # `temperature` parameter is a fixable request bug (this model no
            # longer accepts it at all), not a real outage. Retry once on
            # Bedrock with it omitted before falling back to LiteLLM.
            if "temperature" in str(e) and "deprecated" in str(e):
                _bedrock_rejects_temperature = True
                print(
                    f"[sdk_client] Bedrock model no longer accepts `temperature` — "
                    f"retrying on Bedrock with it omitted instead of falling back to LiteLLM.",
                    flush=True,
                )
                try:
                    return _call_bedrock_streaming(kwargs, model_override=model_override)
                except Exception as retry_err:
                    e = retry_err  # fall through to the generic handling below

            # Non-retryable failure (e.g. expired AWS SSO session, 403 access
            # denied) — retrying the same broken auth MAX_RETRIES times wastes
            # time for no benefit, so go straight to the LiteLLM fallback instead
            # of propagating immediately (the old code only fell back on the
            # _RETRYABLE set; a non-retryable primary failure used to skip the
            # fallback entirely, which is why an expired-credentials error used
            # to surface as a bare crash instead of trying LiteLLM first).
            last_error = e
            _using_fallback = True
            print(
                f"\n{'='*60}\n"
                f"[SDK FALLBACK] AWS Bedrock failed with a non-retryable error "
                f"({type(e).__name__}).\n"
                f"               Switching to LiteLLM proxy.\n"
                f"               Last error: {last_error}\n"
                f"{'='*60}\n",
                flush=True,
            )
            break

    # LiteLLM fallback
    try:
        return _call_litellm(kwargs)
    except Exception as litellm_err:
        raise RuntimeError(
            f"Both Bedrock and LiteLLM failed.\n"
            f"  Bedrock error: {last_error}\n"
            f"  LiteLLM error: {litellm_err}"
        ) from litellm_err


class _JsonExtractionError(ValueError):
    """Raised by _run_agent_once when output_schema is set but no valid JSON
    could be extracted. Carries the raw text and the exact message history
    that produced it, so run_agent() can attempt a cheap continuation repair
    instead of always paying for a full from-scratch redo."""

    def __init__(self, message: str, raw_text: str = "", full_messages: list | None = None):
        super().__init__(message)
        self.raw_text = raw_text
        self.full_messages = full_messages or []


def run_agent(
    system: str,
    messages: list[dict],
    tools: list | None = None,
    output_schema: dict | None = None,
    max_tokens: int = 32000,
    model: str | None = None,
    use_thinking: bool = True,
    temperature: float | None = None,
) -> dict | str:
    """
    Unified agent runner — replaces chat() and chat_json() from llm.py.

    If output_schema is provided → returns a validated dict (structured output).
    If tools are provided → runs a manual tool-use loop.
    Otherwise → simple call, returns text.

    Whenever output_schema is set and the model fails to produce valid JSON:
    - If the raw response looks like it started a real JSON object and just got
      cut off (common on large multi-table/multi-widget generations sitting
      right at the max_tokens ceiling), try a cheap continuation first: ask the
      model to continue from exactly where it stopped, merge, and re-extract.
      This costs roughly the size of the missing tail, not a full redo.
    - Otherwise (or if continuation itself doesn't yield valid JSON), fall back
      to the original behavior: one full retry with an explicit reminder.
    This used to be duplicated as near-identical try/except boilerplate at every
    orchestrator.py call site — discovered piecemeal, one missing call site per
    failure report, because nothing forced every caller to remember to add it.
    Centralizing it here means every current and future caller gets it automatically.

    use_thinking=False is for pure data-generation calls (e.g. multi-table
    schema + hundreds of seed rows) where extended thinking has repeatedly
    caused the model to exhaust the entire max_tokens budget on internal
    reasoning with zero actual output ("No text block in response. Blocks:
    ['thinking']"), reproduced across both Bedrock and LiteLLM. Anthropic's
    thinking budget_tokens is a soft target the model can and does exceed for
    a hard enough task, not a hard cap — capping it (see _run_agent_once)
    reduces but does not eliminate this failure. Disabling thinking outright
    guarantees the full max_tokens budget goes to real output instead, since
    there's no reasoning phase left to run away. Tasks that benefit from
    actual deliberation (architecture/page design) should keep the default.
    """
    try:
        return _run_agent_once(system, messages, tools=tools, output_schema=output_schema,
                                max_tokens=max_tokens, model=model, use_thinking=use_thinking,
                                temperature=temperature)
    except ValueError as e:
        if not output_schema or "Could not extract JSON" not in str(e):
            raise

        raw_text = getattr(e, "raw_text", "") or ""
        full_messages = getattr(e, "full_messages", None) or messages
        # Heuristic for "this is a truncated JSON object" rather than a
        # tool-loop-exhausted/no-JSON-at-all response (e.g. the model left
        # analysis prose with no JSON): it must have actually started an
        # object, and be long enough that a genuine mid-object cutoff is
        # plausible rather than the model simply never emitting JSON.
        looks_like_truncated_json = raw_text.lstrip().startswith("{") and len(raw_text) > 500
        if looks_like_truncated_json:
            logger.warning(
                f"run_agent: response looks truncated ({len(raw_text)} chars) — "
                f"attempting cheap continuation before falling back to a full redo"
            )
            try:
                return _continue_truncated(system, full_messages, raw_text,
                                            max_tokens=max_tokens, model=model)
            except ValueError as cont_err:
                logger.warning(f"run_agent: continuation repair failed ({cont_err}) — falling back to full retry")

        logger.warning(f"run_agent: retrying after JSON extraction failure: {e}")
        retry_messages = list(messages) + [{
            "role": "user",
            "content": (
                "Your previous response did not contain valid JSON. Stop calling "
                "tools or explaining — respond with ONLY the JSON object now, "
                "matching the requested schema."
            ),
        }]
        return _run_agent_once(system, retry_messages, tools=tools, output_schema=output_schema,
                                max_tokens=max_tokens, model=model, use_thinking=use_thinking,
                                temperature=temperature)


def _continue_truncated(
    system: str,
    prior_messages: list[dict],
    partial_text: str,
    max_tokens: int = 32000,
    model: str | None = None,
) -> dict:
    """
    Cheap repair for a truncated JSON response: ask the model to continue from
    exactly where it stopped (same approach as the legacy llm.py:chat_json's
    continuation logic) rather than redoing the entire generation at full cost.
    No tools here — continuation should be a plain text completion, not a new
    tool-use round.
    """
    continuation_messages = list(prior_messages) + [
        {"role": "assistant", "content": partial_text},
        {"role": "user", "content": (
            "Your response was cut off mid-way through the JSON. Continue the JSON "
            "from EXACTLY where you stopped — do NOT restart, do NOT repeat any part "
            "already written. Output ONLY the continuation (the remaining JSON text). "
            "No explanation, no markdown fences."
        )},
    ]
    # use_thinking=False: this injects a fake assistant turn (the partial text)
    # followed by a user instruction to continue it. Anthropic's extended-
    # thinking mode has real constraints around assistant turns in history
    # (e.g. true prefill requires a thinking block on that turn) that haven't
    # been verified safe for this specific pattern — staying off here rather
    # than risking an API-level rejection on the repair path itself.
    continuation = _run_agent_once(system, continuation_messages, tools=None, output_schema=None,
                                    max_tokens=max_tokens, model=model, use_thinking=False)
    if not continuation:
        raise ValueError("Continuation returned empty — nothing to merge")

    merged = (partial_text + continuation).strip()
    if merged.endswith("```"):
        merged = merged[:-3].rstrip()
    return _extract_json(merged)


def _run_agent_once(
    system: str,
    messages: list[dict],
    tools: list | None = None,
    output_schema: dict | None = None,
    max_tokens: int = 32000,
    model: str | None = None,
    use_thinking: bool = True,
    temperature: float | None = None,
) -> dict | str:
    """Single attempt — see run_agent() for the retry wrapper around this."""
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

    if temperature is not None:
        # Extended thinking requires the API's default temperature (1) - the
        # two are mutually exclusive. Every current caller that sets a custom
        # temperature also passes use_thinking=False, so this doesn't fire
        # alongside kwargs["thinking"] below, but guard it explicitly rather
        # than relying on callers to remember that constraint.
        if not use_thinking:
            kwargs["temperature"] = temperature

    if use_thinking:
        # Bounded, not unlimited: without an explicit cap, a big/complex task
        # (e.g. a multi-table schema + 150-row seed) can burn the ENTIRE
        # max_tokens budget on internal reasoning and never emit any actual
        # output — the model then returns a response with only a 'thinking'
        # block and no text/tool_use, which _run_agent_once has no content to
        # extract from ("no text block found"). Capping the thinking budget
        # guarantees real output budget always remains. Bounded to a fraction
        # of max_tokens (min 1024 per Anthropic's floor, max 16000 so it can't
        # dominate even a 64000-token call) rather than a fixed value, so small
        # calls (e.g. max_tokens=4000) still leave enough non-thinking room.
        thinking_budget = min(max(int(max_tokens * 0.25), 1024), 16000, max(max_tokens - 512, 0))
        if thinking_budget >= 1024:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

    total_input_tokens = 0
    total_output_tokens = 0

    # ── Tool-use loop ────────────────────────────────────────────────────────
    for _round in range(MAX_TOOL_ROUNDS):
        # Pass the caller's raw `model` (None unless explicitly overridden),
        # not `effective_model` (which defaults to MODEL_ID — a LiteLLM-only
        # model string) — so a genuine override reaches Bedrock too, while
        # the common no-override case still lets Bedrock use its own
        # BEDROCK_MODEL_ID default instead of being handed a LiteLLM model id.
        response = _call_with_fallback(kwargs, model_override=model)

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

        if not tool_results:
            # stop_reason says "tool_use" but no block in response.content actually
            # had type == "tool_use" — a streaming/proxy edge case. The Anthropic API
            # hard-rejects a user message with empty content (400: "must have
            # non-empty content"), so appending one here would crash every subsequent
            # call in this loop. Treat the response as final instead.
            logger.warning(
                "Tool loop: stop_reason='tool_use' but no tool_use blocks found in "
                "response.content — treating response as final."
            )
            break

        # Append assistant response + tool results for next iteration
        kwargs["messages"].append({"role": "assistant", "content": response.content})
        kwargs["messages"].append({"role": "user", "content": tool_results})
    else:
        logger.warning(f"Tool loop hit max rounds ({MAX_TOOL_ROUNDS})")

    # ── Record token usage ───────────────────────────────────────────────────
    # model=response.model (not effective_model, the requested model) so a
    # run that fell back from LiteLLM to Bedrock — which sends its own
    # BEDROCK_MODEL_ID regardless of what was requested, see
    # _call_bedrock_streaming — still gets priced at whichever model actually
    # served it. Confirmed missing entirely before this fix: every call
    # through this function was bucketed under token_tracker's "unknown" key
    # and priced at the generic default rate, reproducing — in this exact
    # call path — the same mispricing bug token_tracker.py's per-model
    # pricing table was built to eliminate everywhere else.
    run_id = token_tracker.get_run_id()
    token_tracker.record(run_id, total_input_tokens, total_output_tokens, model=getattr(response, "model", effective_model))

    # ── Extract result ───────────────────────────────────────────────────────
    for block in reversed(response.content):
        if block.type != "text":
            continue
        text = getattr(block, "text", "") or ""
        text = text.strip()
        if not text:
            continue

        if output_schema:
            try:
                return _extract_json(text)
            except ValueError as json_err:
                # Carry the raw text + message history so run_agent() can try a
                # cheap continuation repair instead of always redoing this whole
                # (potentially 30k+-token) call from scratch.
                raise _JsonExtractionError(str(json_err), raw_text=text,
                                            full_messages=kwargs["messages"]) from json_err
        return text

    logger.error(f"No text block in response. Blocks: {[b.type for b in response.content]}")
    if output_schema:
        # Same failure class _extract_json raises on (same message prefix, so
        # existing "Could not extract JSON" retry logic catches this too) — a
        # bare "" here violates run_agent's documented contract of always
        # returning a dict when output_schema is set, and every caller does
        # result.get(...) on what comes back without checking its type first.
        raise ValueError(
            f"Could not extract JSON from response — no text block found "
            f"(model likely exhausted the tool-use loop without concluding). "
            f"Blocks: {[b.type for b in response.content]}"
        )
    return ""


def _extract_json(text: str) -> dict:
    """
    Extract JSON from model response — handles fences, preamble, truncation, and trailing text.
    """
    text = text.strip()

    # Sanitize control characters that break JSON parsing (common in LLM code output)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # strict=False allows raw control chars (literal newlines/tabs) inside JSON
    # strings — the model frequently emits these instead of escaped \n when a
    # string value holds multi-line SQL/code, which strict mode would reject.
    #
    # Must return a dict: every caller of _extract_json (per its declared -> dict
    # contract) immediately does result.get("files", ...) on what comes back. If
    # `s` happens to be valid JSON of some other shape — e.g. the model's whole
    # response is itself a quoted string, so json.loads returns a plain str —
    # json.loads "succeeds" but hands back something with no .get(), crashing the
    # caller with an unrelated-looking AttributeError instead of a clear failure.
    # Raising here instead makes that case fall through to the next extraction
    # strategy below, and ultimately to the same ValueError every other genuine
    # extraction failure raises — which callers already know how to retry on.
    def _loads(s: str):
        result = json.loads(s, strict=False)
        if not isinstance(result, dict):
            raise json.JSONDecodeError("Parsed JSON is not an object", s, 0)
        return result

    # Direct parse
    try:
        return _loads(text)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct json.loads failed at pos {e.pos}: {e.msg}")
        pass

    # Strip markdown fences (closed)
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            try:
                return _loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Handle unclosed code fence (truncated response or backticks in content)
    fence_open = re.search(r"```(?:json)?\s*\n", text)
    if fence_open:
        after_fence = text[fence_open.end():]
        # Try parsing the content after the opening fence directly
        try:
            return _loads(after_fence.strip())
        except json.JSONDecodeError:
            pass
        # Strip a trailing incomplete ``` if present
        after_fence = re.sub(r"\n```\s*$", "", after_fence)
        try:
            return _loads(after_fence.strip())
        except json.JSONDecodeError:
            pass
        # Use this narrower text for brace matching below
        text = after_fence

    # Find first { to last } (the JSON object may have preamble/trailing text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return _loads(candidate)
        except json.JSONDecodeError:
            pass

        # Truncated JSON repair — walk backwards to find a parseable substring.
        # The response is typically {"files": {"name": "content", ...}} where content
        # contains code with literal braces — simple brace counting is unreliable.
        # Strategy: find the last valid JSON boundary by trying progressively shorter substrings.
        raw = text[first_brace:]
        # Try closing at each '"}\n' or '"},' boundary from the end backwards (file value endings)
        boundaries = [m.end() for m in re.finditer(r'"\s*\}', raw)]
        for end_pos in reversed(boundaries[-20:]):
            snippet = raw[:end_pos]
            # Close the outer wrapper: trim trailing comma, close remaining braces
            snippet = re.sub(r',\s*$', '', snippet)
            # Try as-is first
            try:
                result = _loads(snippet)
                logger.warning(f"Repaired truncated JSON (used {end_pos}/{len(raw)} chars)")
                return result
            except json.JSONDecodeError:
                pass
            # Try closing with one more brace (the outer {"files": ...})
            try:
                result = _loads(snippet + "}")
                logger.warning(f"Repaired truncated JSON (used {end_pos}/{len(raw)} chars + closing brace)")
                return result
            except json.JSONDecodeError:
                pass

        # Last resort: naive brace counting repair on the full candidate
        repaired = candidate.rstrip()
        if not repaired.endswith('}') and not repaired.endswith(']') and not repaired.endswith('"'):
            for end_marker in ('"}', '"]', '",', '},', '],'):
                idx = repaired.rfind(end_marker)
                if idx > len(repaired) // 2:
                    repaired = repaired[:idx + len(end_marker)]
                    break
        repaired = re.sub(r',\s*$', '', repaired)
        depth_brace = repaired.count("{") - repaired.count("}")
        depth_bracket = repaired.count("[") - repaired.count("]")
        repaired += "]" * max(0, depth_bracket) + "}" * max(0, depth_brace)
        try:
            result = _loads(repaired)
            logger.warning(f"Repaired truncated JSON via brace counting")
            return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract JSON from response (length={len(text)}). "
        f"First 200 chars: {text[:200]!r}. "
        f"Last 200 chars: {text[-200:]!r}"
    )
