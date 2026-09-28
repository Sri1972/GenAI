# requirements.txt:
# fastapi
# uvicorn
# python-dotenv
# openai
# httpx
# openpyxl
# PyMuPDF
# anthropic[bedrock]

import json
import os
import re
import ssl
import tempfile
from pathlib import Path
from typing import Any

import fitz
import httpx
import openpyxl
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv(Path(".") / ".env")

LITELLM_API_BASE = os.getenv("LITELLM_API_BASE", "")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
LITELLM_SSL_CERT = os.getenv("LITELLM_SSL_CERT", "")
LITELLM_TIMEOUT = int(os.getenv("LITELLM_TIMEOUT", "120"))
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "claude-sonnet-4-6")
API_PORT = int(os.getenv("API_PORT", "8080"))
DATA_API_BASE = os.getenv("DATA_API_BASE", "http://localhost:8080")

# ── AWS Bedrock — PRIMARY for /api/chat, not a fallback. LiteLLM's proxy has
# a documented history of prolonged outages (not brief blips), so a chat
# feature that tries LiteLLM first and only reaches Bedrock after several
# retries pays that outage's full cost on every single message. Bedrock is
# tried first instead; LiteLLM only runs as a last-resort backup if Bedrock
# itself is unavailable. Same config shape as the app-generation pipeline's
# own sdk_client.py, which made the identical swap for the same reason.
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/oonx9pzz8l4h",
)
BEDROCK_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_PROFILE = os.getenv("AWS_PROFILE", "default")
BEDROCK_TIMEOUT = int(os.getenv("BEDROCK_TIMEOUT", "120"))


def _make_ssl_context() -> ssl.SSLContext | bool:
    if not LITELLM_SSL_CERT:
        return True
    ctx = ssl.create_default_context()
    cert_content = LITELLM_SSL_CERT.replace("\\n", "\n")
    ctx.load_verify_locations(cadata=cert_content)
    return ctx


http_client = httpx.AsyncClient(
    verify=_make_ssl_context(),
    timeout=httpx.Timeout(connect=30.0, read=float(LITELLM_TIMEOUT), write=60.0, pool=30.0),
)
base_url = LITELLM_API_BASE.rstrip("/") + "/v1" if LITELLM_API_BASE else ""
client = AsyncOpenAI(
    api_key=LITELLM_API_KEY,
    base_url=base_url,
    http_client=http_client,
    timeout=LITELLM_TIMEOUT,
)

# Bedrock client — lazy-init (constructing it touches AWS credential
# resolution; deferred to first actual use rather than import time).
_bedrock_client = None
# Sticky, module-level: once Bedrock has failed enough to trigger the LiteLLM
# backup, every subsequent /api/chat request in this process goes straight to
# LiteLLM instead of re-probing a provider that's known to be down (matches
# the same sticky-fallback pattern used by the app-generation pipeline's own
# sdk_client.py — just for the opposite provider, since this file makes
# Bedrock primary instead).
_chat_using_litellm_fallback = False


def _get_bedrock_chat_client():
    global _bedrock_client
    if _bedrock_client is None:
        from anthropic import AsyncAnthropicBedrock
        _bedrock_client = AsyncAnthropicBedrock(
            aws_profile=BEDROCK_PROFILE,
            aws_region=BEDROCK_REGION,
            http_client=httpx.AsyncClient(
                verify=_make_ssl_context(),
                timeout=httpx.Timeout(connect=30.0, read=float(BEDROCK_TIMEOUT), write=60.0, pool=30.0),
            ),
        )
    return _bedrock_client


