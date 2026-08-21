"""
Model-routing environment for the Claude Agent SDK-spawned Claude Code CLI.

The SDK spawns the `claude` CLI as a subprocess; it is configured entirely via
environment variables (there is no in-code base_url like the openai/anthropic
clients in llm.py / sdk_client.py). This module produces the env dict passed to
`ClaudeAgentOptions.env` for one of three SELECTABLE providers:

  litellm : route through the corporate LiteLLM proxy (ANTHROPIC_BASE_URL +
            ANTHROPIC_AUTH_TOKEN, corporate CA via NODE_EXTRA_CA_CERTS).
  bedrock : AWS Bedrock inference profile (CLAUDE_CODE_USE_BEDROCK=1 + AWS creds).
  local   : the CLI's own auth — the user's ~/.claude login or ambient
            ANTHROPIC_API_KEY. We deliberately override NOTHING so the CLI uses
            whatever it is already authenticated with.

Selection order: explicit arg > TURBOUI_MODEL_PROVIDER env > default "litellm".

Notes:
  - ANTHROPIC_BASE_URL is the LiteLLM base VERBATIM (no `/v1` suffix — that suffix
    in llm.py is an OpenAI-compat artifact; sdk_client.py's Anthropic client already
    uses the bare base).
  - The corporate CA cert lives in LITELLM_SSL_CERT as PEM-in-env with escaped `\n`.
    Node (the CLI runtime) cannot read PEM-from-env — it only trusts a FILE via
    NODE_EXTRA_CA_CERTS. So we materialize the PEM to a temp file once.
"""

from __future__ import annotations

import functools
import os
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "")
LITELLM_SSL_CERT = os.environ.get("LITELLM_SSL_CERT", "")
LITELLM_MODEL = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")
# Small/fast model the CLI uses for background tasks (title-gen, etc.). Route it through
# the proxy too, else the CLI's default haiku name may not be a valid proxy deployment.
LITELLM_SMALL_MODEL = os.environ.get("LITELLM_HAIKU_MODEL", "claude-haiku-4-5")

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/ighsdreux5fs",
)
# Optional Bedrock haiku inference-profile ARN/id for background tasks. If unset, the CLI
# uses its own Bedrock small-model default (needs account model access).
BEDROCK_SMALL_MODEL = os.environ.get("BEDROCK_SMALL_FAST_MODEL", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")

# For "local" provider: the builder uses Sonnet by default (fast + excellent at code
# generation; the local Claude Code default is often Opus, which is much slower for bulk
# work like seed data). Override with TURBOUI_LOCAL_MODEL (e.g. "opus" or a full id).
LOCAL_MODEL = os.environ.get("TURBOUI_LOCAL_MODEL", "sonnet")

VALID_PROVIDERS = ("litellm", "bedrock", "local")
# Default provider. `local` = use the machine's own ~/.claude auth (no corporate creds needed).
DEFAULT_PROVIDER = os.environ.get("TURBOUI_MODEL_PROVIDER", "local").lower()

# Telemetry / auto-update knobs kept off for the corporate-network CLI subprocess.
_QUIET_ENV = {
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_AUTOUPDATER": "1",
}


@functools.lru_cache(maxsize=1)
def ca_cert_path() -> Optional[str]:
    """Materialize LITELLM_SSL_CERT (PEM-in-env, escaped \\n) to a temp .pem file.

    Returns the file path, or None if no cert is configured. Cached so the file is
    written once per process. Reuses the un-escape transform from llm._get_ssl_context.
    """
    pem = LITELLM_SSL_CERT
    if not pem:
        return None
    fh = tempfile.NamedTemporaryFile(
        "w", prefix="turboui-litellm-ca-", suffix=".pem", delete=False, encoding="utf-8"
    )
    fh.write(pem.replace("\\n", "\n"))
    fh.close()
    return fh.name


def litellm_cli_env() -> dict[str, str]:
    """Env for the CLI to route through the LiteLLM proxy (primary path)."""
    if not LITELLM_API_BASE:
        raise ValueError(
            "Model provider 'litellm' selected but LITELLM_API_BASE is not set. "
            "Add it to .env, or select provider 'bedrock' / 'local' "
            "(TURBOUI_MODEL_PROVIDER)."
        )
    env: dict[str, str] = {
        "ANTHROPIC_BASE_URL": LITELLM_API_BASE.rstrip("/"),  # verbatim, no /v1
        "ANTHROPIC_AUTH_TOKEN": LITELLM_API_KEY,  # bearer token, NOT ANTHROPIC_API_KEY
        "ANTHROPIC_MODEL": LITELLM_MODEL,
        "ANTHROPIC_SMALL_FAST_MODEL": LITELLM_SMALL_MODEL,
        **_QUIET_ENV,
    }
    cert = ca_cert_path()
    if cert:
        env["NODE_EXTRA_CA_CERTS"] = cert
    return env


def bedrock_cli_env() -> dict[str, str]:
    """Env for the CLI to route through AWS Bedrock (sticky fallback path).

    The CLI has no built-in proxy->Bedrock switch; the AgentSession wrapper flips to
    this at the connect() boundary on CLIConnectionError/ProcessError.
    """
    env: dict[str, str] = {
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "AWS_REGION": AWS_REGION,
        "AWS_PROFILE": AWS_PROFILE,
        "ANTHROPIC_MODEL": BEDROCK_MODEL_ID,  # application-inference-profile ARN
        **_QUIET_ENV,
    }
    if BEDROCK_SMALL_MODEL:
        env["ANTHROPIC_SMALL_FAST_MODEL"] = BEDROCK_SMALL_MODEL
    # Some corporate networks also front Bedrock TLS through the same proxy CA.
    cert = ca_cert_path()
    if cert:
        env["NODE_EXTRA_CA_CERTS"] = cert
    return env


def local_cli_env() -> dict[str, str]:
    """Env for the CLI to use its OWN local auth (~/.claude login or ambient ANTHROPIC_API_KEY).

    We override nothing about routing/auth — only the quiet flags — so the CLI behaves
    exactly as a normal interactive `claude` session on this machine.
    """
    return dict(_QUIET_ENV)


# ── Provider selection ────────────────────────────────────────────────────────

def resolve_provider(explicit: Optional[str] = None) -> str:
    """explicit arg > TURBOUI_MODEL_PROVIDER env > 'litellm'. Raises on unknown value."""
    p = (explicit or DEFAULT_PROVIDER or "litellm").lower()
    if p not in VALID_PROVIDERS:
        raise ValueError(f"Unknown model provider {p!r}; expected one of {VALID_PROVIDERS}")
    return p


def cli_env_for(provider: Optional[str] = None) -> dict[str, str]:
    """Return the ClaudeAgentOptions.env dict for the selected provider."""
    p = resolve_provider(provider)
    return {"litellm": litellm_cli_env, "bedrock": bedrock_cli_env, "local": local_cli_env}[p]()


def model_for(provider: Optional[str] = None) -> Optional[str]:
    """Model id for the selected provider, or None (let the CLI default) for local w/o override."""
    p = resolve_provider(provider)
    if p == "litellm":
        return LITELLM_MODEL
    if p == "bedrock":
        return BEDROCK_MODEL_ID
    return LOCAL_MODEL or None  # local: only set a model if the user overrode it


def default_model() -> str:
    return LITELLM_MODEL
