from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv
import json
from openai import OpenAI
from PIL import Image
from datetime import datetime
import re

# D3 MCP server SSE endpoint
D3_MCP_SERVER_URL = "http://localhost:3000/sse"
from mcp.client.sse import sse_client

# System context for LLM
system_context = """
You are a PMO assistant.
Guidelines:
- Always call a tool instead of guessing answers.
- Always call a data tool and return real data for every user query.
- Always review the resource and prompts for the tools being used
- When a tool returns data, output ONLY the raw JSON from that tool.
- Use `get_all_projects` only when no filters are mentioned.
- Use `get_filtered_projects` if the user provides filters such as strategic_portfolio, product_line, technology_project.
- To get the values for strategic_portfolio or product_line, use `get_business_lines`.
- If the user asks for details of a project, then it means we need to get all columns from the `get_filtered_projects` tool and pass fields array values = "all_columns" to it. If we need hours, cost or resource information, then specifically ask for that.
- Always use the raw JSON from the tool outputs.
- The user may ask for some mathematical calculations on numeric fields like project_resource_cost_planned, project_resource_hours_planned etc. which has to be done.
- When a user asks for mathematical calculations on numeric fields, please provide the project name, strategic_portfolio, product_line, start_date, end_date, resource hours planned and resource cost planned for each project in the summary.
- When a user asks for mathematical calculations on numeric fields, only show non-zero values in the list
- For any of the user query response, please try and provide your analysis based on the data that you feel is important. Include hours, costs, trends, patterns, or insights that can help in decision-making.
- Look out for information on whether cumulative or non cumulative data is requested or not.
- When building out charts for which the D3_MCP_SERVER_URL MCP server is used, please look for the query from the user to understand which fields from the PMO MCP and DO NOT use cumulative fields but only the other fields.
"""

load_dotenv(".env")
openai_api_key = os.getenv("OPENAI_API_KEY")

server_params = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"]
)

def wrap_content(content: str):
    """Wrap resource/prompt content safely as OpenAI system message format."""
    return content

async def fetch_resource_allocation_data(session, resource_id, start_date, end_date, interval="Weekly"):
    """Fetch resource allocation data from PMO MCP."""
    tool_name = "get_resource_allocation_planned_actual"
    tool_args = {
        "resource_id": resource_id,
        "start_date": start_date,
        "end_date": end_date,
        "interval": interval
    }
    print(f"➡️ Calling tool '{tool_name}' with params: {json.dumps(tool_args, indent=2)}")
    tool_result = await session.call_tool(tool_name, tool_args)
    print("📊 Raw data result:")
    print(tool_result)
    return tool_result

async def create_chart_with_d3(chart_type, chart_args):
    """Call D3 MCP server via SSE and print generated D3 chart code. Also save to HTML file."""
    tool_name = "generate-d3-chart"
    async with sse_client(D3_MCP_SERVER_URL) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            print(f"✅ D3 MCP session initialized at {D3_MCP_SERVER_URL}")
            print(f"🔧 Calling tool '{tool_name}' with args: {json.dumps(chart_args, indent=2)}")
            result = await session.call_tool(tool_name, chart_args)
            chart_code = None
            if hasattr(result, "content") and isinstance(result.content, list):
                for item in result.content:
                    if getattr(item, "type", None) == "text" and hasattr(item, "text"):
                        chart_code = item.text
                        print("\n[Generated D3 Chart Code/Markup]:\n")
                        print(chart_code)
            # Save to file if chart_code is available
            if chart_code:
                output_path = "output_chart.html"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(chart_code)
                print(f"\n✅ Chart HTML saved to: {output_path}")
            return result