def _openai_tools_to_anthropic(tools_openai: list[dict]) -> list[dict]:
    """MCP tools are fetched once as OpenAI-style function-calling schemas
    (see _get_chat_tools) since that's the primary LiteLLM/OpenAI-SDK path.
    Bedrock's native tool-use format is structurally the same information,
    just renamed/flattened — no MCP round-trip needed to reshape it."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in tools_openai
    ]


async def _run_bedrock_chat_stream(system_prompt: str, conversation: list[dict], tools_openai: list[dict],
                                    max_tool_rounds: int = 12):
    """
    Anthropic-native tool-use loop for the Bedrock fallback path. Kept as a
    separate loop rather than a shared abstraction with the LiteLLM/OpenAI-SDK
    loop below: the two providers' tool-calling wire formats are genuinely
    different shapes (OpenAI: tool_calls list + role='tool' messages keyed by
    tool_call_id; Anthropic: tool_use/tool_result content blocks keyed by a
    differently-named id) — forcing one shared code path would mean converting
    back and forth every round instead of once at the boundary.

    An async generator rather than a plain coroutine so the caller can stream
    "tool_call" progress events to the frontend as they happen (RetailBot-style
    UIs otherwise just show a blank spinner for however long a multi-round
    tool-calling turn takes, with no visibility into whether it's stuck or
    genuinely working). Yields {"type": "tool_call", ...} as each tool starts,
    then exactly one {"type": "final_text", "text": ...} at the end.
    """
    client_bedrock = _get_bedrock_chat_client()
    anthropic_tools = _openai_tools_to_anthropic(tools_openai)
    # conversation entries are already plain {"role": "user"/"assistant", "content": str}
    # from the request body — that shape is valid for Anthropic's API as-is.
    messages: list[dict] = list(conversation)

    for _round in range(max_tool_rounds):
        response = await client_bedrock.messages.create(
            model=BEDROCK_MODEL_ID,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=anthropic_tools,
        )

        if response.stop_reason != "tool_use":
            text_parts = [b.text for b in response.content if b.type == "text"]
            yield {"type": "final_text", "text": "".join(text_parts)}
            return

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            text_parts = [b.text for b in response.content if b.type == "text"]
            yield {"type": "final_text", "text": "".join(text_parts)}
            return

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_use_blocks:
            print(f"[datachat] Bedrock tool call: {block.name}({json.dumps(block.input, default=str)[:200]})", flush=True)
            yield {"type": "tool_call", "tool": block.name, "args": block.input}
            result = await _execute_chat_tool(block.name, block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    # Exhausted tool rounds — return whatever text the last response had, if any
    text_parts = [b.text for b in response.content if b.type == "text"]
    yield {"type": "final_text", "text": "".join(text_parts) or "I wasn't able to complete the analysis in the allowed steps."}

# HTTP client for calling the data REST API (no SSL needed — same host)
_data_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0))

# mcp_server.py reads DATA_API_BASE from the environment at its own import
# time (already set above, pointing at the Java backend this sidecar was
# started alongside — see _start_datachat_server in uigen_agent.py) — no
# override needed here, unlike the pure-Python app_server_template.py case.
from mcp_server import mcp_asgi_app  # noqa: E402

# Combined lifespan: MUST enter mcp_asgi_app.lifespan for its session manager
# to start (a bare app.mount() without this accepts connections but
# terminates every session — verified live before writing this, see
# app_server_template.py for the full story), and startup() below used to be
# a separate @app.on_event("startup") handler — merged in explicitly rather
# than relying on the two mechanisms to coexist (they don't reliably: in
# app_server_template.py this exact combination silently skipped the other
# startup hook's body).
from contextlib import asynccontextmanager as _asynccontextmanager


@_asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with mcp_asgi_app.lifespan(_app):
        print(f"\n  DataChat API Server running on port {API_PORT}")
        print(f"  Data API: {DATA_API_BASE}")
        print(f"  Endpoints:")
        print(f"    POST /api/chat         — LLM chat with tool-calling (via MCP, mounted at /mcp)")
        print(f"    GET  /mcp              — MCP server (tools for /api/chat)")
        print(f"    GET  /api/chat/health  — Health check (LLM + data API)")
        print(f"    POST /api/ingest/excel — Parse Excel files")
        print(f"    POST /api/ingest/pdf   — Parse PDF files")
        print(f"    POST /api/ingest/json  — Ingest JSON data")
        print(f"    GET  /health           — Basic health check\n")
        yield


app = FastAPI(title="DataChat API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/mcp", mcp_asgi_app)


from fastmcp import Client as _MCPClient

_MCP_SELF_URL = f"http://localhost:{API_PORT}/mcp"
_mcp_client: "_MCPClient | None" = None
_mcp_tools_openai: list[dict] | None = None


async def _get_mcp_client() -> "_MCPClient":
    """Lazily connect to this same sidecar process's own /mcp mount, reused
    across requests — same lazy/cached pattern this file already used for
    the old _discover_api() (which this replaces)."""
    global _mcp_client
    if _mcp_client is None or not _mcp_client.is_connected():
        _mcp_client = _MCPClient(_MCP_SELF_URL)
        await _mcp_client.__aenter__()
    return _mcp_client


async def _get_chat_tools() -> list[dict]:
    """Fetch tools from the real MCP server (mounted at /mcp on this same
    process) once, converted to OpenAI function-calling format."""
    global _mcp_tools_openai
    if _mcp_tools_openai is None:
        client = await _get_mcp_client()
        mcp_tools = await client.list_tools()
        _mcp_tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema,
                },
            }
            for t in mcp_tools
        ]
    return _mcp_tools_openai


async def _execute_chat_tool(name: str, args: dict) -> str:
    """Execute a tool call via the real MCP server instead of building/parsing
    per-table tool schemas locally — the query logic now lives in mcp_server.py,
    shared with the pure-Python app_server_template.py deployment of this same
    tool server."""
    try:
        client = await _get_mcp_client()
        result = await client.call_tool(name, args)
        data = result.data if hasattr(result, "data") else result
        return data if isinstance(data, str) else json.dumps(data, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {str(e)}"})


# --- Models ---

class ContextPayload(BaseModel):
    type: str = "custom"
    # schema_ entries come in TWO real shapes depending on contextType:
    #  - flat column descriptors (upload-excel/pdf/json): [{name, type}, ...]
    #  - multi-table descriptors (DataChat.skill.tsx's 'structured' contextType,
    #    used for database-connected apps): [{name, type:'table', columns:[...]}, ...]
    # dict[str, Any] already accepts either shape structurally; _build_system_prompt
    # below is what actually has to branch on which one it got.
    schema_: list[dict[str, Any]] | None = None
    # sampleRows is EITHER a flat list (upload-excel/pdf/json: one table/sheet) OR a
    # dict keyed by table name (the 'structured' multi-table case sends one sample
    # array per table, e.g. {"stores": [...], "hourly_metrics": [...]}). Typing this
    # as list-only rejected every multi-table structured request with a 422 — which
    # the frontend then rendered as the literal string "[object Object]" since
    # FastAPI's 422 body puts the validation errors in `detail` as a list of objects,
    # not a string.
    sampleRows: list[dict[str, Any]] | dict[str, list[dict[str, Any]]] | None = None
    text: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    context: ContextPayload
    messages: list[ChatMessage]
    responseFormat: str = "auto"


class JsonIngestRequest(BaseModel):
    data: list[dict[str, Any]]
    metadata: dict[str, Any] | None = None


# --- Helpers ---

def _build_system_prompt(context: ContextPayload, response_format: str) -> str:
    """Build system prompt from the ingested-file context (schema/sample rows/
    metadata), kept outside MCP since the frontend resends the full context on
    every request rather than any MCP client selectively pulling it as a resource."""
    prompt = context.text or "You are an AI data assistant."
    if context.schema_:
        schema_lines = []
        for entry in context.schema_:
            cols = entry.get("columns")
            if isinstance(cols, list):
                # multi-table shape: entry is a table descriptor with nested columns
                col_desc = ", ".join(
                    f"{c.get('name')} ({c.get('type', 'text')})" for c in cols if isinstance(c, dict)
                )
                schema_lines.append(f"{entry.get('name', '?')}: {col_desc}")
            else:
                # flat shape: entry IS a column descriptor
                schema_lines.append(f"{entry.get('name', '?')} ({entry.get('type', 'text')})")
        if schema_lines:
            prompt += "\n\nAvailable data schema:\n" + "\n".join(f"- {l}" for l in schema_lines)
    if context.sampleRows:
        if isinstance(context.sampleRows, dict):
            for table_name, rows in context.sampleRows.items():
                if rows:
                    prompt += f"\n\nSample rows for '{table_name}':\n{json.dumps(rows[:10], default=str)}"
        else:
            prompt += f"\n\nSample rows:\n{json.dumps(context.sampleRows[:10], default=str)}"
    if context.metadata:
        prompt += f"\n\nAdditional context metadata:\n{json.dumps(context.metadata, default=str)}"
    prompt += (
        "\n\nYou have access to tools that let you query the application's live database. "
        "ALWAYS use the tools to fetch real data before answering data questions. "
        "Never guess or fabricate numbers — call query_data or aggregate_data to get actual values. "
        "If you're unsure which tables or columns exist, call list_tables first.\n\n"
        "You have a LIMITED number of tool calls per question — use them efficiently:\n"
        "- For a question spanning multiple records of the same kind (e.g. comparing across "
        "several clients/accounts/categories), do NOT query each one individually one at a "
        "time. Fetch the WHOLE relevant table (or a broad, unfiltered/lightly-filtered slice "
        "of it) in ONE call first, then compute the comparison yourself from those rows.\n"
        "- Use an aggregate/group-by tool call for a cross-record summary (totals, averages, "
        "counts per group) instead of one call per group.\n"
        "- Only query a SPECIFIC single record (one client, one item) when the question is "
        "actually about that one record specifically.\n"
        "- Plan your queries before making them: prefer 1-3 well-chosen broad calls over many "
        "narrow ones. If you're not close to a final answer after a few tool calls, stop adding "
        "detail and answer with what you have rather than continuing to query indefinitely.\n"
        "- If a question needs something that spans MULTIPLE tables in one result (a join, or a "
        "specific cross-table metric) that query_table/aggregate_table can't produce on their "
        "own (they only ever look at one table at a time), call list_custom_endpoints first — "
        "this app may have a purpose-built endpoint for exactly that. If one exists, call it "
        "with call_endpoint instead of fetching each table separately and combining them "
        "yourself. If none exists, fall back to fetching the relevant tables broadly, per the "
        "rules above."
    )

    if response_format == "chart":
        prompt += (
            "\n\nIMPORTANT: The user wants a chart. After fetching data with tools, respond with ONLY valid JSON: "
            '{"type": "bar"|"line"|"donut"|"scatter", "title": "Chart Title", '
            '"data": [{...}], "xKey": "fieldName", "yKeys": ["fieldName1"]}. '
            "The data array must contain the actual values from your tool queries."
        )
    elif response_format == "table":
        prompt += (
            "\n\nIMPORTANT: The user wants tabular output. After fetching data with tools, respond with ONLY a JSON array of objects, "
            "e.g. [{col1: val, col2: val}, ...]. Include relevant columns from the query results."
        )
    elif response_format == "auto":
        prompt += (
            "\n\nResponse format rules:\n"
            "- If the answer is best shown as a chart, wrap it in ```chart\\n{json}\\n``` "
            "where json is: {type, title, data, xKey, yKeys}\n"
            "- If best as a table, wrap it in ```table\\n[{...}, ...]\\n```\n"
            "- Otherwise respond in plain text with markdown formatting.\n"
            "- For simple text answers, just respond normally.\n"
            "- ALWAYS base your response on actual data from tool calls, not assumptions."
        )
    return prompt


def parse_response(text: str) -> dict[str, Any]:
    chart_match = re.search(r"```chart\s*\n([\s\S]*?)\n```", text)
    if chart_match:
        try:
            data = json.loads(chart_match.group(1))
            return {"response": text, "type": "chart", "data": data}
        except json.JSONDecodeError:
            pass

    table_match = re.search(r"```table\s*\n([\s\S]*?)\n```", text)
    if table_match:
        try:
            data = json.loads(table_match.group(1))
            return {"response": text, "type": "table", "data": data}
        except json.JSONDecodeError:
            pass

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "type" in data:
            return {"response": text, "type": "chart", "data": data}
        if isinstance(data, list):
            return {"response": text, "type": "table", "data": data}
    except json.JSONDecodeError:
        pass

    return {"response": text, "type": "text", "data": None}


def detect_column_type(values: list) -> str:
    non_empty = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_empty:
        return "text"
    numeric_count = 0
    for v in non_empty:
        try:
            float(v)
            numeric_count += 1
        except (ValueError, TypeError):
            break
    if numeric_count == len(non_empty):
        return "numeric"
    date_pattern = re.compile(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}")
    if all(date_pattern.search(str(v)) for v in non_empty[:20]):
        return "date"
    unique = set(str(v) for v in non_empty)
    if len(unique) < 20:
        return "categorical"
    return "text"


def infer_schema(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    schema = []
    for col in columns:
        values = [row.get(col) for row in rows[:100]]
        schema.append({"name": col, "type": detect_column_type(values)})
    return schema


# --- Endpoints ---

async def _run_litellm_chat_stream(messages: list[dict], tools: list[dict], max_tool_rounds: int = 12):
    """
    OpenAI-SDK tool-use loop against LiteLLM. `messages` already includes the
    system message (OpenAI shape) and is mutated in place as rounds progress —
    same as the previous non-streaming version, just yielding "tool_call"
    progress events instead of only returning the final text.
    """
    global client
    for _round in range(max_tool_rounds):
        completion = await client.chat.completions.create(
            model=LITELLM_MODEL,
            messages=messages,
            tools=tools,
            temperature=0.3,
        )
        choice = completion.choices[0]

        if choice.finish_reason == "tool_use" or (choice.message.tool_calls and len(choice.message.tool_calls) > 0):
            messages.append(choice.message.model_dump())
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"[datachat] Tool call: {fn_name}({json.dumps(fn_args, default=str)[:200]})", flush=True)
                yield {"type": "tool_call", "tool": fn_name, "args": fn_args}
                result = await _execute_chat_tool(fn_name, fn_args)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
            continue

        yield {"type": "final_text", "text": choice.message.content or ""}
        return

    yield {"type": "final_text", "text": choice.message.content or "I wasn't able to complete the analysis in the allowed steps."}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _stream_chat_events(request: "ChatRequest"):
    """
    Drives the whole /api/chat turn as a stream of SSE events instead of one
    blocking JSON response — the previous shape left the frontend showing a
    blank spinner for however long a multi-round tool-calling turn took (often
    10-60s+ across several tool calls), with zero visibility into whether it
    was stuck or genuinely working. Event types:
      {"type": "tool_call", "tool": str, "args": dict} — a tool is about to run
      {"type": "status", "message": str}               — provider retry/fallback
      {"type": "final", "result": {...parse_response() shape...}}
      {"type": "error", "detail": str}                 — terminal failure

    Bedrock first, LiteLLM only as a last-resort backup (see the module-level
    comment above BEDROCK_MODEL_ID for why). Kept deliberately simple — two
    quick attempts per provider for a genuine transient blip, not the 3x
    escalating-backoff dance this file used to run against LiteLLM before
    ever reaching Bedrock.

    IMPORTANT: once the stream has started (HTTP 200 already sent), failures
    can no longer become HTTP error responses — they're reported as an "error"
    event instead.
    """
    import asyncio
    global client, http_client, _chat_using_litellm_fallback

    system_prompt = _build_system_prompt(request.context, request.responseFormat)
    recent = request.messages[-20:] if len(request.messages) > 20 else request.messages
    conversation: list[dict] = [{"role": m.role, "content": m.content} for m in recent]
    tools = await _get_chat_tools()
    # 5 was too tight for this app's own suggested cross-entity questions
    # ("Which clients need rebalancing?", "Compare X across all accounts")
    # — the MCP tools are per-table/per-filter, not cross-entity, so
    # answering one of these can genuinely need a broad fetch plus several
    # follow-up lookups. Paired with the system prompt's now-explicit
    # "fetch broadly first" guidance below, which reduces how many rounds
    # a given question actually needs.
    max_tool_rounds = 12

    last_bedrock_err = None
    if not _chat_using_litellm_fallback:
        for _attempt in range(2):
            try:
                final_text = None
                async for evt in _run_bedrock_chat_stream(system_prompt, conversation, tools, max_tool_rounds):
                    if evt["type"] == "final_text":
                        final_text = evt["text"]
                    else:
                        yield _sse(evt)
                yield _sse({"type": "final", "result": parse_response(final_text or "")})
                return
            except Exception as attempt_err:
                last_bedrock_err = attempt_err
                print(f"[chat] Bedrock attempt {_attempt+1} failed: {type(attempt_err).__name__}: {attempt_err}", flush=True)
                if _attempt == 0:
                    yield _sse({"type": "status", "message": "Connection hiccup — retrying..."})
                    await asyncio.sleep(2)

        # Bedrock exhausted its retries — fall back to LiteLLM rather than
        # failing the request outright. Sticky: every subsequent /api/chat
        # call in this process goes straight to LiteLLM (see the check above).
        print(
            f"\n{'='*60}\n"
            f"[DATACHAT FALLBACK] Bedrock unavailable after 2 attempts.\n"
            f"                    Switching to LiteLLM ({LITELLM_MODEL}).\n"
            f"                    Last error: {last_bedrock_err}\n"
            f"{'='*60}\n",
            flush=True,
        )
        yield _sse({"type": "status", "message": "Primary AI service unavailable — switching to backup..."})
        _chat_using_litellm_fallback = True

    messages: list[dict] = [{"role": "system", "content": system_prompt}] + conversation
    last_litellm_err = None
    for _attempt in range(2):
        try:
            final_text = None
            async for evt in _run_litellm_chat_stream(messages, tools, max_tool_rounds):
                if evt["type"] == "final_text":
                    final_text = evt["text"]
                else:
                    yield _sse(evt)
            yield _sse({"type": "final", "result": parse_response(final_text or "")})
            return
        except Exception as attempt_err:
            last_litellm_err = attempt_err
            print(f"[chat] LiteLLM attempt {_attempt+1} failed: {type(attempt_err).__name__}: {attempt_err}", flush=True)
            if _attempt == 0:
                yield _sse({"type": "status", "message": "Backup connection hiccup — retrying..."})
                try:
                    await http_client.aclose()
                except Exception:
                    pass
                http_client = httpx.AsyncClient(
                    verify=_make_ssl_context(),
                    timeout=httpx.Timeout(connect=30.0, read=float(LITELLM_TIMEOUT), write=60.0, pool=30.0),
                )
                client = AsyncOpenAI(
                    api_key=LITELLM_API_KEY,
                    base_url=base_url,
                    http_client=http_client,
                    timeout=LITELLM_TIMEOUT,
                )
                await asyncio.sleep(2)

    bedrock_err_display = last_bedrock_err if last_bedrock_err is not None else "not attempted (backup already active from an earlier failure this session)"
    err_msg = f"Both Bedrock and LiteLLM failed.\n  Bedrock error: {bedrock_err_display}\n  LiteLLM error: {last_litellm_err}"
    yield _sse({"type": "error", "detail": err_msg})


@app.post("/api/chat")
async def chat(request: ChatRequest):
    # No pre-flight "is LiteLLM configured" gate here — Bedrock is primary
    # and needs no .env values at all (just AWS credentials, resolved via
    # AWS_PROFILE), so an unconfigured LITELLM_API_BASE no longer means the
    # chat feature is unusable. If BOTH providers are genuinely unreachable,
    # _stream_chat_events already reports that as a clear "error" SSE event.
    return StreamingResponse(_stream_chat_events(request), media_type="text/event-stream")


@app.get("/api/chat/health")
async def chat_health():
    """Check LLM connectivity and data API availability. Bedrock is primary
    and doesn't require .env configuration (it resolves AWS credentials via
    AWS_PROFILE) — a real reachability probe would cost a genuine Bedrock
    call on every health check, which this deliberately avoids; LiteLLM's
    backup config is reported for visibility only, not treated as required."""
    health = {
        "bedrock_model": BEDROCK_MODEL_ID,
        "aws_region": BEDROCK_REGION,
        "litellm_backup_configured": bool(LITELLM_API_BASE and LITELLM_API_KEY),
        "using_litellm_fallback": _chat_using_litellm_fallback,
        "data_api_base": DATA_API_BASE,
    }
    try:
        resp = await _data_client.get(f"{DATA_API_BASE}/api/metadata")
        health["data_api_status"] = resp.status_code
        if resp.status_code == 200:
            meta = resp.json()
            health["tables_available"] = len(meta.get("tables", []))
    except Exception as e:
        health["data_api_error"] = str(e)
    health["status"] = "healthy" if health.get("data_api_status") == 200 else "degraded"
    return health


@app.post("/api/ingest/excel")
async def ingest_excel(file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename or "upload.xlsx").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        wb = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_raw = list(ws.iter_rows(values_only=True))
            if not rows_raw:
                continue
            headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows_raw[0])]
            data_rows = [dict(zip(headers, row)) for row in rows_raw[1:]]
            schema = infer_schema(data_rows[:100])
            sheets.append({
                "name": sheet_name,
                "schema": schema,
                "rows": data_rows[:100],
                "totalRows": len(data_rows),
                "sampleRows": data_rows[:10],
            })
        wb.close()
        os.unlink(tmp_path)
        return {"sheets": sheets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        doc = fitz.open(tmp_path)
        chunks = []
        for page in doc:
            chunks.append(page.get_text())
        full_text = "\n".join(chunks)
        title = doc.metadata.get("title", "") if doc.metadata else ""
        page_count = len(doc)
        doc.close()
        os.unlink(tmp_path)

        return {
            "pages": page_count,
            "text": full_text,
            "chunks": chunks,
            "metadata": {"title": title, "pages": page_count},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/json")
async def ingest_json(request: JsonIngestRequest):
    try:
        rows = request.data
        schema = infer_schema(rows)
        return {
            "schema": schema,
            "rows": rows[:100],
            "totalRows": len(rows),
            "sampleRows": rows[:10],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
