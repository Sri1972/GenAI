from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv

import json
import anthropic
import re

# Added imports required by functions later in this module
import sys
import hashlib
import subprocess
import urllib.request
import shutil
from pathlib import Path
from datetime import datetime
import uuid
import argparse
import shutil
import webbrowser

# Load environment variables
load_dotenv('.env')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')  # Put your Claude API key in .env

# Initialize Anthropic client and model default at module level so it's always defined
try:
    claude = anthropic.Anthropic(api_key=anthropic_api_key)
except Exception:
    claude = None
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# Short-lived in-process chat memory
chat_memories = {}
MEMORY_MAX_MESSAGES = 200
# Directory to store per-chat memory JSON files
CHAT_MEMORY_DIR = Path(__file__).resolve().parent / 'chat_memory'


def ensure_memory_dir():
    try:
        CHAT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def memory_file_for(chat_id: str) -> Path:
    # sanitize chat_id for filename
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', chat_id)[:64]
    ensure_memory_dir()
    return CHAT_MEMORY_DIR / f"{safe}.json"


def load_chat_memory(chat_id: str):
    """Load persisted chat memory for chat_id into the in-process chat_memories dict.
    Returns the loaded list (may be empty)"""
    path = memory_file_for(chat_id)
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    chat_memories[chat_id] = data[-MEMORY_MAX_MESSAGES:]
                    return chat_memories[chat_id]
        except Exception as e:
            print(f"Failed to load chat memory for {chat_id}: {e}")
    # ensure key exists
    chat_memories.setdefault(chat_id, [])
    return chat_memories[chat_id]


def save_chat_memory(chat_id: str, messages):
    """Atomically save the provided messages list for chat_id to disk."""
    path = memory_file_for(chat_id)
    try:
        tmp = path.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(messages[-MEMORY_MAX_MESSAGES:], f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        try:
            tmp.replace(path)
        except Exception:
            # fallback to move
            os.replace(str(tmp), str(path))
    except Exception as e:
        print(f"Failed to save chat memory for {chat_id}: {e}")


def set_chat_memory(chat_id: str, messages):
    """Assign into in-memory store and persist to disk."""
    chat_memories[chat_id] = messages[-MEMORY_MAX_MESSAGES:]
    try:
        save_chat_memory(chat_id, chat_memories[chat_id])
    except Exception:
        pass

server_params = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"]
)


