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

# Pricing per million tokens (defaults: Sonnet 4.6)
COST_INPUT_PER_MTOK = float(os.environ.get("LLM_COST_INPUT_PER_MTOK", "3.0"))
COST_OUTPUT_PER_MTOK = float(os.environ.get("LLM_COST_OUTPUT_PER_MTOK", "15.0"))

_lock = threading.Lock()
_usage: dict[str, dict] = {}

# Thread-local run_id so each worker thread auto-tracks to the right bucket
_thread_local = threading.local()


def set_run_id(run_id: str) -> None:
    _thread_local.run_id = run_id


def get_run_id() -> str:
    return getattr(_thread_local, "run_id", "default")


def reset(run_id: str) -> None:
    with _lock:
        _usage[run_id] = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


def record(run_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    with _lock:
        if run_id not in _usage:
            _usage[run_id] = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        _usage[run_id]["prompt_tokens"] += prompt_tokens
        _usage[run_id]["completion_tokens"] += completion_tokens
        _usage[run_id]["calls"] += 1


def get(run_id: str) -> dict:
    with _lock:
        u = _usage.get(run_id, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0})
        total_tokens = u["prompt_tokens"] + u["completion_tokens"]
        input_cost = u["prompt_tokens"] / 1_000_000 * COST_INPUT_PER_MTOK
        output_cost = u["completion_tokens"] / 1_000_000 * COST_OUTPUT_PER_MTOK
        return {
            **u,
            "total_tokens": total_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
        }


def format_summary(run_id: str, elapsed: float = 0) -> list[str]:
    u = get(run_id)
    return [
        "━" * 40,
        f"\U0001f4ca Token Usage  │  ⏱️ {elapsed:.1f}s  │  \U0001f504 {u['calls']} LLM call{'s' if u['calls'] != 1 else ''}",
        f"   Input: {u['prompt_tokens']:,} tokens (${u['input_cost']:.4f})",
        f"   Output: {u['completion_tokens']:,} tokens (${u['output_cost']:.4f})",
        f"   Total: {u['total_tokens']:,} tokens — ${u['total_cost']:.4f}",
        "━" * 40,
    ]
