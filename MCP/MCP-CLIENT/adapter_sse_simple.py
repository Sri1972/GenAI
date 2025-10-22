"""Minimal FastAPI adapter that forwards a request to the local D3 MCP SSE endpoint
and returns the generated HTML.

Usage:
  POST /generate-chart with JSON { "chart_args": {...} } OR { "query": "..." }

This file is intentionally small and depends only on `fastapi`, `uvicorn` and your
local `mcp` package (the MCP SSE client is used to call the D3 MCP server).
"""
import os
import json
import asyncio
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# D3 MCP SSE endpoint
D3_MCP_SERVER_URL = "http://localhost:3000/sse"

# import mcp SSE client
from mcp.client.sse import sse_client
from mcp import ClientSession

app = FastAPI(title="D3 SSE -> HTTP adapter (simple)")

class ChartRequest(BaseModel):
    chart_args: Optional[Dict[str, Any]] = None
    query: Optional[str] = None
    tool_name: Optional[str] = "generate-d3-chart"


@app.post("/generate-chart", response_class=HTMLResponse)
async def generate_chart(req: ChartRequest):
    tool_name = req.tool_name or "generate-d3-chart"
    chart_args = req.chart_args if req.chart_args is not None else ({"query": req.query} if req.query else {})
    if not chart_args:
        raise HTTPException(status_code=400, detail="Provide chart_args or query in the request body")

    try:
        async with sse_client(D3_MCP_SERVER_URL) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, chart_args)

                # Try to find generated HTML in result.content
                chart_code = None
                if hasattr(result, "content") and isinstance(result.content, list):
                    for item in result.content:
                        if getattr(item, "type", None) == "text" and hasattr(item, "text"):
                            chart_code = item.text
                            break
                        if getattr(item, "type", None) == "html" and hasattr(item, "text"):
                            chart_code = item.text
                            break

                # Fallback shapes
                if not chart_code:
                    if isinstance(result, dict):
                        chart_code = result.get("result") or result.get("html") or result.get("content")
                    elif isinstance(result, str):
                        chart_code = result

                if chart_code and ("<html" in chart_code.lower() or "<svg" in chart_code.lower() or "<!doctype" in chart_code.lower()):
                    return HTMLResponse(content=chart_code, status_code=200)
                elif chart_code:
                    safe = "<pre style='white-space:pre-wrap;font-family:monospace;'>%s</pre>" % (chart_code.replace("<","&lt;").replace(">","&gt;"))
                    return HTMLResponse(content=safe, status_code=200)

                return JSONResponse(content={"result": str(result)}, status_code=200)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Adapter error: {exc}")
