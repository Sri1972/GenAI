#!/usr/bin/env python3
"""
Quick test client for the Figma MCP server.
Usage:
    python test_client.py                    # run the full demo
    python test_client.py --tool figma_get_status
    python test_client.py --tool figma_list_frames
    python test_client.py --tool figma_create_frame --args '{"name":"TestFrame","width":390,"height":844}'
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:7771"


def call_mcp(method: str, params: dict) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/mcp",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}


def call_tool(name: str, arguments: dict) -> dict:
    return call_mcp("tools/call", {"name": name, "arguments": arguments})


def print_result(label: str, result: dict):
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    if "result" in result:
        content = result["result"].get("content", [])
        if content:
            try:
                parsed = json.loads(content[0]["text"])
                print(json.dumps(parsed, indent=2))
            except Exception:
                print(content[0].get("text", ""))
        else:
            print(json.dumps(result["result"], indent=2))
    elif "error" in result:
        print(f"ERROR: {result['error']}")


def run_demo():
    print("Figma MCP Test Client")
    print("="*50)

    # 1. Initialize handshake
    r = call_mcp("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
    })
    print(f"\nInitialize: {r.get('result', {}).get('serverInfo', r.get('error', 'OK'))}")

    # 2. List tools
    r = call_mcp("tools/list", {})
    tools = r.get("result", {}).get("tools", [])
    print(f"\nAvailable tools ({len(tools)}):")
    for t in tools:
        print(f"  • {t['name']}")

    # 3. Check relay/Figma status
    r = call_tool("figma_get_status", {})
    print_result("figma_get_status", r)

    # 4. List existing frames
    r = call_tool("figma_list_frames", {})
    print_result("figma_list_frames", r)

    # 5. Create a test frame
    r = call_tool("figma_create_frame", {
        "name": "MCP_Test",
        "width": 390,
        "height": 844,
        "x": 2000,
        "y": 0,
        "fill": "#1a1a2e",
    })
    print_result("figma_create_frame: MCP_Test", r)

    # 6. Add a rectangle
    r = call_tool("figma_create_rectangle", {
        "frame_name": "MCP_Test",
        "name": "header",
        "x": 0, "y": 0,
        "width": 390, "height": 80,
        "fill": "#3b82f6",
    })
    print_result("figma_create_rectangle: header", r)

    # 7. Add text
    r = call_tool("figma_create_text", {
        "frame_name": "MCP_Test",
        "name": "title",
        "content": "Hello from MCP!",
        "x": 20, "y": 26,
        "font_size": 20,
        "color": "#ffffff",
        "bold": True,
    })
    print_result("figma_create_text: title", r)

    print(f"\n{'='*50}")
    print("  Demo complete. Check your Figma canvas for 'MCP_Test' frame.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", help="Call a specific tool by name")
    parser.add_argument("--args", default="{}", help="JSON arguments for the tool")
    args = parser.parse_args()

    if args.tool:
        arguments = json.loads(args.args)
        result = call_tool(args.tool, arguments)
        print_result(f"{args.tool}({args.args})", result)
    else:
        run_demo()
