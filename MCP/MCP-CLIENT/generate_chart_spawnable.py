#!/usr/bin/env python3
"""
Minimal spawnable script for Claude Desktop.
- Reads a query string from argv[1] or JSON from stdin ("{\"query\":...}").
- Connects to the local D3 MCP SSE endpoint and calls the tool `generate-d3-chart`.
- Writes the returned HTML to stdout (so the parent process can capture it).

Usage examples:
  python -u generate_chart_spawnable.py "Show a multiline chart for ..."
  echo '{"query":"Show a chart for ..."}' | python -u generate_chart_spawnable.py

Important: spawn this with the venv python and use -u (unbuffered). Do NOT run with reload/watchers.
"""
import asyncio
import sys
import json
import traceback
from mcp import ClientSession
from mcp.client.sse import sse_client

D3_MCP_SERVER_URL = "http://localhost:3000/sse"

async def main():
    # Read query: prefer argv[1], else JSON from stdin, else raw stdin
    if len(sys.argv) > 1:
        query = sys.argv[1]
        try:
            parsed = json.loads(query)
            if isinstance(parsed, dict) and "query" in parsed:
                query = parsed["query"]
        except Exception:
            pass
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            print("ERROR: provide a query as argv or JSON on stdin", file=sys.stderr)
            return 2
        try:
            parsed = json.loads(raw)
            query = parsed.get("query") if isinstance(parsed, dict) else raw.strip()
        except Exception:
            query = raw.strip()

    if not query:
        print("ERROR: empty query", file=sys.stderr)
        return 2

    tool_name = "generate-d3-chart"
    tool_args = {"query": query}

    try:
        async with sse_client(D3_MCP_SERVER_URL) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)

                # Extract HTML/text content from result
                chart_code = None
                try:
                    # Result may have .content as list of items; aggregate text/html parts
                    if hasattr(result, "content") and isinstance(result.content, list):
                        parts = []
                        for item in result.content:
                            # item may be an object with .type and .text, or just text
                            t = getattr(item, 'type', None)
                            text = None
                            if hasattr(item, 'text'):
                                text = item.text
                            elif isinstance(item, str):
                                text = item
                            # Prefer html/text parts; include anything textual
                            if isinstance(text, str) and text.strip():
                                parts.append(text)
                        if parts:
                            chart_code = '\n'.join(parts)
                    elif isinstance(result, dict):
                        # Some servers return dicts with various keys
                        chart_code = result.get('result') or result.get('html') or result.get('content') or None
                        if isinstance(chart_code, list):
                            # join list elements
                            chart_code = '\n'.join([str(x) for x in chart_code])
                    elif isinstance(result, str):
                        chart_code = result

                except Exception:
                    chart_code = None

                if chart_code:
                    # Output to stdout for parent to capture (ensure encoding and flush)
                    try:
                        # Write as utf-8 to ensure full content
                        sys.stdout.write(chart_code)
                        sys.stdout.flush()
                        return 0
                    except Exception as e:
                        print("ERROR writing chart code to stdout:", e, file=sys.stderr)
                        return 5
                else:
                    print("ERROR: no HTML/markup returned by generate-d3-chart", file=sys.stderr)
                    # Also print raw result to stderr for diagnostics
                    try:
                        print(json.dumps(result, default=str), file=sys.stderr)
                    except Exception:
                        try:
                            print(str(result), file=sys.stderr)
                        except Exception:
                            print(repr(result), file=sys.stderr)
                    return 3
    except Exception as e:
        print("EXCEPTION: " + str(e), file=sys.stderr)
        traceback.print_exc()
        return 4

if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
