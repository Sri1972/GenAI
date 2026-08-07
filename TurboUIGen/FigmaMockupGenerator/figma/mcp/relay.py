#!/usr/bin/env python3
"""
Figma Relay Agent
=================
Runs on the user's LOCAL machine. Acts as a bridge in the chain:

    LLM / Claude
        ↓  HTTP POST (JSON-RPC 2.0)      ← this IS the MCP protocol
    server.py  on port 7771
        ↓  WebSocket /relay              ← internal pipe, NOT the MCP endpoint
    relay.py   (this file, on your laptop)
        ↓  stdio (stdin/stdout)
    figma-console-mcp  (npm, auto-started)
        ↓  WebSocket port 9223
    Figma Desktop Bridge plugin
        ↓
    Figma Desktop

Two different protocols are in play — don't confuse them:

  HTTP POST http://localhost:7771/mcp    ← the MCP endpoint (what LLMs call)
  WebSocket ws://localhost:7771/relay   ← internal pipe between server.py and relay.py

The --server argument below refers to the INTERNAL WebSocket pipe, not the MCP endpoint.
You only ever need to change --server if server.py is deployed to AWS instead of localhost.

Usage:
    # Default — server.py running locally on port 7771
    python relay.py

    # server.py deployed to AWS
    python relay.py --server ws://your-aws-server.com/relay

Start order:
    1. python server.py          (MCP server — can run on AWS or locally)
    2. python relay.py           (this file — MUST run on laptop with Figma open)
    3. Figma Desktop → Plugins → Development → Figma Desktop Bridge → Run
       Wait for "Local Ready" in the plugin panel
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import os
import time
from pathlib import Path

import websockets
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("figma-relay")

NODE_PATH = r"C:\Program Files\nodejs"
NPX_CMD   = os.path.join(NODE_PATH, "npx.cmd")


# ── figma-console-mcp process manager ────────────────────────────────────────

class FigmaBridge:
    """
    Manages figma-console-mcp via its stdio MCP transport.

    figma-console-mcp exposes TWO interfaces:
      - stdio (stdin/stdout): the MCP interface — THIS is where we send JSON-RPC commands
      - WebSocket on port 9223: for the Figma Desktop Bridge PLUGIN to connect to (not for us)
    """

    def __init__(self):
        self._proc      = None
        self._tool_name = "figma_execute"
        self._req_lock  = asyncio.Lock()   # one in-flight call at a time over stdio

    def start_mcp_process(self):
        """Start figma-console-mcp as a subprocess, communicating via stdio."""
        # Kill stale node processes on ports 9223-9232
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Get-NetTCPConnection -LocalPort (9223..9232) -State Listen -ErrorAction SilentlyContinue "
                 "| Select-Object -ExpandProperty OwningProcess "
                 "| ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"],
                capture_output=True, timeout=8,
            )
        except Exception:
            pass

        env = {**os.environ,
               "PATH": NODE_PATH + os.pathsep + os.environ.get("PATH", ""),
               "FIGMA_ACCESS_TOKEN": os.environ.get("FIGMA_ACCESS_TOKEN", ""),
               "ENABLE_MCP_APPS": "true"}

        self._proc = subprocess.Popen(
            [NPX_CMD, "-y", "figma-console-mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # separate stderr so we don't mix with JSON-RPC stdout
            text=True, encoding="utf-8", errors="replace",
            bufsize=0, env=env,
        )
        log.info(f"figma-console-mcp PID: {self._proc.pid}")

        # Patch manifest for prototype / setReactionsAsync support
        time.sleep(3)
        manifest_path = Path.home() / ".figma-console-mcp" / "plugin" / "manifest.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                if m.get("documentAccess") == "dynamic-page":
                    m["documentAccess"] = "dynamic-page-requires-explicit-load"
                    manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")
                    log.info("Patched plugin manifest for prototype support")
            except Exception as e:
                log.warning(f"Manifest patch failed: {e}")

    def _send_stdio(self, msg: dict):
        """Write a JSON-RPC message to figma-console-mcp stdin."""
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

    def _recv_stdio(self, timeout: float = 15.0) -> dict:
        """Read the next JSON-RPC line from figma-console-mcp stdout (blocking)."""
        import threading
        result = {}
        exc_holder = []

        def read():
            try:
                while True:
                    line = self._proc.stdout.readline()
                    if not line:
                        exc_holder.append(EOFError("figma-console-mcp stdout closed"))
                        return
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        result.update(json.loads(line))
                        return
                    except json.JSONDecodeError:
                        log.debug(f"non-JSON stdout: {line[:120]}")
            except Exception as e:
                exc_holder.append(e)

        t = threading.Thread(target=read, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError("Timed out reading from figma-console-mcp stdout")
        if exc_holder:
            raise exc_holder[0]
        return result

    def initialize(self):
        """Perform MCP handshake over stdio and discover the execute tool name."""
        # initialize
        self._send_stdio({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "figma-relay", "version": "1.0.0"},
            },
        })
        resp = self._recv_stdio(timeout=15)
        log.info(f"figma-console-mcp serverInfo: {resp.get('result', {}).get('serverInfo', {})}")

        # notifications/initialized (no response expected)
        self._send_stdio({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # discover tools
        self._send_stdio({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        resp2 = self._recv_stdio(timeout=10)
        tools = resp2.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        log.info(f"figma-console-mcp tools: {tool_names}")

        # Find the code-execution tool — prefer names containing "exec" or "run"
        execute_candidates = [n for n in tool_names if any(k in n.lower() for k in ("exec", "run", "eval", "code"))]
        if execute_candidates:
            self._tool_name = execute_candidates[0]
        elif tool_names:
            self._tool_name = tool_names[0]

        log.info(f"Using execute tool: {self._tool_name}")

    def _call_tool_sync(self, tool_name: str, arguments: dict, recv_timeout: float = 30.0) -> dict:
        """Call any figma-console-mcp tool synchronously and return the parsed result."""
        req_id = int(time.time() * 1000) % 100000
        self._send_stdio({
            "jsonrpc": "2.0", "id": req_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        deadline = time.time() + recv_timeout
        while time.time() < deadline:
            try:
                resp = self._recv_stdio(timeout=min(5.0, deadline - time.time()))
            except TimeoutError:
                continue
            except Exception as e:
                return {"error": str(e)}
            if resp.get("id") == req_id:
                result = resp.get("result", {})
                content = result.get("content", [])
                if content:
                    text = content[0].get("text", "")
                    if text:
                        try:
                            return json.loads(text)
                        except Exception:
                            return {"result": text}
                return result
        return {"error": f"Timed out calling {tool_name}"}

    async def execute_code(self, code: str) -> dict:
        """
        Execute JS in Figma via figma-console-mcp.

        figma-console-mcp's figma_execute tool DISCARDS the JS return value —
        it only reports {success: true}. To get data back we:
          1. Wrap the JS to write output via console.log with a unique marker
          2. After execution succeeds, call figma_get_console_logs to read it back
          3. Parse the last log entry matching our marker as the result
        """
        async with self._req_lock:
            marker = f"__MCP_{int(time.time()*1000)%999999}__"

            # figma-console-mcp discards return values — we use console.log with a
            # unique marker to smuggle the result back through the log stream.
            # The generated code already starts with (async () => { ... return X; })()
            # We replace the outer IIFE so console.log captures the return value.
            import re as _re
            # Strip the outer (async () => { ... })(); wrapper if present
            inner = code.strip()
            m = _re.match(r'^\(async\s*\(\)\s*=>\s*\{(.*)\}\)\(\)\s*;?\s*$', inner, _re.DOTALL)
            inner_body = m.group(1).strip() if m else inner

            wrapped_code = f"""