async def run(query: str):
    try:
        print("🚀 Starting PMO MCP client...")
        async with stdio_client(server_params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                print("✅ MCP session initialized")

                # Let the LLM decide which tool to call and with what arguments
                tools_result = await session.list_tools()
                resources_result = await session.list_resources()
                prompts_result = await session.list_prompts()
                resources = resources_result.resources
                prompts = prompts_result.prompts
                print(f"📊 Loaded: {len(tools_result.tools)} tools, {len(resources)} resources, {len(prompts)} prompts")

                # Compose system messages for LLM
                system_messages = [
                    {"role": "system", "content": system_context}
                ]
                for resource in resources:
                    content = getattr(resource, "content", None) or getattr(resource, "_content", None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({
                            "role": "system",
                            "content": f"[{resource.name}] {wrap_content(content)}"
                        })
                for prompt in prompts:
                    content = getattr(prompt, "content", None) or getattr(prompt, "_content", None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({
                            "role": "system",
                            "content": f"[{prompt.name}] {wrap_content(content)}"
                        })
                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        },
                    }
                    for tool in tools_result.tools
                ]
                messages = system_messages + [{"role": "user", "content": query}]
                client = OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                assistant_msg = response.choices[0].message
                messages.append(assistant_msg.model_dump())
                max_iterations = 3
                iteration = 0
                tool_calls = getattr(assistant_msg, "tool_calls", [])
                last_tool_output = None
                called_tools = set()
                # Phase 1: Tool calling (LLM-driven)
                while tool_calls and iteration < max_iterations:
                    iteration += 1
                    tool_names = [tc.function.name for tc in tool_calls]
                    print(f"🔧 Iteration {iteration}: Calling {', '.join(tool_names)}")
                    responded_tool_call_ids = set()
                    for tool_execution in tool_calls:
                        try:
                            tool_name = tool_execution.function.name
                            tool_args = json.loads(tool_execution.function.arguments) if tool_execution.function.arguments else {}
                            print(f"➡️ Calling tool '{tool_name}' with params: {json.dumps(tool_args, indent=2)}")
                            tool_result = await session.call_tool(tool_name, tool_args)
                            called_tools.add(tool_name)
                            # Extract actual data if it's a data tool
                            if tool_name.startswith("get_") and "chart" not in tool_name:
                                if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                    data = tool_result.structuredContent.get('result', tool_result.structuredContent)
                                elif hasattr(tool_result, 'content') and isinstance(tool_result.content, list):
                                    data = [json.loads(item.text) for item in tool_result.content]
                                elif isinstance(tool_result, dict):
                                    data = tool_result.get('result', tool_result)
                                else:
                                    print("❌ Could not extract data from tool_result!")
                                    continue
                                last_tool_output = data
                            else:
                                last_tool_output = tool_result
                            # --- FIX: Append tool message for each tool_call_id ---
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_execution.id,
                                "name": tool_name,
                                "content": str(tool_result)
                            })
                            responded_tool_call_ids.add(tool_execution.id)
                        except Exception as tool_error:
                            print(f"❌ Error in tool '{tool_execution.function.name}': {tool_error}")
                            traceback.print_exc()
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_execution.id,
                                "name": tool_execution.function.name,
                                "content": f"Error: {str(tool_error)}"
                            })
                            responded_tool_call_ids.add(tool_execution.id)
                    # Ensure all tool_call_ids have a response
                    for tc in tool_calls:
                        if tc.id not in responded_tool_call_ids:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.function.name,
                                "content": "No result"
                            })
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                    )
                    assistant_msg = response.choices[0].message
                    messages.append(assistant_msg.model_dump())
                    tool_calls = getattr(assistant_msg, "tool_calls", [])
                # Phase 2: Reasoning over tool output
                print("🎯 MCP Tool Output (Raw JSON)")
                print("=" * 60)
                if last_tool_output:
                    print(last_tool_output)
                    # Error check: If last_tool_output is an error response, do not chart
                    if (isinstance(last_tool_output, list) and last_tool_output and isinstance(last_tool_output[0], dict) and "error" in last_tool_output[0]):
                        print(f"[ERROR] Data tool returned error: {last_tool_output[0]['error']}")
                        return  # Stop chart workflow on error
                    # If last_tool_output is a list of dicts (data), generate chart
                    if isinstance(last_tool_output, list) and all(isinstance(x, dict) for x in last_tool_output):
                        # Determine whether the user explicitly requested cumulative data in their query
                        user_wants_cumulative = False
                        try:
                            # 'query' is the original user query passed to run()
                            if isinstance(query, str) and re.search(r"\bcumul(ative)?\b", query, flags=re.IGNORECASE):
                                user_wants_cumulative = True
                        except Exception:
                            user_wants_cumulative = False

                        # Helper to remove cumulative-like fields from the data
                        def strip_cumulative_columns(rows):
                            def is_cumul_field(name):
                                if not isinstance(name, str):
                                    return False
                                n = name.lower()
                                return ("cumul" in n) or ("cumulative" in n) or ("_cumulative" in n)
                            return [{k: v for k, v in row.items() if not is_cumul_field(k)} for row in rows]

                        # Choose the data to use for charting: filter out cumulative fields by default
                        data_for_chart = last_tool_output
                        if not user_wants_cumulative:
                            try:
                                filtered = strip_cumulative_columns(last_tool_output)
                                # If filtering leaves numeric series, use it; otherwise keep original and warn
                                if filtered and isinstance(filtered[0], dict):
                                    numeric_keys = [k for k, v in filtered[0].items() if isinstance(v, (int, float))]
                                    if numeric_keys:
                                        data_for_chart = filtered
                                        print("[INFO] Removed cumulative fields for charting (user did not request cumulative data).")
                                    else:
                                        print("[WARN] Removing cumulative fields would remove all numeric series; using original data including cumulative fields.")
                                else:
                                    print("[WARN] Filter step returned unexpected structure; using original data.")
                            except Exception as e:
                                print(f"[WARN] Error filtering cumulative fields: {e}; using original data.")

                        # --- Chart generation logic ---
                        # 1. Multi-line (if data has multiple series fields)
                        multiline_fields = [k for k in data_for_chart[0].keys() if k not in ("month", "date", "category", "label", "week_start", "week_end")]
                        time_fields = ("month", "date", "week_start", "week_end")
                        if len(multiline_fields) >= 2 and any(f in data_for_chart[0] for f in time_fields):
                            await run_chart("multi-line", data_for_chart, features=["legend", "tooltip"])
                        # 2. Bar
                        elif "category" in data_for_chart[0] or "name" in data_for_chart[0] or "project_name" in data_for_chart[0]:
                            await run_chart("bar", data_for_chart, features=["tooltip"])
                        # 3. Pie
                        elif "label" in data_for_chart[0]:
                            await run_chart("pie", data_for_chart, features=["legend"])
                        else:
                            print("[INFO] No recognized chart type for data fields.")
                else:
                    print("⚠️ No tool output, assistant said:")
                    print(assistant_msg.content)
                    # --- Fallback: If no tool was called, call get_all_projects and try charting ---
                    print("[Fallback] No tool call detected. Fetching all projects for charting...")
                    try:
                        tool_result = await session.call_tool("get_all_projects", {})
                        if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                            data = tool_result.structuredContent.get('result', tool_result.structuredContent)
                        elif hasattr(tool_result, 'content') and isinstance(tool_result.content, list):
                            data = [json.loads(item.text) for item in tool_result.content]
                        elif isinstance(tool_result, dict):
                            data = tool_result.get('result', tool_result)
                        else:
                            print("❌ Could not extract data from fallback tool_result!")
                            return
                        print("[Fallback] Data fetched, attempting chart...")
                        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
                            multiline_fields = [k for k in data[0].keys() if k not in ("month", "date", "category", "label")]
                            if len(multiline_fields) >= 2 and ("month" in data[0] or "date" in data[0]):
                                await run_chart("multi-line", data, features=["legend", "tooltip"])
                            elif "category" in data[0] or "name" in data[0] or "project_name" in data[0]:
                                await run_chart("bar", data, features=["tooltip"])
                            elif "label" in data[0]:
                                await run_chart("pie", data, features=["legend"])
                            else:
                                print("[INFO] No recognized chart type for fallback data fields.")
                    except Exception as fallback_error:
                        print(f"[Fallback Error] {fallback_error}")
                        traceback.print_exc()
    except Exception as e:
        print(f"❌ Client Error: {e}")
        traceback.print_exc()

