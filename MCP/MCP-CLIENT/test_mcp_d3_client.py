"""Test client for the D3 STDIO MCP server.

This script demonstrates how to call the stdio MCP server created at
D:\GenAI\MCP\CHARTS\mcp-d3-stdio-custom\mcp_d3_stdio_server.py

It will:
- Spawn the server as a subprocess
- Send a JSON tool call (pie/bar/line)
- Read the JSON response line from the server
- Print the saved HTML path

Notes:
- This client supports an optional Claude step: if environment variable USE_CLAUDE=1
  and Anthropic client is configured, it will send a prompt to Claude and expect a JSON-first
  tool call in Claude's reply. If not configured, the client will generate a sample tool call
  directly.
"""
from __future__ import annotations
import os
import sys
import json
import subprocess
from pathlib import Path
import time
import re

try:
    import anthropic
except Exception:
    anthropic = None

from dotenv import load_dotenv
load_dotenv('.env')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
AUTO_SEND = os.getenv('LLM_AUTO_SEND', '0').lower() in ('1', 'true', 'yes')

# Optional MCP integration
try:
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except Exception:
    MCP_AVAILABLE = False

# Example templates for chart tools (used to include in system prompt)
EXAMPLE_TEMPLATES = {
    'pie': {
        "tool": "pie",
        "arguments": {
            "title": "Example Pie",
            "data": {"labels": ["A","B","C"], "datasets": [{"label":"Share","data":[10,50,40], "backgroundColor":["#1f77b4","#ff7f0e","#2ca02c"]}]}
        }
    },
    'donut': {
        "tool": "donut",
        "arguments": {"title": "Example Donut", "data": {"labels":["A","B"], "datasets":[{"label":"Share","data":[30,70]}]}}
    },
    'line': {
        "tool": "line",
        "arguments": {"title":"Example Line","data":{"labels":["Jan","Feb","Mar"],"datasets":[{"label":"Series","data":[10,20,15]}]}}
    },
    'multi_line': {
        "tool":"multi_line","arguments":{"title":"Multi Line","data":{"labels":["Jan","Feb","Mar"],"datasets":[{"label":"A","data":[5,7,6]},{"label":"B","data":[3,9,4]}]}}
    },
    'bar': {
        "tool":"bar","arguments":{"title":"Example Bar","data":{"labels":["A","B","C"],"datasets":[{"label":"Val","data":[4,6,3]}]}}
    },
    'multi_bar': {
        "tool":"multi_bar","arguments":{"title":"Multi Bar","data":{"labels":["A","B"],"datasets":[{"label":"Planned","data":[120,200]},{"label":"Actual","data":[100,180]}]}}
    },
    'stacked_bar': {
        "tool":"stacked_bar","arguments":{"title":"Stacked","data":{"labels":["Q1","Q2"],"datasets":[{"label":"Labor","data":[40,50]},{"label":"Tools","data":[10,15]}]}}
    }
}

ROOT = Path(__file__).resolve().parent
SERVER = Path('..') / 'CHARTS' / 'mcp-d3-stdio-custom' / 'mcp_d3_stdio_server.py'
SERVER = (ROOT / SERVER).resolve()

def spawn_server():
    if not SERVER.exists():
        raise FileNotFoundError(f"Server not found at {SERVER}")
    # Start the server as a child process and keep pipes open
    proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc

def send_request(proc, payload: dict, timeout=10):
    line = json.dumps(payload)
    # write the line
    try:
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
    except Exception as e:
        raise
    # Read one response line
    try:
        out = proc.stdout.readline()
        if not out:
            # try to read stderr for clues
            err = proc.stderr.read()
            raise RuntimeError(f"No response from server. Stderr: {err}")
        return json.loads(out)
    except Exception as e:
        raise