(async () => {{
  try {{
    var __r;
    __r = await (async () => {{
      {inner_body}
    }})();
    var __out = __r !== undefined ? (typeof __r === 'string' ? __r : JSON.stringify(__r)) : JSON.stringify({{ok:true}});
    console.log('{marker}' + __out);
  }} catch(__e) {{
    console.log('{marker}' + JSON.stringify({{error: __e && __e.message ? __e.message : String(__e)}}));
  }}
}})();
""".strip()

            loop = asyncio.get_event_loop()

            # Step 1: execute the code
            exec_result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self._call_tool_sync(
                    self._tool_name, {"code": wrapped_code}, recv_timeout=35.0
                )),
                timeout=40.0,
            )

            # Check execution succeeded
            success = exec_result.get("success", False) if isinstance(exec_result, dict) else False
            if not success and isinstance(exec_result, dict) and exec_result.get("error"):
                return exec_result

            # Step 2: read console logs directly from figma-console-mcp via stdio
            # figma_get_console_logs is a figma-console-mcp tool, not our MCP server
            await asyncio.sleep(0.5)  # let Figma flush logs
            logs_result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self._call_tool_sync(
                    "figma_get_console_logs", {"limit": 20, "clear": False}, recv_timeout=10.0
                )),
                timeout=15.0,
            )
            log.debug(f"console logs result keys: {list(logs_result.keys()) if isinstance(logs_result, dict) else type(logs_result)}")

            # figma-console-mcp returns logs in various shapes — search all of them
            def extract_log_strings(obj) -> list:
                if isinstance(obj, list):
                    result = []
                    for item in obj:
                        if isinstance(item, str):
                            result.append(item)
                        elif isinstance(item, dict):
                            for k in ("message", "text", "content", "log", "value"):
                                if k in item and isinstance(item[k], str):
                                    result.append(item[k])
                    return result
                if isinstance(obj, dict):
                    for k in ("logs", "messages", "entries", "data", "content"):
                        if k in obj:
                            return extract_log_strings(obj[k])
                return []

            log_strings = extract_log_strings(logs_result)
            log.debug(f"extracted {len(log_strings)} log strings")

            # Search for our marker (newest first)
            for entry_str in reversed(log_strings):
                if marker in entry_str:
                    value_str = entry_str.split(marker, 1)[1].strip()
                    try:
                        return json.loads(value_str)
                    except Exception:
                        return {"result": value_str}

            # No marker found — fine for fire-and-forget ops (setReactionsAsync)
            log.debug(f"No marker in logs. logs_result sample: {str(logs_result)[:300]}")
            return {"ok": True, "note": "executed silently"}

    def stop(self):
        if self._proc:
            self._proc.terminate()
            self._proc = None


# ── Main relay loop ───────────────────────────────────────────────────────────

async def run_relay(mcp_server_url: str):
    bridge = FigmaBridge()

    # Start figma-console-mcp
    log.info("Starting figma-console-mcp…")
    bridge.start_mcp_process()

    # Handshake over stdio
    log.info("Initialising figma-console-mcp over stdio…")
    try:
        bridge.initialize()
    except Exception as e:
        log.error(f"figma-console-mcp init failed: {e}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Figma Relay ready!")
    print(f"  figma-console-mcp: ready (stdio)")
    print(f"  MCP server: {mcp_server_url}")
    print()
    print(f"  ACTION REQUIRED:")
    print(f"    Open Figma Desktop → Plugins → Development → Figma Desktop Bridge → Run")
    print(f"    Wait for 'Local Ready'")
    print(f"{'='*60}\n")

    # Connect to MCP server and relay commands
    reconnect_delay = 1
    while True:
        try:
            log.info(f"Connecting to MCP server: {mcp_server_url}")
            async with websockets.connect(mcp_server_url, ping_interval=20) as ws:
                log.info("Connected to MCP server — relay is active")
                reconnect_delay = 1

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type")
                    req_id   = msg.get("id")
                    code     = msg.get("code", "")

                    if msg_type == "execute" and code:
                        log.info(f"Executing in Figma (req {req_id[:8]}…)")
                        try:
                            result = await bridge.execute_code(code)
                        except Exception as ex:
                            log.error(f"execute_code error: {ex}")
                            result = {"error": str(ex)}
                        await ws.send(json.dumps({
                            "type": "result",
                            "id": req_id,
                            "result": result,
                        }))
                        log.info(f"Result sent for req {req_id[:8]}")

        except (websockets.exceptions.ConnectionClosed,
                ConnectionRefusedError, OSError) as e:
            log.warning(f"MCP server disconnected ({e}). Retrying in {reconnect_delay}s…")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)
        except Exception as e:
            log.error(f"Relay error: {e}")
            await asyncio.sleep(reconnect_delay)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Figma Relay Agent")
    parser.add_argument("--server", default="ws://localhost:7771/relay",
                        help="MCP server WebSocket URL (default: ws://localhost:7771/relay)")
    args = parser.parse_args()

    try:
        asyncio.run(run_relay(args.server))
    except KeyboardInterrupt:
        print("\nRelay stopped.")
