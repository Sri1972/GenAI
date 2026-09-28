"""
Token usage tracker — shared by all TurboUIGen LLM pipelines.

Tracks prompt/completion tokens per run_id, computes costs,
and formats a summary block for build logs.

Used by:
  - WebUIGenerator/agents/llm.py (web app generate/refine)
  - FigmaMockupGenerator/figma/wireframe/figma_agent_shared.py (Figma wireframe)
"""

import os
import threading

# Pricing per million tokens, by model — a run billed at Haiku rates was
# reproduced directly showing 3x its real cost because every run used to be
# priced with one hardcoded global rate regardless of which model actually
# ran (defaulting to Sonnet 4.6's $3/$15, so a cheaper-model run's displayed
# cost was simply wrong, not reflective of the real bill). Keyed by the bare
# model id (no "bedrock:" prefix, no date suffix) — record() strips those
# before storing so a lookup here doesn't need to.
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5":  (1.00, 5.00),
    "claude-sonnet-5":   (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5":     (5.00, 25.00),
    "claude-opus-4-8":   (5.00, 25.00),
    "claude-opus-4-7":   (5.00, 25.00),
    "claude-opus-4-6":   (5.00, 25.00),
    "claude-fable-5-1":  (10.00, 50.00),
    "claude-fable-5":    (10.00, 50.00),
}
# Fallback for a model id not in the table above (new/unlisted model) or
# calls that never passed a model at all (e.g. figma_agent_shared.py's
# record_token_usage) — env-overridable, same as before this fix existed.
_DEFAULT_PRICING = (
    float(os.environ.get("LLM_COST_INPUT_PER_MTOK", "3.0")),
    float(os.environ.get("LLM_COST_OUTPUT_PER_MTOK", "15.0")),
)


def _rate_for_model(model: str | None) -> tuple[float, float]:
    if not model:
        return _DEFAULT_PRICING
    # Strip a "bedrock:" (or similar) prefix and any trailing date suffix
    # some callers pass (e.g. "claude-sonnet-4-6-20260115") so the same
    # entry matches regardless of which call site's naming convention.
    bare = model.split(":")[-1]
    if bare in _MODEL_PRICING:
        return _MODEL_PRICING[bare]
    for known, rates in _MODEL_PRICING.items():
        if bare.startswith(known):
            return rates
    return _DEFAULT_PRICING


def rate_for_model(model: str | None) -> tuple[float, float]:
    """Public wrapper around _rate_for_model — for callers outside this
    module that need to compare/rank models by cost (e.g. Product Forge's
    Draft Mode cheapest-reachable-model picker in agents/llm.py)."""
    return _rate_for_model(model)


_lock = threading.Lock()
_usage: dict[str, dict] = {}

# Thread-local run_id so each worker thread auto-tracks to the right bucket
_thread_local = threading.local()


def set_run_id(run_id: str) -> None:
    _thread_local.run_id = run_id


def get_run_id() -> str:
    return getattr(_thread_local, "run_id", "default")


def _empty_bucket() -> dict:
    return {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "by_model": {}}


def reset(run_id: str) -> None:
    with _lock:
        _usage[run_id] = _empty_bucket()


def record(run_id: str, prompt_tokens: int, completion_tokens: int, model: str | None = None) -> None:
    with _lock:
        if run_id not in _usage:
            _usage[run_id] = _empty_bucket()
        u = _usage[run_id]
        u["prompt_tokens"] += prompt_tokens
        u["completion_tokens"] += completion_tokens
        u["calls"] += 1
        # Grouped by model so get() can price each group at its own real
        # rate — a run that switches models mid-way (or a caller that never
        # passes one at all) is priced correctly either way, not lumped
        # together under one guessed rate.
        key = model or "unknown"
        by_model = u["by_model"].setdefault(key, {"prompt_tokens": 0, "completion_tokens": 0})
        by_model["prompt_tokens"] += prompt_tokens
        by_model["completion_tokens"] += completion_tokens


def get(run_id: str) -> dict:
    with _lock:
        u = _usage.get(run_id) or _empty_bucket()
        total_tokens = u["prompt_tokens"] + u["completion_tokens"]
        input_cost = 0.0
        output_cost = 0.0
        for model, sub in u["by_model"].items():
            in_rate, out_rate = _rate_for_model(None if model == "unknown" else model)
            input_cost += sub["prompt_tokens"] / 1_000_000 * in_rate
            output_cost += sub["completion_tokens"] / 1_000_000 * out_rate
        return {
            "prompt_tokens": u["prompt_tokens"],
            "completion_tokens": u["completion_tokens"],
            "calls": u["calls"],
            "total_tokens": total_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
        }


def format_summary(run_id: str, elapsed: float = 0) -> list[str]:
    u = get(run_id)
    return [
        "=" * 40,
        f"Token Usage | {elapsed:.1f}s | {u['calls']} LLM call{'s' if u['calls'] != 1 else ''}",
        f"   Input: {u['prompt_tokens']:,} tokens (${u['input_cost']:.4f})",
        f"   Output: {u['completion_tokens']:,} tokens (${u['output_cost']:.4f})",
        f"   Total: {u['total_tokens']:,} tokens - ${u['total_cost']:.4f}",
        "=" * 40,
    ]