def interactive_client():
    if not anthropic:
        print("ERROR: The 'anthropic' package is not installed. Install it in your environment to use this interactive client.")
        print("You can still run the script by installing anthropic or set up the environment differently.")
        return
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not found in environment. Please set it in .env or environment variables.")
        return
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    proc = spawn_server()
    print("D3 STDIO MCP server spawned. Enter chart requests (type 'quit' to exit).")

    # Try to fetch MCP tool list/resources/prompts to provide Claude with exact tool names
    mcp_system_text = ''
    if MCP_AVAILABLE:
        try:
            # Reuse the same PMO server command used elsewhere in this repo
            server_params = StdioServerParameters(
                command="npx",
                args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"]
            )

            async def _fetch_mcp_context():
                tool_descriptions = []
                system_text_parts = []
                try:
                    async with stdio_client(server_params) as (reader, writer):
                        async with ClientSession(reader, writer) as session:
                            await session.initialize()
                            tools_result = await session.list_tools()
                            resources_result = await session.list_resources()
                            prompts_result = await session.list_prompts()
                            tools = getattr(tools_result, 'tools', [])
                            # build tool descriptions
                            for tool in tools:
                                desc = (getattr(tool, 'description', '') or '').strip().replace('\n', ' ')
                                schema = getattr(tool, 'inputSchema', None) or {}
                                props = schema.get('properties', {}) if isinstance(schema, dict) else {}
                                required = schema.get('required', []) if isinstance(schema, dict) else []
                                params = []
                                for k, v in (props.items() if isinstance(props, dict) else []):
                                    ptype = ''
                                    if isinstance(v, dict):
                                        ptype = v.get('type') or v.get('title') or ''
                                    params.append("{}{}".format(k, (' (' + str(ptype) + ')') if ptype else ''))
                                param_str = ", ".join(params) if params else "no parameters"
                                req_str = (" Required: {}.".format(', '.join(required))) if required else ""
                                tool_descriptions.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
                            system_text_parts.append("Available tools:\n" + "\n".join(tool_descriptions))

                            # resources and prompts
                            resources = getattr(resources_result, 'resources', [])
                            prompts = getattr(prompts_result, 'prompts', [])
                            for resource in resources:
                                content = getattr(resource, 'content', None) or getattr(resource, '_content', None)
                                if isinstance(content, str) and content.strip():
                                    system_text_parts.append(f"[RESOURCE - {resource.name}] {content}")
                            for prompt in prompts:
                                content = getattr(prompt, 'content', None) or getattr(prompt, '_content', None)
                                if isinstance(content, str) and content.strip():
                                    system_text_parts.append(f"[PROMPT - {prompt.name}] {content}")
                except Exception:
                    # ignore MCP errors and continue without MCP context
                    return ''
                return "\n\n".join(system_text_parts)

            try:
                mcp_system_text = asyncio.run(_fetch_mcp_context()) or ''
                if mcp_system_text:
                    print('Included MCP tool/resource context for Claude prompt (tools count may vary).')
            except Exception:
                mcp_system_text = ''
        except Exception:
            mcp_system_text = ''
    AUTO_OPEN = os.getenv('AUTO_OPEN_HTML', '0').lower() in ('1', 'true', 'yes')
    try:
        while True:
            user_query = input('\nYour chart request> ').strip()
            if not user_query:
                continue
            if user_query.lower() in ('quit', 'exit'):
                print('Exiting interactive client.')
                break
            if user_query.lower() in ('help', '?'):
                print('\nQuick usage:')
                print('- Type a plain English request (e.g. "Create a pie chart showing Project A 10%, Project B 50%, Project C 40%")')
                print("- Or paste a raw tool JSON object starting with '{' or prefix with 'json:' to send it directly to the D3 server (bypass Claude).\n  Example JSON: {\"tool\":\"pie\", \"arguments\":{\"title\":\"My Pie\", \"data\":{\"labels\":[\"A\",\"B\"],\"datasets\":[{\"label\":\"Pct\",\"data\":[10,90]}]}}}")
                continue

            # Direct JSON mode: if you paste JSON or prefix with 'json:' send directly to server
            raw_json = None
            if user_query.startswith('{') or user_query.lower().startswith('json:'):
                js = user_query
                if user_query.lower().startswith('json:'):
                    js = user_query.split(':', 1)[1].strip()
                # Support multi-line JSON pastes. If the first line doesn't parse, keep
                # reading until braces are balanced or the user finishes input (empty line or 'END').
                def is_json_balanced(s: str) -> bool:
                    depth = 0
                    in_str = False
                    esc = False
                    for ch in s:
                        if esc:
                            esc = False
                            continue
                        if ch == '\\':
                            esc = True
                            continue
                        if ch == '"':
                            in_str = not in_str
                            continue
                        if in_str:
                            continue
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                    return depth == 0 and not in_str

                def read_multiline_json(first: str) -> str:
                    buf = first
                    if is_json_balanced(buf):
                        return buf
                    print('\nDetected incomplete JSON. Paste remaining lines. Finish with an empty line or a line containing only END.')
                    while True:
                        try:
                            more = input()
                        except EOFError:
                            break
                        if more is None:
                            break
                        if more.strip() == '' or more.strip().upper() == 'END':
                            break
                        buf += '\n' + more
                        if is_json_balanced(buf):
                            break
                    return buf

                full_js = read_multiline_json(js)
                try:
                    raw_json = json.loads(full_js)
                except Exception as e:
                    print('Invalid JSON pasted:', e)
                    print('If you prefer, type a plain English request and Claude will produce the JSON-first tool call.')
                    continue
            if raw_json:
                # send directly to server
                try:
                    resp = send_request(proc, raw_json)
                except Exception as e:
                    print('Failed to send raw JSON to D3 server:', e)
                    continue
                print('\nServer response:', resp)
                if isinstance(resp, dict) and resp.get('status') == 'ok':
                    print('Saved HTML path:', resp.get('path'))
                else:
                    print('Server error or unexpected response')
                continue

            # Build a detailed system prompt including optional MCP tool schema and example JSON templates
            base_instr = (
                "You are a D3 chart generator assistant. When asked to produce a chart you MUST output a single JSON object as the very first thing in your response with the exact form: {\"tool\":\"<tool_name>\", \"arguments\": {...}}\n"
                "Requirements:\n"
                "- The JSON object must be the very first token in the assistant response and appear alone on its line (no surrounding text on that line).\n"
                "- After the JSON object you may include a short human-readable explanation, but the client will parse only the first JSON object.\n"
                "- After the JSON object, ALSO print the JSON again inside a short explanatory sentence for troubleshooting, for example:\n"
                "  {\"tool\":\"pie\", ... }\n  JSON: {\"tool\":\"pie\", ... } (This is the exact JSON used to generate the chart.)\n"
            )

            tool_list_line = 'Available tools: pie, donut, line, multi_line, bar, multi_bar, stacked_bar.'
            # include MCP-derived tool descriptions if present
            mcp_context_block = ''
            if mcp_system_text:
                mcp_context_block = "\n\nMCP server tool and resource information (useful examples and parameter shapes):\n" + mcp_system_text

            examples_text = "\n\nExample JSON templates (use the same exact JSON structure):\n"
            for k, v in EXAMPLE_TEMPLATES.items():
                examples_text += json.dumps(v, ensure_ascii=False) + "\n"

            system = base_instr + "\n" + tool_list_line + mcp_context_block + examples_text

            # Anthropic requires the user turn to be prefixed with a blank-line + 'Human:'
            # and the assistant turn typically follows with 'Assistant:'. Build the prompt
            # as: <system_instructions>\n\nHuman: <user_query>\n\nAssistant:
            prompt = system + "\n\nHuman: " + user_query + "\n\nAssistant:"

            def send_to_claude(prompt_text: str) -> str:
                # Prefer the Messages API if available, then chat, then completions
                # Normalize returned assistant text for downstream parsing.
                # Don't print the full prompt here to avoid leaking secrets.
                # 1) messages.create (preferred newer API)
                try:
                    messages_api = getattr(client, 'messages', None)
                    if messages_api is not None and hasattr(messages_api, 'create'):
                        # Anthropic messages.create often expects 'input' as array or string
                        try:
                            res = messages_api.create(model=CLAUDE_MODEL, input=[{"role":"system","content":""}, {"role":"user","content":prompt_text}])
                        except TypeError:
                            # some SDKs take 'messages' argument
                            res = messages_api.create(model=CLAUDE_MODEL, messages=[{"role":"system","content":""}, {"role":"user","content":prompt_text}])
                        # extract assistant text
                        if isinstance(res, dict):
                            # common shapes
                            if res.get('completion'):
                                return res.get('completion')
                            choices = res.get('choices') or []
                            if choices:
                                c0 = choices[0]
                                msg = c0.get('message') or c0.get('delta') or {}
                                if isinstance(msg, dict):
                                    return msg.get('content') or c0.get('text') or ''
                        return getattr(res, 'completion', None) or getattr(res, 'text', None) or ''
                except Exception:
                    pass

                # 2) chat.completions.create
                try:
                    chat = getattr(client, 'chat', None)
                    if chat is not None and hasattr(chat, 'completions'):
                        try:
                            res = chat.completions.create(model=CLAUDE_MODEL, messages=[{"role":"system","content":""}, {"role":"user","content":prompt_text}])
                        except TypeError:
                            res = chat.completions.create(model=CLAUDE_MODEL, input=prompt_text)
                        if isinstance(res, dict):
                            if res.get('completion'):
                                return res.get('completion')
                            choices = res.get('choices') or []
                            if choices:
                                c0 = choices[0]
                                msg = c0.get('message') or c0.get('delta') or {}
                                if isinstance(msg, dict):
                                    return msg.get('content') or c0.get('text') or ''
                        return getattr(res, 'completion', None) or getattr(res, 'text', None) or ''
                except Exception:
                    pass

                # 2) Legacy completions API (older SDKs)
                try:
                    res = client.completions.create(model=CLAUDE_MODEL, prompt=prompt_text, max_tokens_to_sample=8000)
                    return getattr(res, 'completion', None) or (res.get('completion') if isinstance(res, dict) else '') or getattr(res, 'text', None) or ''
                except Exception as e:
                    # If the error message suggests using the Messages API, try alternate chat methods
                    msg = str(e)
                    if 'Please use the Messages API' in msg or 'not supported on this API' in msg or 'Messages API' in msg:
                        # Try other common SDK entrypoints for chat/messages
                        try:
                            # Try messages.create again with alternative args
                            messages_api = getattr(client, 'messages', None)
                            if messages_api is not None and hasattr(messages_api, 'create'):
                                try:
                                    r3 = messages_api.create(model=CLAUDE_MODEL, input=[{"role":"user","content":prompt_text}])
                                except TypeError:
                                    r3 = messages_api.create(model=CLAUDE_MODEL, messages=[{"role":"user","content":prompt_text}])
                                if isinstance(r3, dict):
                                    choices = r3.get('choices') or []
                                    if choices:
                                        c0 = choices[0]
                                        return c0.get('message', {}).get('content') or c0.get('text') or ''
                                return getattr(r3, 'text', '') or getattr(r3, 'completion', '') or ''
                        except Exception:
                            pass
                    # re-raise if nothing worked
                    raise

            try:
                assistant_text = send_to_claude(prompt)
            except Exception as e:
                # If the Anthropic error explicitly suggests using the Messages API,
                # surface a helpful hint and fall back to local parsing rather than
                # repeatedly failing. This helps when the configured CLAUDE_MODEL is
                # not compatible with the legacy completions endpoint.
                msg = str(e)
                if 'Please use the Messages API' in msg or 'not supported on this API' in msg or 'Messages API' in msg:
                    print('Anthropic request failed with a model/API compatibility error:')
                    print(msg)
                    print('\nHint: your configured CLAUDE_MODEL or Anthropic SDK may require using the Messages API (update CLAUDE_MODEL to a messages-compatible model or ensure your SDK supports messages).')
                    print('Falling back to local natural-language parsing for simple percentage lists. You can also paste raw JSON directly.')
                    # fall through to local parse flow by setting assistant_text to '' so parsed_local may run
                    assistant_text = ''
                else:
                    print('Anthropic request failed:', e)
                    print('You can retry or type a simpler query.')
                    continue

            # extract first JSON object from assistant_text
            def extract_first_json(s: str):
                start = s.find('{')
                if start == -1:
                    return None
                depth = 0
                for i in range(start, len(s)):
                    if s[i] == '{':
                        depth += 1
                    elif s[i] == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(s[start:i+1])
                            except Exception:
                                try:
                                    cand = s[start:i+1]
                                    cand = re.sub(r',\s*(?=[\]}])', '', cand)
                                    return json.loads(cand)
                                except Exception:
                                    return None
                return None

            parsed = extract_first_json(assistant_text or '')
            if not parsed:
                # Try a local natural-language parser as a fallback for simple patterns like
                # "Project A - 10%, Project B - 50% and Project C - 40%"
                def parse_nl_to_payload(text: str):
                    # find label-number pairs where number may have % sign
                    pairs = re.findall(r"([A-Za-z0-9 &'\-_.]+?)\s*[-:\u2013]?\s*([0-9]+(?:\.[0-9]+)?)\s*%", text)
                    if not pairs:
                        # try alternative pattern: 'A 10% B 20%'
                        pairs = re.findall(r"([A-Za-z0-9 &'\-_.]+?)\s+([0-9]+(?:\.[0-9]+)?)\s*%", text)
                    if not pairs:
                        return None
                    labels = [p[0].strip() for p in pairs]
                    values = []
                    for p in pairs:
                        try:
                            values.append(float(p[1]))
                        except Exception:
                            values.append(0.0)
                    # build a pie payload
                    payload = {
                        "tool": "pie",
                        "arguments": {
                            "title": "Parsed Pie",
                            "data": {
                                "labels": labels,
                                "datasets": [{"label": "Value", "data": values}]
                            }
                        }
                    }
                    return payload

                parsed_local = parse_nl_to_payload(user_query or assistant_text or '')
                if parsed_local:
                    print('\nCould not parse JSON from Claude; inferred this payload from your text:')
                    print(json.dumps(parsed_local, indent=2, ensure_ascii=False))
                    confirm2 = input('\nSend this to D3 server? (y/n) ').strip().lower()
                    if confirm2 in ('y', 'yes') or AUTO_SEND:
                        try:
                            resp = send_request(proc, parsed_local)
                        except Exception as e:
                            print('Failed to send parsed payload to D3 server:', e)
                            continue
                        print('\nServer response:', resp)
                        if isinstance(resp, dict) and resp.get('status') == 'ok':
                            path = resp.get('path')
                            print('Saved HTML path:', path)
                            if AUTO_OPEN:
                                try:
                                    os.startfile(path)
                                except Exception:
                                    try:
                                        subprocess.Popen(['cmd', '/c', 'start', path], shell=True)
                                    except Exception:
                                        pass
                        else:
                            print('Server error or unexpected response')
                        continue
                print('\nClaude did not return a parsable JSON-first tool object. Here is Claude output for inspection:\n')
                print(assistant_text)
                print('\nPlease adjust your request or try again, or paste JSON directly.')
                continue

            # show parsed JSON and ask for confirmation before sending to D3 server
            print('\nParsed JSON tool object:')
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
            if not AUTO_SEND:
                confirm = input('\nSend this to D3 server? (y/n) ').strip().lower()
                if confirm not in ('y', 'yes'):
                    print('Aborted sending to server. You can edit your request and try again.')
                    continue
            else:
                print('AUTO_SEND is enabled — sending without confirmation')
                # If AUTO_SEND is enabled, skip confirmation
                if AUTO_SEND:
                    print('AUTO_SEND enabled: sending without manual confirmation')

            # Ensure parsed looks like a tool call
            if not isinstance(parsed, dict) or 'tool' not in parsed:
                print('Parsed JSON does not look like a tool call:', parsed)
                print('Claude output:\n', assistant_text)
                continue

            # Forward to D3 server
            try:
                resp = send_request(proc, parsed)
            except Exception as e:
                print('Failed to send request to D3 server:', e)
                continue

            print('\nServer response:', resp)
            if isinstance(resp, dict) and resp.get('status') == 'ok':
                path = resp.get('path')
                print('Saved HTML path:', path)
                if AUTO_OPEN:
                    try:
                        os.startfile(path)
                    except Exception:
                        try:
                            subprocess.Popen(['cmd', '/c', 'start', path], shell=True)
                        except Exception:
                            pass
            else:
                print('Server error or unexpected response')
    finally:
        try:
            proc.kill()
        except Exception:
            pass

if __name__ == '__main__':
    interactive_client()