def forward_chart_json_to_d3(chart_payload: dict, timeout: int = 30) -> str | None:
    """Spawn the D3 STDIO server and forward a chart JSON payload to it. Returns saved HTML path or None."""
    try:
        d3_server = Path(__file__).resolve().parents[1] / 'CHARTS' / 'mcp-d3-stdio-custom' / 'mcp_d3_stdio_server.py'
        if not d3_server.exists():
            print('D3 server not found at', d3_server)
            return None
        proc = subprocess.Popen([sys.executable, str(d3_server)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc.stdin.write(json.dumps(chart_payload) + "\n")
            proc.stdin.flush()
            out = proc.stdout.readline()
            if not out:
                err = proc.stderr.read()
                print('D3 server no response:', err)
                return None
            try:
                resp = json.loads(out)
            except Exception:
                print('D3 server returned non-JSON:', out)
                return None
            if isinstance(resp, dict) and resp.get('status') == 'ok':
                return resp.get('path')
            print('D3 server returned error:', resp)
            return None
        finally:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception as e:
        print('Error forwarding to D3 server:', e)
        return None


def move_chart_to_client(server_path: str | Path, chart_type: str = 'chart', query_hint: str | None = None) -> str | None:
    """Move server-saved HTML into the client's html-charts directory with a meaningful name.
    Filename format: <chart_type>_<query_hint>_<YYYYmmdd_HHMMSS>_<hex>.html
    Returns the new path string or None on failure."""
    try:
        server_p = Path(server_path)
        if not server_p.exists():
            return None
        outdir = Path(__file__).resolve().parent / 'html-charts'
        outdir.mkdir(parents=True, exist_ok=True)
        # sanitize chart_type and query_hint
        ct = (chart_type or 'chart')
        ct = re.sub(r'[^A-Za-z0-9_-]', '_', str(ct))[:40]
        qh = (query_hint or '')
        qh = re.sub(r'[^A-Za-z0-9_-]', '_', str(qh))[:40] if qh else 'query'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        h = hashlib.sha1((str(server_p) + ts).encode('utf-8')).hexdigest()[:6]
        filename = f"{ct}_{qh}_{ts}_{h}.html"
        dest = outdir / filename
        try:
            # Use shutil.move so the file is removed from the server folder (no duplicate)
            shutil.move(str(server_p), str(dest))
        except Exception:
            # fallback: copy then remove original
            try:
                shutil.copyfile(str(server_p), str(dest))
                try:
                    server_p.unlink()
                except Exception:
                    pass
            except Exception as e:
                print('Failed to move/copy chart into client html-charts:', e)
                return None
        return str(dest)
    except Exception as e:
        print('Failed to move chart into client html-charts:', e)
        return None


def move_and_open_chart(server_path: str | Path, chart_type: str = 'chart', query_hint: str | None = None) -> str | None:
    """Move server-saved HTML into client's html-charts and open it in the default browser."""
    moved = move_chart_to_client(server_path, chart_type=chart_type, query_hint=query_hint)
    if not moved:
        return None
    # Try platform-open: on Windows use os.startfile, fallback to webbrowser
    try:
        if os.name == 'nt':
            os.startfile(moved)
        else:
            webbrowser.open_new_tab(Path(moved).as_uri())
    except Exception:
        try:
            webbrowser.open_new_tab(Path(moved).as_uri())
        except Exception:
            pass
    return moved

async def run(query: str, chat_id: str = "default"):
    try:
        print("🚀 Starting stdio_client to MCP server...")
        async with stdio_client(server_params) as (reader, writer):
            print("✅ Connected to PMO MCP server")
            async with ClientSession(reader, writer) as session:
                print("🔧 Initializing MCP session...")
                await session.initialize()
                print("✅ MCP session initialized")

                # Tool listing
                tools_result = await session.list_tools()
                print("Available tools:", tools_result)

                # Build a rich, structured description of available tools including parameter names/types
                tool_lines = []
                for tool in tools_result.tools:
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
                    tool_lines.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
                tool_descriptions = "\n".join(tool_lines)

                system_instructions = (
                    "You are a PMO assistant connected to a PMO MCP server.\n"
                    "Rules:\n"
                    "- For any question requiring factual project or resource data, you MUST return a JSON tool call as the very first thing in your response.\n"
                    "- If the user request requires more than one MCP tool call (for example: data for multiple resource ids, or multiple independent time ranges), you MUST return a JSON object whose first property is 'plan' and whose value is a list of step objects. Each step object must include an 'id' (short string), 'tool' (tool name), and 'arguments' (object). Do NOT put any explanatory text before the JSON plan.\n"
                    "- The JSON must be a single object in this exact form with no leading text: {\"tool\":\"<tool_name>\", \"arguments\": {...}} or when multiple steps are required: {\"plan\": [{\"id\":\"s1\", \"tool\":\"<tool_name>\", \"arguments\": {...}}, ...]}\n"
                    "- If clarification is required, ask a short clarifying question instead of guessing data.\n\n"
                    "- Important: Treat each user data-request as independent by default. For queries that request fresh data (for example: resource ids, monthly intervals, date ranges, or explicit 'list' requests), do NOT reuse tool outputs from previous unrelated queries unless the user explicitly asks you to 'reuse previous results'. Always plan and fetch the required data anew.\n\n"
                    "Available tools and their parameters:\n"
                ) + tool_descriptions + (
                    "\n\nExamples (when data is needed, respond exactly with the JSON object first):\n"
                    "User: \"List all projects in the PMO system.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_all_projects\",\"arguments\":{}}\n\n"
                    "If a user asks for data that requires multiple independent MCP calls (for example: 'Give me monthly hours for resource id 1 and resource id 2 for 2025'), return a plan like this as your FIRST output. The client will execute each plan step in order and append their outputs back into the conversation for you to reason on and then request rendering.\n"
                    "Example multi-step plan (fetch-only):\n"
                    "{\"plan\":[{\"id\":\"s1\",\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":1,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}},{\"id\":\"s2\",\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":2,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}}]}\n\n"
                    "After the client runs the plan steps it will append the tool outputs into the conversation as user messages tagged like '[TOOL OUTPUT - s1]' and '[TOOL OUTPUT - s2]'. When you receive those, produce either a render tool call (e.g., {\"tool\":\"render_from_dataset\", \"arguments\":{...}}) or a final JSON chart payload (labels/datasets) to be forwarded to the renderer.\n\n"
                    "User: \"Show planned vs actual hours for resource 42 from 2025-01-01 to 2025-12-31 monthly.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":42,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}}\n\n"
                    "User: \"Give me projects in Market & Sell portfolio with hours and costs.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_filtered_projects\",\"arguments\":{\"fields\":[\"project_name\",\"project_resource_hours_planned\",\"project_resource_cost_planned\"],\"filters\":[{\"column\":\"strategic_portfolio\",\"operator\":\"=\",\"value\":\"Market & Sell\"}]}}\n\n"
                    "If you need to provide commentary or explanation, put it AFTER the JSON object. The client will execute the first JSON object it finds and then provide the tool output back to you for any further reasoning.\n"
                )

                system_messages = [
                    {"role": "system", "content": system_instructions}
                ]

                # Build a richer system context by injecting resources and prompts from the MCP server
                resources_result = await session.list_resources()
                prompts_result = await session.list_prompts()
                resources = getattr(resources_result, 'resources', [])
                prompts = getattr(prompts_result, 'prompts', [])

                # Inject resource and prompt contents into the system context so Claude can use them
                for resource in resources:
                    content = getattr(resource, 'content', None) or getattr(resource, '_content', None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({"role": "system", "content": f"[{resource.name}] {content}"})
                for prompt in prompts:
                    content = getattr(prompt, 'content', None) or getattr(prompt, '_content', None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({"role": "system", "content": f"[{prompt.name}] {content}"})

                # Prepare the initial user message
                user_message = {"role": "user", "content": query}

                # Load or initialize short-lived in-process conversation memory for this chat_id
                conversation_messages = load_chat_memory(chat_id).copy() if load_chat_memory(chat_id) else []
                if not isinstance(conversation_messages, list):
                    conversation_messages = []
                # Append the new user message as the latest turn and persist immediately
                conversation_messages.append(user_message)
                # Persist right away so a chat file exists for this chat_id even before assistant returns
                try:
                    set_chat_memory(chat_id, conversation_messages)
                except Exception:
                    pass

                # Build a single string system_text from system_messages for Anthropic calls
                system_text = "\n".join([m['content'] for m in system_messages])

                # Helper: if assistant returns full HTML (chart), save to html-charts/ and return filepath

                def save_html_response_if_needed(text: str, query_text: str = None, prefix: str = "chart") -> str | None:
                    """If `text` looks like a full HTML document or a complete chart page, save it to html-charts and return path.
                    This function no longer attempts in-place repair — rendering/repair is centralized to the D3 MCP server.
                    """
                    markers = ["<!DOCTYPE html", "<html", "<script id=\"chart-data\"", "<div id=\"chart\""]
                    if not any(m in (text or '') for m in markers):
                        return None
                    try:
                        outdir = Path(__file__).resolve().parent / "html-charts"
                        outdir.mkdir(parents=True, exist_ok=True)
                        slug = ""
                        if query_text:
                            slug = re.sub(r'[^A-Za-z0-9_-]', '_', query_text)[:40]
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        h = hashlib.sha1((text or '').encode('utf-8')).hexdigest()[:6]
                        filename = f"{prefix}_{slug}_{ts}_{h}.html" if slug else f"{prefix}_{ts}_{h}.html"
                        filepath = outdir / filename
                        with open(filepath, 'wb') as f:
                            data = (text or '').encode('utf-8')
                            f.write(data)
                            f.flush()
                            try:
                                os.fsync(f.fileno())
                            except Exception:
                                pass
                        return str(filepath)
                    except Exception as e:
                        print("Failed to save HTML to file:", e)
                        return None

                # Automatic chart generation: if the user asked for a chart and we have recent tool output, spawn the chart generator
                async def try_auto_generate_chart_from_last_tool_output(user_query: str):
                    nonlocal conversation_messages
                    # Detect chart intent
                    if not re.search(r"\b(chart|plot|render|visuali[sz]e|graph)\b", user_query, re.IGNORECASE):
                        return None
                    # Find the most recent TOOL OUTPUT block in conversation_messages (any role)
                    last_tool_data = None
                    last_tool_name = None
                    for msg in reversed(conversation_messages):
                        content = msg.get('content') if isinstance(msg.get('content'), str) else None
                        if not content:
                            continue
                        # Accept lines that begin with [TOOL OUTPUT - NAME] or similar markers
                        header_match = re.match(r"\[TOOL OUTPUT - ([^\]]+)\]\s*(.*)$", content, re.DOTALL)
                        if header_match:
                            last_tool_name = header_match.group(1)
                            last_tool_data = header_match.group(2).strip()
                            break
                        # Sometimes the tool output is embedded as JSON only; accept a JSON object or array on its own line
                        stripped = content.strip()
                        if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                            # Heuristic: treat this as the latest tool output
                            last_tool_data = stripped
                            # no tool name available in this case
                            last_tool_name = None
                            break
                    if not last_tool_data:
                        return None

                    # Helper: try to parse the last tool payload into usable records
                    def parse_tool_payload(payload: str):
                        if not payload or not isinstance(payload, str):
                            return None
                        text = payload.strip()
                        # Detect a Markdown-style table and convert to list-of-dicts
                        # Example header: | # | Project Name | Product Line | Total Planned Cost |
                        lines = text.splitlines()
                        tbl_start = None
                        for i in range(len(lines)-1):
                            # a header line with '|' followed by a separator like |---| or ---
                            if '|' in lines[i] and re.search(r"\|?\s*-{3,}\s*\|?", lines[i+1]):
                                tbl_start = i
                                break
                        if tbl_start is not None:
                            try:
                                header_line = lines[tbl_start]
                                # gather subsequent table rows
                                data_rows = []
                                for r in lines[tbl_start+2:]:
                                    if not r.strip() or '|' not in r:
                                        break
                                    data_rows.append(r)
                                def split_row(r):
                                    return [c.strip() for c in re.split(r"\s*\|\s*", r.strip().strip('|'))]
                                headers = split_row(header_line)
                                parsed = []
                                for dr in data_rows:
                                    cells = split_row(dr)
                                    while len(cells) < len(headers):
                                        cells.append('')
                                    row = {}
                                    for h, c in zip(headers, cells):
                                        v = c
                                        # try to parse currency/number
                                        num = None
                                        try:
                                            s = re.sub(r'[^0-9.\-]', '', v)
                                            if s not in ('', '-', None):
                                                num = float(s)
                                        except Exception:
                                            num = None
                                        row[h or 'col'] = (num if num is not None else v)
                                    parsed.append(row)
                                if parsed:
                                    return parsed
                            except Exception:
                                pass
                        # If it's fenced JSON, extract inner
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
                        if m:
                            text = m.group(1).strip()
                        # Sometimes tool output is a quoted JSON string (double-encoded). Try to detect and unquote
                        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
                            try:
                                unq = json.loads(text)
                                if isinstance(unq, (dict, list)):
                                    return unq
                                text = unq if isinstance(unq, str) else text
                            except Exception:
                                # fall through
                                pass
                        # Direct parse attempt
                        try:
                            return json.loads(text)
                        except Exception:
                            # Try to extract first {...} or [...] block
                            start = text.find('{')
                            if start == -1:
                                start = text.find('[')
                            end = text.rfind('}')
                            if end == -1:
                                end = text.rfind(']')
                            if start != -1 and end != -1 and end > start:
                                candidate = text[start:end+1]
                                try:
                                    return json.loads(candidate)
                                except Exception:
                                    # Try cleaning trailing commas
                                    cleaned = re.sub(r',\s*(?=[\]\}])', '', candidate)
                                    try:
                                        return json.loads(cleaned)
                                    except Exception:
                                        return None
                            return None

                    # Instead of only using the last tool output, prefer using an LLM-based matcher
                    # that examines all cached tool outputs in the conversation and selects the
                    # one that best answers the user's query. If none match, ask the client to
                    # fetch the data live from the MCP server.

                    # Collect all tool outputs from the conversation into a list with their message index
                    cached_tool_outputs = []  # list of {msg_index, name, content}
                    for mi, msg in enumerate(conversation_messages):
                        content = msg.get('content') if isinstance(msg.get('content'), str) else None
                        if not content:
                            continue
                        header_match = re.match(r"\[TOOL OUTPUT - ([^\]]+)\]\s*(.*)$", content, re.DOTALL)
                        if header_match:
                            cached_tool_outputs.append({'msg_index': mi, 'name': header_match.group(1), 'content': header_match.group(2).strip()})
                            continue
                        # raw JSON-only user messages may also contain tool outputs
                        stripped = content.strip()
                        if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                            cached_tool_outputs.append({'msg_index': mi, 'name': None, 'content': stripped})

                    # If the user explicitly mentioned a resource id, try a deterministic match first:
                    requested_ids = []
                    try:
                        ids1 = re.findall(r"resource[_\s]*id\s*[:=]?\s*(\d+)", user_query, re.IGNORECASE)
                        ids2 = re.findall(r"resource\s+(\d+)\b", user_query, re.IGNORECASE)
                        for x in ids1 + ids2:
                            try:
                                requested_ids.append(int(x))
                            except Exception:
                                pass
                    except Exception:
                        requested_ids = []

                    # Initialize selection variables to avoid UnboundLocalError in all branches
                    # Note: do NOT reinitialize selection here — keep any deterministic
                    # match found above. The matcher logic below will only set these
                    # if it returns an explicit choice or requests a fetch.

                    # Initialize selection variables and deterministic hit flag
                    selected_payload = None
                    selected_name = None
                    deterministic_hit = False

                    # Deterministic matching: for each cached output, look backward a few messages
                    # to find the assistant tool-call JSON that produced it, then compare arguments.resource_id
                    if requested_ids and cached_tool_outputs:
                        for entry in reversed(cached_tool_outputs):
                            midx = entry.get('msg_index')
                            if midx is None:
                                continue
                            # look back up to 6 messages for an assistant message that contains the JSON tool call
                            for lookback in range(1, 7):
                                i = midx - lookback
                                if i < 0:
                                    break
                                mmsg = conversation_messages[i]
                                mcontent = mmsg.get('content') if isinstance(mmsg.get('content'), str) else None
                                if not mcontent:
                                    continue
                                # find fenced JSON blocks or inline JSON
                                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", mcontent, re.IGNORECASE)
                                parsed_call = None
                                if m:
                                    try:
                                        parsed_call = json.loads(m.group(1))
                                    except Exception:
                                        parsed_call = None
                                else:
                                    inline = re.search(r"(\{\s*\"tool\"[\s\S]*?\})", mcontent)
                                    if inline:
                                        try:
                                            parsed_call = json.loads(inline.group(1))
                                        except Exception:
                                            parsed_call = None
                                if not parsed_call or not isinstance(parsed_call, dict):
                                    continue
                                args = parsed_call.get('arguments', {}) or {}
                                rid = args.get('resource_id') or args.get('resourceId') or args.get('resource')
                                try:
                                    if isinstance(rid, str) and rid.isdigit():
                                        rid = int(rid)
                                except Exception:
                                    pass
                                if isinstance(rid, int) and rid in requested_ids:
                                    # deterministic hit
                                    selected_name = entry.get('name')
                                    selected_payload = entry.get('content')
                                    deterministic_hit = True
                                    break
                            if selected_payload:
                                break

                    # If deterministic match found, skip the LLM matcher and use the selected payload.
                    # The assistant should return a JSON object exactly in one of these forms:
                    # {"match_index": N}  -> use cached_tool_outputs[N]
                    # {"fetch": {"tool": "get_resource_allocation_planned_actual", "arguments": { ... } }} -> client will fetch
                    # {"none": true} -> no suitable data found and no fetch requested
                    # If no deterministic match was found above, ask the matcher LLM to pick
                    matcher_json = None
                    if not deterministic_hit:
                        matcher_request = {
                            'user_query': user_query,
                            'cached_count': len(cached_tool_outputs),
                        }

                        matcher_prompt = (
                            "You are a small helper that chooses whether a user's chart request can be satisfied from cached tool outputs.\n"
                            "Input: a user query and a numbered list (0..N-1) of cached tool outputs (each is JSON or text).\n"
                            "Task: If one of the cached tool outputs contains the data needed to fulfill the user's query, return exactly {\"match_index\": <index>} where <index> is the zero-based index into the list.\n"
                            "If none of the cached outputs are suitable, return exactly {\"fetch\": {\"tool\": \"get_resource_allocation_planned_actual\", \"arguments\": {\"resource_id\": <id>, \"start_date\": \"YYYY-MM-DD\", \"end_date\": \"YYYY-MM-DD\", \"interval\": \"Monthly\"}}} when the query appears to request resource allocation data for a specific resource, choosing sensible dates (default to current year) and a single resource id inferred from the query.\n"
                            "If unsure and no fetch should be made, return exactly {\"none\": true}.\n"
                            "Return only JSON in one of the three forms above, with no extra text.\n"
                        )

                        # prepare the list items for the prompt (truncate items to avoid blowing tokens)
                        preview_items = []
                        for i, item in enumerate(cached_tool_outputs):
                            c = item.get('content') or ''
                            preview = c[:1000].replace('\n', '\\n')
                            preview_items.append(f"{i}: {preview}")

                        full_prompt = matcher_prompt + "\nUser query:\n" + user_query + "\n\nCached tool outputs (index: preview):\n" + "\n".join(preview_items)

                        # Call Claude synchronously (small production call) to get the match instruction
                        matcher_response_text = None
                        try:
                            mresp = claude.messages.create(model=CLAUDE_MODEL, max_tokens=300, system=system_text, messages=[{"role": "user", "content": full_prompt}])
                            matcher_response_text = getattr(mresp, 'content')[0].text if mresp is not None else None
                        except Exception as e:
                            print('Matcher LLM call failed, falling back to last-tool behavior:', e)
                            matcher_response_text = None

                        # Helper to parse JSON from the matcher response
                        def parse_json_response(text: str):
                            if not text:
                                return None
                            # try direct parse or fenced JSON
                            try:
                                return json.loads(text)
                            except Exception:
                                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
                                if m:
                                    try:
                                        return json.loads(m.group(1))
                                    except Exception:
                                        pass
                                # extract first {...}
                                start = text.find('{')
                                end = text.rfind('}')
                                if start != -1 and end != -1 and end > start:
                                    try:
                                        return json.loads(text[start:end+1])
                                    except Exception:
                                        pass
                            return None

                        matcher_json = parse_json_response(matcher_response_text) if matcher_response_text else None

                    # Do not reinitialize selected_payload/selected_name here — deterministic hit
                    # may have already populated them above.
                    # If the matcher returned a match_index, use that cached payload
                    if matcher_json and isinstance(matcher_json, dict) and 'match_index' in matcher_json:
                        idx = int(matcher_json.get('match_index'))
                        if 0 <= idx < len(cached_tool_outputs):
                            selected_name = cached_tool_outputs[idx].get('name')
                            selected_payload = cached_tool_outputs[idx].get('content')

                    # If matcher asked to fetch, call the MCP tool
                    elif matcher_json and isinstance(matcher_json, dict) and 'fetch' in matcher_json:
                        fetch = matcher_json.get('fetch') or {}
                        tool_to_call = fetch.get('tool')
                        args = fetch.get('arguments', {}) or {}
                        try:
                            print(f"➡️ Matcher requested fetch: {tool_to_call} {args}")
                            tool_result = await session.call_tool(tool_to_call, args)
                            # normalize tool_result into a string payload
                            try:
                                if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                    result_content = json.dumps(tool_result.structuredContent, default=str)
                                elif hasattr(tool_result, 'content') and tool_result.content is not None:
                                    content = tool_result.content
                                    if isinstance(content, list):
                                        parts = [getattr(p, 'text', p) for p in content]
                                        if len(parts) == 1 and isinstance(parts[0], str):
                                            try:
                                                parsed_payload = json.loads(parts[0])
                                                result_content = json.dumps(parsed_payload, default=str)
                                            except Exception:
                                                result_content = parts[0]
                                        else:
                                            try:
                                                result_content = json.dumps(parts, default=str)
                                            except Exception:
                                                result_content = "\n".join(str(p) for p in parts)
                                    else:
                                        if isinstance(content, (dict, list)):
                                            result_content = json.dumps(content, default=str)
                                        else:
                                            result_content = str(content)
                                else:
                                    try:
                                        result_content = json.dumps(tool_result, default=str)
                                    except Exception:
                                        result_content = str(tool_result)
                            except Exception:
                                result_content = None
                            if result_content:
                                # append tool output into conversation and use it
                                conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_to_call}]\n{result_content}"})
                                if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                                    conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                                set_chat_memory(chat_id, conversation_messages)
                                selected_name = tool_to_call
                                selected_payload = result_content
                        except Exception as e:
                            print('Live fetch failed:', e)

                    # If matcher didn't return anything usable, fall back to using the most recent cached payload
                    if not selected_payload and cached_tool_outputs:
                        selected_name = cached_tool_outputs[-1].get('name')
                        selected_payload = cached_tool_outputs[-1].get('content')

                    if not selected_payload:
                        return None

                    dataset_obj = parse_tool_payload(selected_payload)
                    # Fallback: if payload looks like an HTML fragment containing a <script id='chart-data'> JSON, extract it
                    if not dataset_obj and isinstance(selected_payload, str):
                        mscript = re.search(r"<script[^>]*id=['\"]chart-data['\"][^>]*>([\s\S]*?)</script>", selected_payload, re.IGNORECASE)
                        if mscript:
                            inner = mscript.group(1).strip()
                            try:
                                dataset_obj = json.loads(inner)
                            except Exception:
                                try:
                                    cleaned = re.sub(r',\s*(?=[\]}])', '', inner)
                                    dataset_obj = json.loads(cleaned)
                                except Exception:
                                    dataset_obj = None

                    if not dataset_obj:
                        # Helpful debug message to aid tracing why no dataset was forwarded
                        print('No parsable dataset found in selected payload. Sample preview:')
                        try:
                            preview = (selected_payload or '')[:1000]
                            print(preview)
                        except Exception:
                            print('[unable to preview selected_payload]')
                        return None

                    # Delegate to the centralized D3 MCP server (rendering centralized). If server fails,
                    # we'll fall back to local behavior later.
                        # Quick validation: ensure embedded chart-data exists and is non-empty
                        def html_has_embedded_data(html_text: str) -> bool:
                            if '<script id="chart-data"' in html_text:
                                # crude check for non-empty JSON
                                m = re.search(r'<script id="chart-data".*?>([\s\S]*?)</script>', html_text, re.IGNORECASE)
                                if m:
                                    content = m.group(1).strip()
                                    return len(content) > 20
                            # fallback: look for recognizable dataset keys
                            return bool(re.search(r'"capacity"|"planned"|"actual"|"capacity_hours"|"planned_hours"', html_text, re.IGNORECASE))

                        if saved and html_has_embedded_data(html_output):
                            print("✅ Auto-generated chart saved to:", saved)
                            conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved}"})
                            set_chat_memory(chat_id, conversation_messages)
                            return f"HTML_SAVED:{saved}"
                        # If HTML exists but has no embedded data, fall through to local renderer

                    # If spawnable failed or produced HTML without embedded data, prefer forwarding the dataset
                    # to the centralized D3 MCP server. If that fails, fall back to the HTTP adapter/local renderer.
                    try:
                        # Detect explicit user request for pie/donut and pass hint to server
                        chart_hint = None
                        if user_query and re.search(r'\b(donut|doughnut)\b', user_query, re.IGNORECASE):
                            chart_hint = 'donut'
                        elif user_query and re.search(r'\b(pie)\b', user_query, re.IGNORECASE):
                            chart_hint = 'pie'

                        # The D3 MCP server expects a tool-like object; forward the payload and include chart_type hint
                        # Debug: show what will be forwarded to D3 MCP
                        try:
                            preview = None
                            if isinstance(dataset_obj, (dict, list)):
                                preview = json.dumps(dataset_obj)[:1000]
                            else:
                                preview = str(dataset_obj)[:1000]
                        except Exception:
                            preview = '<unserializable dataset>'
                        print('Forwarding to D3 MCP. chart_hint=', chart_hint, 'dataset preview=', preview)

                        # Normalize wrapper shapes like {"result": [...]} -> use the inner list
                        data_to_forward = dataset_obj
                        if isinstance(dataset_obj, dict) and 'result' in dataset_obj and isinstance(dataset_obj['result'], list):
                            data_to_forward = dataset_obj['result']
                        # Also unwrap single-key dicts where the value is a list (common wrapper)
                        if isinstance(data_to_forward, dict):
                            # try to find any list value to use if labels/datasets not present
                            list_vals = [v for v in data_to_forward.values() if isinstance(v, list) and v]
                            if list_vals:
                                data_to_forward = list_vals[0]

                        # If we have a list of records, try to synthesize {labels, datasets} for Chart.js
                        synthesized = None
                        if isinstance(data_to_forward, list) and data_to_forward:
                            # detect label and value fields heuristically
                            sample = data_to_forward[0]
                            if isinstance(sample, dict):
                                # possible label keys and cost keys
                                label_keys = ['project_name', 'name', 'project', 'title']
                                value_keys = ['project_resource_cost_planned', 'planned_cost', 'total_planned_cost', 'cost', 'project_cost_planned']
                                found_label = None
                                found_value = None
                                for k in label_keys:
                                    if k in sample:
                                        found_label = k
                                        break
                                for k in value_keys:
                                    if k in sample:
                                        found_value = k
                                        break
                                # fallback: choose first string-like key for labels and first numeric key for values
                                if not found_label:
                                    for k, v in sample.items():
                                        if isinstance(v, str) and k.lower().find('name') >= 0:
                                            found_label = k
                                            break
                                if not found_value:
                                    for k, v in sample.items():
                                        if isinstance(v, (int, float)):
                                            found_value = k
                                            break

                                if found_label and found_value:
                                    labels = []
                                    values = []
                                    for rec in data_to_forward:
                                        lbl = rec.get(found_label) if isinstance(rec, dict) else str(rec)
                                        val = rec.get(found_value) if isinstance(rec, dict) else None
                                        # coerce numeric strings to numbers
                                        if isinstance(val, str):
                                            try:
                                                val = float(re.sub(r'[^0-9.\-]', '', val))
                                            except Exception:
                                                val = 0.0
                                        if val is None:
                                            try:
                                                # try nested lookup like rec['fields']['project_resource_cost_planned']
                                                val = float(re.sub(r'[^0-9.\-]', '', str(rec.get(found_value, 0))))
                                            except Exception:
                                                val = 0.0
                                        labels.append(str(lbl))
                                        values.append(float(val or 0))

                                    # Provide simple colors for slices
                                    colors = [
                                        '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f'
                                    ]
                                    bg = [colors[i % len(colors)] for i in range(len(values))]
                                    synthesized = {
                                        'labels': labels,
                                        'datasets': [{
                                            'label': 'Planned Cost',
                                            'data': values,
                                            'backgroundColor': bg,
                                            'borderColor': bg,
                                            'borderWidth': 1
                                        }]
                                    }

                        # Only forward if we have something plausible to render
                        if synthesized is not None:
                            payload_data = synthesized
                        else:
                            # fallback to forwarding raw data_to_forward if it already looks chart-ready
                            payload_data = data_to_forward

                        # Validate payload_data quickly
                        valid_forward = False
                        if isinstance(payload_data, dict) and payload_data.get('labels') and payload_data.get('datasets'):
                            valid_forward = True
                        elif isinstance(payload_data, list) and payload_data:
                            valid_forward = True

                        if not valid_forward:
                            print('Not forwarding to D3 MCP because parsed dataset looks empty or invalid. payload preview:')
                            try:
                                print(str(payload_data)[:1000])
                            except Exception:
                                print('<unserializable>')
                            return None

                        forward_payload = {"tool": "render_from_dataset", "arguments": {"title": f"Auto-generated Chart", "data": payload_data, "chart_type": chart_hint}}
                        saved_path = forward_chart_json_to_d3(forward_payload, timeout=int(os.getenv('CHART_SPAWNABLE_TIMEOUT', '30')))
                        if saved_path:
                            # Copy into client html-charts with a meaningful name
                            client_saved = move_and_open_chart(saved_path, chart_type=(chart_hint or 'chart'), query_hint='auto')
                            final_path = client_saved or saved_path
                            print("✅ Auto-generated chart delegated to D3 MCP and saved to:", final_path)
                            conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {final_path}"})
                            set_chat_memory(chat_id, conversation_messages)
                            return f"HTML_SAVED:{final_path}"
                    except Exception as e:
                        print("D3 delegation failed, falling back to adapter/local renderer:", e)

                    # If D3 delegation did not succeed, continue with previous adapter-based fallback
                    html_output = None

                # If this user query appears to request a chart and we have recent tool output, try auto-generate now and return early
                auto_generated = await try_auto_generate_chart_from_last_tool_output(query)
                if auto_generated:
                    return auto_generated

                # Iterative tool-calling loop driven by Claude JSON responses
                max_iterations = 3
                iteration = 0
                last_tool_output = None

                # use module-level `re` imported at top; do not re-import here to avoid closure issues
                def extract_json_from_text(text: str):
                    # Try direct parse, fenced JSON, or first {...} block
                    try:
                        return json.loads(text)
                    except Exception:
                        m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
                        candidate = None
                        if m:
                            candidate = m.group(1)
                        else:
                            start = text.find('{')
                            end = text.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                candidate = text[start:end+1]
                        if candidate:
                            try:
                                return json.loads(candidate)
                            except Exception:
                                return None
                        return None

                # Iterative Claude loop: request -> optional tool call -> feed tool output back -> repeat
                while iteration < max_iterations:
                    iteration += 1
                    try:
                        response = claude.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=1000,
                            system=system_text,
                            messages=conversation_messages
                        )
                    except Exception as e:
                        if hasattr(anthropic, "NotFoundError") and isinstance(e, getattr(anthropic, "NotFoundError")):
                            print(f"ERROR: Anthropic model '{CLAUDE_MODEL}' not found. Set CLAUDE_MODEL in .env to a supported model id (check Anthropic Console).")
                            return f"ERROR: Anthropic model '{CLAUDE_MODEL}' not found. Update CLAUDE_MODEL and retry."
                        print("Anthropic API error:", e)
                        traceback.print_exc()
                        return f"ERROR: Anthropic API request failed: {e}"

                    # Extract assistant text
                    try:
                        assistant_text = getattr(response, 'content')[0].text
                    except Exception:
                        # Be tolerant to response shape variations
                        assistant_text = str(response)

                    # Persist the assistant's raw response into the in-memory conversation so subsequent turns see it
                    conversation_messages.append({"role": "assistant", "content": assistant_text})
                    # Trim memory to limit size
                    if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                        conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                    chat_memories[chat_id] = conversation_messages

                    print(f"Claude (iter {iteration}) response:\n", assistant_text)

                    # Try to extract JSON tool call from the assistant text
                    parsed = extract_json_from_text(assistant_text)

                    # Fallback heuristics for non-JSON tool hints
                    if not parsed:
                        inv_match = re.search(r'<invoke\s+name="([^"]+)"', assistant_text)
                        if inv_match:
                            parsed = {"tool": inv_match.group(1), "arguments": {}}
                        else:
                            # detect simple mentions like 'get_all_projects' or 'get_business_lines'
                            if re.search(r'\bget_all_projects\b', assistant_text):
                                parsed = {"tool": "get_all_projects", "arguments": {}}
                            elif re.search(r'\bget_business_lines\b', assistant_text):
                                parsed = {"tool": "get_business_lines", "arguments": {}}

                    # If parsed JSON is a multi-step plan, execute each step sequentially
                    if parsed and isinstance(parsed, dict) and 'plan' in parsed and isinstance(parsed.get('plan'), list):
                        steps = parsed.get('plan')
                        print(f"➡️ Received plan with {len(steps)} steps. Executing sequentially...")
                        plan_results = {}
                        for idx, step in enumerate(steps):
                            try:
                                tool_name = step.get('tool')
                                tool_args = step.get('arguments', {}) or {}
                                print(f"➡️ Plan step {idx+1}: Executing tool {tool_name} with args: {tool_args}")
                                try:
                                    tool_result = await session.call_tool(tool_name, tool_args)
                                except Exception as tool_err:
                                    print(f"Tool {tool_name} execution error in plan: {tool_err}")
                                    tool_result = {"error": str(tool_err)}

                                # Normalize tool_result into a string payload
                                try:
                                    if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                        result_content = json.dumps(tool_result.structuredContent, default=str)
                                    elif hasattr(tool_result, 'content') and tool_result.content is not None:
                                        content = tool_result.content
                                        if isinstance(content, list):
                                            parts = [getattr(p, 'text', p) for p in content]
                                            if len(parts) == 1 and isinstance(parts[0], str):
                                                try:
                                                    parsed_payload = json.loads(parts[0])
                                                    result_content = json.dumps(parsed_payload, default=str)
                                                except Exception:
                                                    result_content = parts[0]
                                            else:
                                                try:
                                                    result_content = json.dumps(parts, default=str)
                                                except Exception:
                                                    result_content = "\n".join(str(p) for p in parts)
                                        else:
                                            if isinstance(content, (dict, list)):
                                                result_content = json.dumps(content, default=str)
                                            else:
                                                result_content = str(content)
                                    else:
                                        try:
                                            result_content = json.dumps(tool_result, default=str)
                                        except Exception:
                                            result_content = str(tool_result)
                                except Exception:
                                    result_content = str(tool_result)

                                # Store and append to conversation so Claude can see step outputs
                                plan_results_key = tool_name or f"step_{idx+1}"
                                plan_results[plan_results_key] = result_content
                                conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                                # Trim and persist memory after each step
                                if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                                    conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                                chat_memories[chat_id] = conversation_messages
                                # If the tool output is very large, save it to disk and add a short assistant pointer
                                try:
                                    if isinstance(result_content, str) and len(result_content) > 4000:
                                        outdir = Path(__file__).resolve().parent / "data-exports"
                                        outdir.mkdir(parents=True, exist_ok=True)
                                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        fname = f"payload_{tool_name}_{chat_id}_{ts}.json"
                                        fpath = outdir / fname
                                        with open(fpath, 'w', encoding='utf-8') as _f:
                                            _f.write(result_content)
                                        conversation_messages.append({"role": "assistant", "content": f"[SAVED_PAYLOAD] {str(fpath)}"})
                                        set_chat_memory(chat_id, conversation_messages)
                                except Exception:
                                    pass
                            except Exception as e:
                                print(f"Error while executing plan step {idx+1}: {e}")
                                plan_results[f"step_{idx+1}_error"] = str(e)

                        # After executing the plan, provide the aggregated outputs back to the loop for further reasoning
                        # Try to auto-merge plan step results when they look like time-series for charting
                        def try_merge_plan_timeseries(plan_results_dict):
                            # plan_results_dict: {tool_name: result_content (stringified JSON or text)}
                            # Build a list of series with explicit labels and numeric arrays
                            all_series = []
                            labels_union = set()
                            for key, val in plan_results_dict.items():
                                try:
                                    parsed = json.loads(val) if isinstance(val, str) else val
                                except Exception:
                                    try:
                                        parsed = json.loads(str(val))
                                    except Exception:
                                        parsed = None
                                records = None
                                if isinstance(parsed, dict) and 'result' in parsed and isinstance(parsed['result'], list):
                                    records = parsed['result']
                                elif isinstance(parsed, list):
                                    records = parsed
                                if not records or not isinstance(records, list):
                                    continue
                                # detect label and numeric keys
                                sample = records[0] if records else {}
                                if not isinstance(sample, dict):
                                    continue
                                label_key = None
                                for k in sample.keys():
                                    if any(x in k.lower() for x in ('month', 'date', 'period', 'time', 'week')):
                                        label_key = k; break
                                if not label_key:
                                    # fallback to first string-like key
                                    for k, v in sample.items():
                                        if isinstance(v, str):
                                            label_key = k; break
                                numeric_key = None
                                for k, v in sample.items():
                                    if k == label_key:
                                        continue
                                    if isinstance(v, (int, float)) or (isinstance(v, str) and re.match(r'^[\d,\.\-\s]+$', str(v).strip())):
                                        numeric_key = k; break
                                if not label_key or not numeric_key:
                                    continue
                                series_labels = [str(r.get(label_key, '')) for r in records]
                                series_values = []
                                for r in records:
                                    try:
                                        v = r.get(numeric_key, 0)
                                        if v is None:
                                            v = 0
                                        if isinstance(v, str):
                                            v = float(re.sub(r'[^0-9.\-]', '', v) or 0)
                                        series_values.append(float(v))
                                    except Exception:
                                        series_values.append(0.0)
                                # collect
                                all_series.append({'label': f"{key}:{numeric_key}", 'labels': series_labels, 'data': series_values})
                                for L in series_labels:
                                    labels_union.add(L)

                            if not all_series:
                                return None

                            # sort labels: try YYYY-MM detection else lexicographic
                            def sort_labels(lbls):
                                try:
                                    if all(re.match(r'^\d{4}-\d{2}$', l) for l in lbls):
                                        return sorted(lbls)
                                except Exception:
                                    pass
                                return sorted(lbls)

                            unified_labels = sort_labels(list(labels_union))

                            # align each series to unified labels filling missing with 0
                            palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b']
                            datasets = []
                            for idx, s in enumerate(all_series):
                                mapping = {l: v for l, v in zip(s['labels'], s['data'])}
                                aligned = [float(mapping.get(L, 0) or 0) for L in unified_labels]
                                color = palette[idx % len(palette)]
                                datasets.append({'label': s['label'], 'data': aligned, 'borderColor': color, 'backgroundColor': color, 'fill': False})

                            return {'labels': unified_labels, 'datasets': datasets}

                        merged_payload = None
                        try:
                            merged_payload = try_merge_plan_timeseries(plan_results)
                        except Exception as _:
                            merged_payload = None

                        if merged_payload:
                            try:
                                # Prefer server-side merge if available
                                saved_path = None
                                try:
                                    # Attempt to call server merge_timeseries tool if the MCP server exposes it
                                    merge_args = {'merged': merged_payload}
                                    # some MCP servers expose merge_timeseries as a tool; prefer calling it
                                    try:
                                        merge_result = await session.call_tool('merge_timeseries', {'items': []})
                                        # If we've reached here, the server supports merge_timeseries; skip local
                                        # But we already have merged_payload so just proceed to render
                                    except Exception:
                                        # server doesn't support merge_timeseries or call failed; proceed with local merged_payload
                                        pass
                                except Exception:
                                    pass

                                forward_payload = {"tool": "render_from_dataset", "arguments": {"title": "Auto-merged Chart", "data": merged_payload, "chart_type": "line"}}
                                saved_path = forward_chart_json_to_d3(forward_payload, timeout=int(os.getenv('CHART_SPAWNABLE_TIMEOUT', '30')))
                                if saved_path:
                                    # copy into client html-charts
                                    client_saved = move_and_open_chart(saved_path, chart_type='line', query_hint='auto-merged')
                                    final_path = client_saved or saved_path
                                    print("✅ Plan auto-merged and chart saved to:", final_path)
                                    conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {final_path}"})
                                    set_chat_memory(chat_id, conversation_messages)
                                    # set last_tool_output to the saved path indicator so the loop can exit or reason further
                                    last_tool_output = json.dumps({'html_saved': final_path})
                                else:
                                    last_tool_output = json.dumps(plan_results)
                            except Exception as e:
                                print("Failed to forward merged plan payload to D3 MCP:", e)
                                last_tool_output = json.dumps(plan_results)
                        else:
                            last_tool_output = json.dumps(plan_results)
                        # continue to next iteration so Claude gets the tool outputs as user messages
                        continue

                    # If parsed JSON indicates a tool invocation, execute it
                    if parsed and isinstance(parsed, dict) and 'tool' in parsed:
                        tool_name = parsed['tool']
                        tool_args = parsed.get('arguments', {}) or {}
                        print(f"➡️ Iteration {iteration}: Executing tool {tool_name} with args: {tool_args}")
                        try:
                            tool_result = await session.call_tool(tool_name, tool_args)
                        except Exception as tool_err:
                            print(f"Tool {tool_name} execution error: {tool_err}")
                            tool_result = {"error": str(tool_err)}

                        # Normalize tool_result into a string payload to send back to Claude
                        try:
                            if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                result_content = json.dumps(tool_result.structuredContent, default=str)
                            elif hasattr(tool_result, 'content') and tool_result.content is not None:
                                content = tool_result.content
                                if isinstance(content, list):
                                    parts = [getattr(p, 'text', p) for p in content]
                                    if len(parts) == 1 and isinstance(parts[0], str):
                                        try:
                                            parsed_payload = json.loads(parts[0])
                                            result_content = json.dumps(parsed_payload, default=str)
                                        except Exception:
                                            result_content = parts[0]
                                    else:
                                        try:
                                            result_content = json.dumps(parts, default=str)
                                        except Exception:
                                            result_content = "\n".join(str(p) for p in parts)
                                else:
                                    if isinstance(content, (dict, list)):
                                        result_content = json.dumps(content, default=str)
                                    else:
                                        result_content = str(content)
                            else:
                                try:
                                    result_content = json.dumps(tool_result, default=str)
                                except Exception:
                                    result_content = str(tool_result)
                        except Exception:
                            result_content = str(tool_result)

                        last_tool_output = result_content
                        # Append tool output into conversation as a user message so Claude can reason about it in the next turn
                        conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                        # Trim and persist memory after tool output
                        if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                            conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        set_chat_memory(chat_id, conversation_messages)
                        # If the tool output is very large, save it to disk and add a short assistant pointer
                        try:
                            if isinstance(result_content, str) and len(result_content) > 4000:
                                outdir = Path(__file__).resolve().parent / "data-exports"
                                outdir.mkdir(parents=True, exist_ok=True)
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fname = f"payload_{tool_name}_{chat_id}_{ts}.json"
                                fpath = outdir / fname
                                with open(fpath, 'w', encoding='utf-8') as _f:
                                    _f.write(result_content)
                                conversation_messages.append({"role": "assistant", "content": f"[SAVED_PAYLOAD] {str(fpath)}"})
                                set_chat_memory(chat_id, conversation_messages)
                        except Exception:
                            pass
                        # Continue the loop to let Claude decide next action
                        continue

                    # No tool requested — treat assistant_text as final answer
                    saved_path = save_html_response_if_needed(assistant_text, query, prefix="claude_answer")
                    if saved_path:
                        print("✅ Final Claude answer saved to:", saved_path)
                        conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved_path}"})
                        set_chat_memory(chat_id, conversation_messages)
                        return f"HTML_SAVED:{saved_path}"
                    else:
                        # If Claude returned an HTML page but it lacks embedded chart-data, try auto-generating
                        # a chart by forwarding the most recent tool output(s) to the centralized D3 MCP server.
                        is_html = bool(re.search(r"<!DOCTYPE html|<html", assistant_text, re.IGNORECASE))
                        has_embedded = '<script id="chart-data"' in (assistant_text or '')
                        recent_tool_output_exists = any(re.search(r"\[TOOL OUTPUT - ", m.get('content', '') or '') for m in conversation_messages)
                        if is_html and (not has_embedded) and recent_tool_output_exists:
                            print("Assistant returned HTML without embedded data — attempting to auto-generate chart from recent tool outputs...")
                            try:
                                auto_generated = try_auto_generate_chart_from_last_tool_output(query)
                                if auto_generated:
                                    # try_auto_generate_chart_from_last_tool_output already appends and saves
                                    return auto_generated
                                else:
                                    print("Auto-generation fallback did not produce an HTML file.")
                            except Exception as e:
                                print("Auto-generation fallback failed:", e)

                        print("✅ Final Claude answer:")
                        print(assistant_text)
                        set_chat_memory(chat_id, conversation_messages)
                        return assistant_text

                # If we exit loop with last_tool_output, ask Claude to reason over it (final analysis)
                if last_tool_output:
                    system_text = "\n".join([m['content'] for m in system_messages])
                    conversation_messages.append({
                        "role": "user",
                        "content": f"Here is the raw JSON result:\n{last_tool_output}\n\nNow, based on my original query ('{query}'), please compute and explain the answer. Provide only the analysis and final answer."
                    })
                    reasoning_resp = claude.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=1000,
                        system=system_text,
                        messages=conversation_messages
                    )
                    final_text = reasoning_resp.content[0].text
                    # If Claude produced HTML for the reasoning result, save instead of printing
                    saved_path = save_html_response_if_needed(final_text, query, prefix="claude_reasoning")
                    if saved_path:
                        # copy to client html-charts for consistent naming
                        client_saved = move_and_open_chart(saved_path, chart_type='reasoning', query_hint='claude_reasoning')
                        final_path = client_saved or saved_path
                        print("\n🤖 Claude reasoning result saved to:\n", final_path)
                        conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {final_path}"})
                        set_chat_memory(chat_id, conversation_messages)
                        return f"HTML_SAVED:{final_path}"
                    else:
                        print("\n🤖 Claude reasoning result:\n")
                        print(final_text)
                        # Persist final reasoning in memory and return
                        conversation_messages.append({"role": "assistant", "content": final_text})
                        set_chat_memory(chat_id, conversation_messages)
                        return final_text

                # If nothing produced, fallback to previous simple behavior
                print("⚠️ No tool output produced and no final answer returned from Claude.")
                # Persist current memory state even if no useful output
                set_chat_memory(chat_id, conversation_messages)
                return None

    except Exception as e:
        print("Error during MCP session:")
        traceback.print_exc()