# Chart generation logic (from sample-charts-client.py)
openai_client = OpenAI(api_key=openai_api_key)

async def run_chart(chart_type, data, features=None, chart_type_hint=None):
    features = features or []
    # For bar charts, if there are multiple numeric fields, request a grouped (multi-bar) chart with a color palette and legend below the chart
    if chart_type == "bar":
        if data and isinstance(data, list) and isinstance(data[0], dict):
            keys = list(data[0].keys())
            x_candidates = [k for k in keys if k.lower() in ("project_name", "name", "category", "label")]
            y_candidates = [k for k in keys if k not in x_candidates and isinstance(data[0][k], (int, float))]
            if len(y_candidates) > 1:
                bar_features = features + [
                    "grouped", "multi-bar", "legend", "color palette", "legend below chart", "no extra comments", "header", "tooltip", "labels",
                    "legend should use a flexbox div below the chart, with each legend item showing a colored square (for bar) or circle (for line) and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes",
                    "Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels."
                ]
                prompt = f"Generate a complete D3.js v7 grouped (multi-bar) bar chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nX-axis: {x_candidates[0] if x_candidates else 'category'}; Y-axis: {', '.join(y_candidates)}. Each bar group should represent a {x_candidates[0] if x_candidates else 'category'}, and each bar in the group should represent one of the numeric fields. Use a distinct color palette for each bar. Place the legend below the chart. Only include key elements: header, legend, tooltip, labels, and axis. Do not include any extra comments or descriptions. The legend must use a flexbox div below the chart, with each legend item showing a colored square and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes. Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels. Output a complete HTML file with embedded JS and CSS."
            else:
                prompt = f"Generate a complete D3.js v7 bar chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nFeatures: header, legend, tooltip, labels, axis, color palette, legend below chart, no extra comments, legend should use a flexbox div below the chart, with each legend item showing a colored square and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes. Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels. Output a complete HTML file with embedded JS and CSS."
        else:
            prompt = f"Generate a complete D3.js v7 bar chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nFeatures: header, legend, tooltip, labels, axis, color palette, legend below chart, no extra comments, legend should use a flexbox div below the chart, with each legend item showing a colored square and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes. Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels. Output a complete HTML file with embedded JS and CSS."
    else:
        # For multi-line charts, enforce consistent style: lines only, no dots, no area shading
        if chart_type == "multi-line":
            prompt = f"Generate a complete D3.js v7 multi-line chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nFeatures: header, legend, tooltip, labels, axis, color palette, legend below chart, no extra comments. Show only lines for each series, do not include any dots, markers, or area shading/fill under the lines. Do not add scatter points or circles, only lines. The legend should use a flexbox div below the chart, with each legend item showing a colored circle and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes. Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels. Output a complete HTML file with embedded JS and CSS."
        else:
            prompt = f"Generate a complete D3.js v7 {chart_type} chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nFeatures: header, legend, tooltip, labels, axis, color palette, legend below chart, no extra comments, legend should use a flexbox div below the chart, with each legend item showing a colored circle and label, aligned and spaced nicely, using display:flex, align-items:center, gap:20px, margin-top:30px; the color must match the series color exactly; do not use SVG for the legend; only use HTML/CSS for the legend; legend must never overlap the chart or axes. Always show clear, descriptive X and Y axis labels. Never show 'NaN', 'undefined', or empty labels. Format all axis ticks and labels as human-readable values. Validate data before rendering labels. Output a complete HTML file with embedded JS and CSS."
    print(f"\n=== {chart_type.upper()} CHART TEST (OpenAI LLM) ===")
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a D3.js expert. Generate beautiful, robust, and safe D3.js v7 code for the user's request. Always output a complete HTML file."},
            {"role": "user", "content": prompt}
        ]
    )
    chart_code = response.choices[0].message.content
    # Remove any leading markdown code block markers (e.g., ```html or ```)
    chart_code = re.sub(r"^```[a-zA-Z]*\s*", "", chart_code)
    chart_code = re.sub(r"```$", "", chart_code).strip()
    # Remove the first <p>...</p> block (chart description) if present
    chart_code = re.sub(r"<p>.*?</p>\s*", "", chart_code, count=1, flags=re.DOTALL)
    # --- Inject consistent axis line thickness CSS ---
    # If <style> exists, append or replace .domain rule; else, add <style> block in <head>
    domain_css = ".domain { stroke-width: 1.5; }"
    if "<style" in chart_code:
        # Try to replace any .domain rule
        chart_code = re.sub(r"(\.domain\s*\{[^}]*?)(stroke-width\s*:\s*[^;]+;)?([^}]*\})", lambda m: f".domain {{ {domain_css} {' '.join([x for x in [m.group(1), m.group(3)] if x])} }}", chart_code, flags=re.DOTALL)
        # If no .domain rule, just append
        if ".domain {" not in chart_code:
            chart_code = re.sub(r"(<style[^>]*>)", r"\1\n" + domain_css + "\n", chart_code, count=1)
    else:
        # Insert <style> block in <head>
        chart_code = re.sub(r"(<head[^>]*>)", r"\1\n<style>" + domain_css + "</style>", chart_code, count=1)
    print("\n[Generated D3 Chart Code/Markup]:\n")
    print(chart_code[:500] + ("..." if len(chart_code) > 500 else ""))
    if chart_code:
        from datetime import datetime
        import os
        os.makedirs("html-charts", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = os.path.join("html-charts", f"output_{chart_type}_chart_{timestamp}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(chart_code)
        print(f"\n✅ Chart HTML saved to: {output_path}")
    else:
        print("❌ No chart code generated.")

if __name__ == "__main__":
    import asyncio
    query = "Show a multiline chart in weekly intervals for planned and actual hours for resource id 2 for 2025."
    #query = "Show a bar chart for planned, actual and capacity hours and costs for projects in the Market & Sell portfolio"
    asyncio.run(run(query))