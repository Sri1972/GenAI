"""
AgentSession + SessionManager — the conversational streaming layer (Phase 4).

One persistent ClaudeSDKClient per project. send_message_stream() drives the
sdk_builder flow (seed → agent build → deterministic finalize/serve → agent heal),
mapping SDK messages to SSE wire events whose shapes match the reference web client:

  start · text · tool_use · tool_result · result · done · error   (+ a phase event
  for the deterministic Python steps: install/serve/qa).

- First message on a fresh project = full generate (seed skeleton first).
- Subsequent messages = refine (same live client → re-finalize light).

Events are yielded as dicts; the FastAPI route serializes each as `data: {json}\n\n`.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Optional

from claude_agent_sdk import (
    ClaudeSDKClient, AssistantMessage, TextBlock, ThinkingBlock,
    ToolUseBlock, ToolResultBlock, UserMessage, ResultMessage, StreamEvent,
)

from . import uigen_agent as ug
from . import agent_runtime
from . import sdk_builder as sb
from . import projects as project_store
from .turboui_mcp import ProjectContext


def _origin_is_human(msg) -> bool:
    origin = getattr(msg, "origin", None)
    return origin is None or (isinstance(origin, dict) and origin.get("kind") == "human")


class AgentSession:
    """A persistent conversational session bound to one project (cwd)."""

    def __init__(self, slug: str, provider: Optional[str] = None):
        self.slug = slug
        self.provider = provider
        # slug is a routing key: legacy flat slug → web-apps/<slug>; project key
        # "<project>--<app-id>" → projects/<project>/webapp/<app-id>.
        self.project_dir = project_store.dir_for_key(slug)
        self.port: int = 0
        self.api_port: int = 0
        self.client: Optional[ClaudeSDKClient] = None
        self.session_id: Optional[str] = None
        self.mode: Optional[str] = None   # 'collaborate' | 'autopilot' — set from the first message
        self.preview_url: str = f"/app/{slug}/"
        self._lock = asyncio.Lock()
        self._started = self.project_dir.exists() and (self.project_dir / "package.json").exists()

    async def _ensure_client(self):
        if self.client is not None:
            return
        self.port, self.api_port = sb.assign_ports(self.slug)
        ctx = ProjectContext(project_name=self.slug, project_dir=self.project_dir,
                             port=self.port, api_port=self.api_port)
        opts = agent_runtime.build_options(
            ctx, provider=self.provider, resume_session_id=self.session_id, mode=self.mode
        )
        self.client = ClaudeSDKClient(opts)
        await self.client.connect()

    async def _drain(self, queue: asyncio.Queue):
        """Consume one agent turn, pushing wire events onto the queue.

        With include_partial_messages=True we get token-level StreamEvents (Claude's native
        thinking + text deltas) AND the final AssistantMessage blocks. We stream text/thinking
        from the deltas, and take only ToolUseBlocks from AssistantMessage (skipping its
        Text/Thinking blocks to avoid duplicating what the deltas already streamed).
        """
        assert self.client is not None
        async for msg in self.client.receive_response():
            if isinstance(msg, StreamEvent):
                ev = msg.event or {}
                if ev.get("type") == "content_block_delta":
                    delta = ev.get("delta") or {}
                    dt = delta.get("type")
                    if dt == "text_delta" and delta.get("text"):
                        await queue.put({"type": "text", "content": delta["text"]})
                    elif dt == "thinking_delta" and delta.get("thinking"):
                        await queue.put({"type": "thinking", "content": delta["thinking"]})
            elif isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, ToolUseBlock):
                        await queue.put({
                            "type": "tool_use", "tool_name": b.name,
                            "tool_input": b.input or {}, "tool_use_id": b.id,
                        })
                    # Text/Thinking already streamed via StreamEvent deltas above.
            elif isinstance(msg, UserMessage):
                for b in (msg.content if isinstance(msg.content, list) else []):
                    if isinstance(b, ToolResultBlock):
                        content = b.content
                        if isinstance(content, list):
                            content = "\n".join(
                                (c.get("text", "") if isinstance(c, dict) else str(c)) for c in content
                            )
                        await queue.put({
                            "type": "tool_result", "tool_use_id": b.tool_use_id,
                            "content": content, "is_error": bool(getattr(b, "is_error", False)),
                        })
            elif isinstance(msg, ResultMessage):
                if _origin_is_human(msg):
                    self.session_id = msg.session_id
                    await queue.put({
                        "type": "result", "session_id": msg.session_id,
                        "cost_usd": getattr(msg, "total_cost_usd", 0.0) or 0.0,
                        "num_turns": getattr(msg, "num_turns", None),
                    })

    async def _run_turn(self, prompt: str, queue: asyncio.Queue):
        """Send one prompt and drain its response to the queue."""
        assert self.client is not None
        await self.client.query(prompt)
        await self._drain(queue)

    async def send_message_stream(self, message: str, mode: Optional[str] = None) -> AsyncIterator[dict]:
        """One conversational turn, Claude-Code style: run the turn, live-update the preview.

        The workspace (scaffold + running Vite/API) is set up ONCE, lazily. After that every
        message is just a normal agent turn — Claude talks or edits files as it sees fit, and
        edits hot-reload into the preview. No per-message build pipeline, no forced QA.
        """
        # Mode is fixed at connect (it shapes the system prompt); adopt it from the first message.
        if self.client is None and mode:
            self.mode = mode

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _prog(s: str):  # bridge blocking progress() callbacks onto the async queue
            try:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "phase", "phase": s})
            except RuntimeError:
                pass

        async def worker():
            try:
                await queue.put({"type": "start", "project": self.slug})

                # 1) One-time workspace setup (scaffold + live Vite/API). Fast after the
                #    first-ever shared npm install; shown as a resolving setup step.
                if self.slug not in sb._PREPARED:
                    self.port, self.api_port = sb.assign_ports(self.slug)
                    await asyncio.to_thread(
                        sb.prepare_workspace, self.slug, self.port, self.api_port, _prog
                    )
                    self._started = True
                elif not self.port:
                    self.port, self.api_port = sb.assign_ports(self.slug)

                await self._ensure_client()

                # 2) The turn — Claude's native thinking/text/tools stream through. It may
                #    just talk (ask a question) or it may edit files; either way the turn
                #    ends when Claude is done and we wait for the next message.
                await self._run_turn(message, queue)

                # 3) Light sync so data changes take effect; frontend already hot-reloaded.
                await asyncio.to_thread(
                    sb.sync_workspace, self.slug, self.project_dir, self.port, self.api_port, _prog
                )

                await queue.put({"type": "app_ready", "preview_url": self.preview_url, "port": self.port})
                await queue.put({"type": "done", "session_id": self.session_id})
            except Exception as e:
                import traceback
                traceback.print_exc()
                await queue.put({"type": "error", "error": f"{type(e).__name__}: {e}"})
                await queue.put({"type": "done", "session_id": self.session_id})
            finally:
                await queue.put(None)

        async with self._lock:  # one active turn per session
            task = asyncio.create_task(worker())
            try:
                while True:
                    ev = await queue.get()
                    if ev is None:
                        break
                    yield ev
            finally:
                if not task.done():
                    task.cancel()

    async def ensure_serving(self) -> dict:
        """Bring an already-built app up (link node_modules + start Vite/API) WITHOUT running
        an agent turn, so its live preview works the moment it's reopened.

        If the project has NO real app yet (just the placeholder skeleton, or nothing), do
        nothing here — we don't spin up a throwaway server. The first chat message will
        scaffold and build it. prepare_workspace's own guard means the build path never
        wipes a real app either.
        """
        async with self._lock:
            self.port, self.api_port = sb.assign_ports(self.slug)
            if not sb._has_real_app(self.project_dir):
                return self.status()   # hasApp=False → frontend shows the "describe it" state
            if self.slug not in sb._PREPARED:
                await asyncio.to_thread(
                    sb.prepare_workspace, self.slug, self.port, self.api_port, lambda s: None
                )
                self._started = True
        return self.status()

    async def interrupt(self):
        if self.client is not None:
            try:
                await self.client.interrupt()
            except Exception:
                pass

    async def disconnect(self):
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

    def status(self) -> dict:
        running = self.slug in ug._dev_servers
        has_app = sb._has_real_app(self.project_dir)
        return {
            "project": self.slug, "sessionId": self.session_id,
            "previewUrl": self.preview_url if has_app else None,
            "port": self.port, "running": running, "started": self._started,
            "hasApp": has_app,
        }


def _refine_prompt(message: str) -> str:
    return (
        "Refine the existing app per this request. Edit only the files that need to change; "
        "keep everything else working. Do not touch managed files (vite.config.ts, package.json, "
        "tsconfig.json, src/main.tsx, api/app_server.py, api/.env, src/hooks/useApi.ts). "
        "After editing, run mcp__turboui__tsc_check and fix reported errors. Then stop.\n\n"
        f"Request: {message}"
    )


class SessionManager:
    """Registry of AgentSessions keyed by project slug."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}

    def get(self, slug: str, provider: Optional[str] = None) -> AgentSession:
        s = self._sessions.get(slug)
        if s is None:
            s = AgentSession(slug, provider=provider)
            self._sessions[slug] = s
        elif provider and s.client is None:
            # Session was pre-created (e.g. by /open) before the user picked a model;
            # adopt the provider as long as we haven't connected the client yet.
            s.provider = provider
        return s

    async def close(self, slug: str):
        s = self._sessions.pop(slug, None)
        if s is not None:
            await s.disconnect()


SESSIONS = SessionManager()