if __name__ == "__main__":
    print("PMO Claude REPL — type ':exit' or Ctrl-C to quit.")
    # Start a fresh session id per REPL run unless user chooses to load an existing one
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    # sanitize to match memory_file_for rules
    session_id = re.sub(r'[^A-Za-z0-9_.-]', '_', session_id)[:64]
    current_chat_id = session_id
    # allow starting with a named session via CLI
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--session', '-s', help='Start REPL with this session id (sanitized).')
    known_args, _ = parser.parse_known_args()
    if known_args.session:
        chosen = re.sub(r'[^A-Za-z0-9_.-]', '_', known_args.session)[:64]
        current_chat_id = chosen

    # Ensure chat memory dir exists
    ensure_memory_dir()
    print(f"Session started. Session ID: {current_chat_id}")
    print("Commands: :list-sessions  :use <id>  :show <id>  :show  :exit")

    def human_size(n):
        try:
            n = int(n)
        except Exception:
            return str(n)
        for unit in ['B','KB','MB','GB','TB']:
            if n < 1024:
                return f"{n}{unit}"
            n = n/1024
        return f"{n:.1f}TB"

    def list_sessions():
        try:
            files = []
            for p in CHAT_MEMORY_DIR.iterdir():
                if p.is_file() and p.suffix == '.json':
                    stat = p.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat(' ')
                    size = human_size(stat.st_size)
                    files.append((p.name, mtime, size))
            return sorted(files, key=lambda t: t[0])
        except Exception:
            return []

    try:
        # Load (or initialize) memory for this new session so subsequent runs use it
        load_chat_memory(current_chat_id)
        while True:
            try:
                raw = input(f"\n[{current_chat_id}] What information can I get you from the PMO platform? ")
            except EOFError:
                print("\nEOF received, exiting.")
                break
            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                # Save and exit
                try:
                    set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                except Exception:
                    pass
                break

            if raw is None:
                continue
            query = raw.strip()
            if not query:
                continue
            # REPL commands prefixed with ':'
            if query.startswith(":"):
                parts = query[1:].split()
                cmd = parts[0].lower() if parts else ''
                if cmd in ('exit', 'quit'):
                    print('Exiting.')
                    try:
                        set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                    except Exception:
                        pass
                    break
                if cmd == 'list-sessions' or cmd == 'list':
                    sess = list_sessions()
                    if not sess:
                        print('No sessions found.')
                    else:
                        print('Saved sessions:')
                        for s in sess:
                            print(' -', s)
                    continue
                if cmd in ('use', 'load') and len(parts) >= 2:
                    new_id = parts[1]
                    new_id = re.sub(r'[^A-Za-z0-9_.-]', '_', new_id)[:64]
                    current_chat_id = new_id
                    load_chat_memory(current_chat_id)
                    print(f'Loaded session: {current_chat_id}')
                    continue
                if cmd == 'show':
                    if len(parts) >= 2:
                        target = re.sub(r'[^A-Za-z0-9_.-]', '_', parts[1])[:64]
                        path = memory_file_for(target)
                        if path.exists():
                            try:
                                with open(path, 'r', encoding='utf-8') as f:
                                    data = f.read()
                                    print(data[:4000])
                            except Exception as e:
                                print('Failed to read session file:', e)
                        else:
                            print('Session file not found:', path)
                    else:
                        print('Current session:', current_chat_id)
                    continue
                print('Unknown command:', cmd)
                continue

            # Run the main routine using the selected session id
            try:
                asyncio.run(run(query, chat_id=current_chat_id))
            except KeyboardInterrupt:
                print('\nInterrupted by user during run; saving session and returning to REPL.')
                try:
                    set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                except Exception:
                    pass
                continue

    except KeyboardInterrupt:
        print('\nInterrupted. Goodbye.')
        try:
            set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
        except Exception:
            pass