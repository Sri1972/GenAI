"""
Model-tier/pricing config for Product Forge — NOT a client anymore. Actual
LLM calls go through the same shared LiteLLM-primary/Bedrock-fallback client
the rest of this platform uses (WebUIGenerator/agents/llm.py's chat()/
chat_stream_with_usage()), not a second implementation of the same thing.
This file only holds what's genuinely Product-Forge-specific: which model
tier to use for which kind of call, and the per-model dollar cost table used
to turn token counts into a cost estimate (agents/llm.py has no notion of
pricing — it only tracks token counts, via token_tracker).

Two-tier model strategy:
- DRAFT_MODEL (Haiku): Used for discussion rounds — fast and cheap
- ARTIFACT_MODEL (Sonnet): Used for final artifact generation — higher quality
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DRAFT_MODEL = os.getenv("LITELLM_HAIKU_MODEL", "claude-haiku-4-5")
ARTIFACT_MODEL = os.getenv("LITELLM_SONNET_45_MODEL", "claude-sonnet-4-5")

# Cost per 1M tokens (USD) — adjust based on your LiteLLM proxy pricing
MODEL_COSTS = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "bedrock-fallback": {"input": 3.00, "output": 15.00},
}

DEFAULT_MAX_TOKENS_DISCUSSION = 4096
DEFAULT_MAX_TOKENS_ARTIFACT = 32768
DEFAULT_MAX_TOKENS_ARTIFACT_DRAFT = 16384

# finish_reason values (OpenAI-style "length", Anthropic-style "max_tokens") that
# indicate the model was cut off before it finished — callers should continue generation.
TRUNCATION_FINISH_REASONS = {"length", "max_tokens"}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = MODEL_COSTS.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * costs["input"] / 1_000_000) + (output_tokens * costs["output"] / 1_000_000)
