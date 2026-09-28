"""
Shared subprocess wrapper around the standalone Claude Code CLI, run headlessly
against Bedrock. Every agent under ContentAgents/ calls run_claude() instead of
talking to an LLM API directly, so the "LLM step" is always the same Claude
Code CLI binary that a human would otherwise drive interactively.

Requires the CLI on PATH: npm install -g @anthropic-ai/claude-code
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

# Same Bedrock inference-profile ARNs as Agents/.claude/settings.json, so a
# headless run.py call uses the same models as an interactive session here.
BEDROCK_ENV = {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_REGION": "us-east-1",
    "AWS_PROFILE": "default",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/oonx9pzz8l4h",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/ighsdreux5fs",
}

# The standard tool set the CLI can offer. Every call explicitly allows or
# disallows all of these -- leaving any of them "unspecified" is what causes
# the CLI to stop and ask an interactive permission question in headless
# mode, which breaks JSON output (there's no TTY to answer it).
ALL_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "NotebookEdit", "Task"]

# Global model picker (mirrors TurboAppGenerator's header model picker:
# Agents/TurboAppGenerator/WebUIGenerator/agents/llm.py + API/server.py's
# /api/models routes) -- "sonnet"/"opus" are CLI model aliases that resolve
# via the ANTHROPIC_DEFAULT_SONNET_MODEL/OPUS_MODEL ARNs in BEDROCK_ENV
# above, so no new AWS setup is needed for either choice.
MODEL_CHOICES = [
    {"id": "sonnet", "label": "Claude Sonnet 5"},
    {"id": "opus", "label": "Claude Opus 5"},
]
_DEFAULT_MODEL = "sonnet"
_MODEL_SELECTION_FILE = Path(__file__).resolve().parent.parent / "model_selection.json"


def get_selected_model() -> str:
    try:
        model = json.loads(_MODEL_SELECTION_FILE.read_text(encoding="utf-8")).get("model")
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_MODEL
    return model if model in {c["id"] for c in MODEL_CHOICES} else _DEFAULT_MODEL


def set_selected_model(model: str) -> None:
    if model not in {c["id"] for c in MODEL_CHOICES}:
        raise ValueError(f"Unknown model '{model}' -- choices are {[c['id'] for c in MODEL_CHOICES]}")
    _MODEL_SELECTION_FILE.write_text(json.dumps({"model": model}), encoding="utf-8")


class ClaudeCliError(RuntimeError):
    pass


def _resolve_claude_binary() -> str:
    """Find the real claude.exe rather than the claude.cmd shim npm puts on
    PATH on Windows. subprocess-ing a .cmd file routes through cmd.exe's own
    argument re-tokenization, which mangles multi-line prompt arguments
    (our prompts are pretty-printed JSON with embedded newlines) -- the
    actual .exe, invoked directly, doesn't have that problem."""
    found = shutil.which("claude")
    if not found:
        raise ClaudeCliError(
            "`claude` CLI not found on PATH. Install with: "
            "npm install -g @anthropic-ai/claude-code"
        )
    if found.lower().endswith(".cmd"):
        npm_root = Path(found).parent
        real_exe = npm_root / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if real_exe.exists():
            return str(real_exe)
    return found


def run_claude(prompt: str, system_prompt: str | None = None,
               allowed_tools: list[str] | None = None,
               cwd: str | None = None, model: str | None = None,
               resume: str | None = None, timeout: int = 900) -> dict:
    """Run `claude -p` headlessly and return the parsed JSON result.

    allowed_tools scopes exactly which tools this call may use (e.g.
    ["Read", "Write", "Bash", "Glob"]) -- mirrors the `tools:` frontmatter of
    the matching .claude/agents/*.md subagent, so both entry points behave
    the same way. Defaults to no tools at all (pure text/JSON reasoning).
    Every other standard tool is explicitly disallowed via --disallowedTools
    so the CLI never stops to ask an interactive permission question, which
    would otherwise break headless JSON output.

    resume: a session_id from a previous run_claude() call's returned dict
    (result["session_id"]) -- continues that conversation with `prompt` as
    the next turn, remembering everything said so far. Don't pass
    system_prompt when resuming; the CLI replays the original one from the
    session automatically.
    """
    claude_bin = _resolve_claude_binary()

    allowed = allowed_tools or []
    disallowed = [t for t in ALL_TOOLS if t not in allowed]

    cmd = [claude_bin, "-p", prompt, "--output-format", "json"]
    if resume:
        cmd += ["--resume", resume]
    elif system_prompt:
        cmd += ["--system-prompt", system_prompt]
    if allowed:
        cmd += ["--allowedTools", ",".join(allowed)]
    if disallowed:
        cmd += ["--disallowedTools", ",".join(disallowed)]
    cmd += ["--model", model or get_selected_model()]

    env = {**os.environ, **BEDROCK_ENV}

    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                               text=True, encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCliError(f"claude CLI timed out after {timeout}s") from exc

    if proc.returncode != 0:
        # Some failures (e.g. an expired AWS/Bedrock credential) print nothing
        # to stderr and put the real detail on stdout instead -- include both
        # rather than raising an unhelpful "exited 1: " with no context.
        detail = proc.stderr.strip() or proc.stdout.strip() or "(no output on stdout or stderr)"
        raise ClaudeCliError(f"claude CLI exited {proc.returncode}: {detail[:2000]}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeCliError(f"claude CLI returned non-JSON output: {proc.stdout[:2000]}") from exc

    if data.get("is_error"):
        raise ClaudeCliError(f"claude CLI reported an error: {data.get('result')}")

    return data


def run_claude_text(prompt: str, **kwargs) -> str:
    """Convenience wrapper: run_claude() and return just the result text."""
    return run_claude(prompt, **kwargs)["result"]


def extract_json(text: str) -> dict | list:
    """Pull a JSON object/array out of a model response that may be wrapped
    in a ```json ... ``` fence or have leading/trailing prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start_candidates = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not start_candidates:
        raise ValueError(f"No JSON found in text: {text[:500]}")
    start = min(start_candidates)
    end = max(text.rfind("}"), text.rfind("]")) + 1
    return json.loads(text[start:end])
