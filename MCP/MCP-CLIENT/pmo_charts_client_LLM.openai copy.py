from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv
import json
from openai import OpenAI
from pyecharts.charts import Line
from pyecharts import options as opts
from pyecharts.render import make_snapshot
from snapshot_selenium import snapshot
from PIL import Image
from datetime import datetime

# System context for LLM
system_context = """
You are a PMO assistant.
Guidelines:
- Always call a tool instead of guessing answers.
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

# MCP ECharts server parameters for STDIO
server_params_echarts = StdioServerParameters(
    command="node",
    args=[r"D:\\GenAI\\MCP\\CHARTS\\mcp-echarts\\build\\index.js"],
    env={**os.environ, "TRANSPORT_TYPE": "stdio"}
)

async def create_chart_with_echarts(chart_type, chart_args):
    """Call MCP ECharts server via STDIO and render chart PNG using pyecharts."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    # Prepare tool name and args
    tool_name = f"generate_{chart_type}_chart"
    async with stdio_client(server_params_echarts) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            print("✅ MCP ECharts session initialized")
            print(f"🔧 Calling tool '{tool_name}' with args: {json.dumps(chart_args, indent=2)}")
            result = await session.call_tool(tool_name, chart_args)
            print(f"[DEBUG] Full MCP ECharts result: {result}")
            # Generate unique filename (move this up before image extraction)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            images_dir = os.path.abspath("images")
            os.makedirs(images_dir, exist_ok=True)
            chart_type_name = f"{chart_type}_chart"
            json_file = os.path.join(images_dir, f"{chart_type_name}_{timestamp}.json")
            html_file = os.path.join(images_dir, f"{chart_type_name}_{timestamp}.html")
            png_file = os.path.join(images_dir, f"{chart_type_name}_{timestamp}.png")
            # Extract JSON option
            chart_option_json = None
            image_b64 = None
            if hasattr(result, "content"):
                if isinstance(result.content, list):
                    for item in result.content:
                        # Use getattr/hasattr for Pydantic objects
                        if getattr(item, "type", None) == "image" and getattr(item, "mimeType", None) == "image/png" and hasattr(item, "data"):
                            image_b64 = item.data
                        elif getattr(item, "type", None) == "text" and hasattr(item, "text"):
                            chart_option_json = item.text
                # If no text found, fallback to first item text if available
                if not chart_option_json and isinstance(result.content, list):
                    for item in result.content:
                        if hasattr(item, "text"):
                            chart_option_json = item.text
                            break
            # If image found, save/open it and return
            if image_b64:
                import base64
                if image_b64.startswith("data:image/png;base64,"):
                    image_b64 = image_b64.split(",", 1)[1]
                with open(png_file, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                print(f"✅ Chart PNG created: {png_file}")
                img = Image.open(png_file)
                img.show()
                # Delete temp files
                try:
                    os.remove(json_file)
                except Exception:
                    pass
                return png_file
            # If outputType is 'option', just print the config for debugging
            if chart_option_json:
                print("[DEBUG] MCP Bar Chart Config:", chart_option_json)
                # Save chart config JSON to file
                try:
                    with open(json_file, "w", encoding="utf-8") as jf:
                        if isinstance(chart_option_json, str):
                            jf.write(chart_option_json)
                        else:
                            json.dump(chart_option_json, jf, indent=2)
                    print(f"✅ Bar chart JSON config saved: {json_file}")
                except Exception as e:
                    print(f"[ERROR] Could not save bar chart JSON config: {e}")
                # Print the 'data' part for MCP inspector
                try:
                    if isinstance(chart_option_json, str):
                        chart_json = json.loads(chart_option_json)
                    else:
                        chart_json = chart_option_json
                    if "series" in chart_json:
                        for s in chart_json["series"]:
                            print(f"[MCP Inspector] Bar Chart Series '{s.get('name', '')}':")
                            print(json.dumps(s.get("data", []), indent=2))
                    elif "data" in chart_json:
                        print("[MCP Inspector] Bar Chart Data:")
                        print(json.dumps(chart_json["data"], indent=2))
                except Exception as e:
                    print(f"[ERROR] Could not parse chart_option_json for MCP Inspector: {e}")
                print("⚠️ No PNG image found in MCP ECharts result. Check outputType and server config.")
                return chart_option_json
            print("❌ No chart option or image returned from MCP ECharts.")
            return

def transform_to_echarts_line_chart(data, x_field, y_fields, title):
    x_axis = [row[x_field] for row in data]
    series = []
    for y_field in y_fields:
        series.append({
            "name": y_field,
            "data": [row[y_field] for row in data],
            "smooth": False,
            "showSymbol": True
        })
    return {
        "title": {"text": title},
        "xAxis": {"data": x_axis, "name": x_field, "type": "category", "boundaryGap": False},
        "yAxis": {"name": "Value", "type": "value"},
        "series": series,
        "legend": {"orient": "horizontal", "left": "center", "bottom": "bottom"},
        "tooltip": {"trigger": "axis"}
    }

def flatten_multiline_chart_data(data, x_field, y_fields):
    flat_data = []
    for row in data:
        for y_field in y_fields:
            flat_data.append({
                "group": y_field,
                "time": row[x_field],
                "value": row[y_field]
            })
    return flat_data

def transform_to_echarts_bar_chart(data, category_field, value_fields, title):
    """
    Transform project data for MCP ECharts bar chart tool.
    Returns: {
        "title": str,
        "series": [
            {"name": value_field, "data": [{"category": str, "value": number}, ...]}
        ],
        "data": [...original data array...]
    }
    """
    series = []
    for value_field in value_fields:
        series.append({
            "name": value_field,
            "data": [
                {"category": row[category_field], "value": row.get(value_field, 0)}
                for row in data if category_field in row and value_field in row
            ]
        })
    return {
        "title": title,
        "series": series,
        "data": data
    }

def build_grouped_bar_chart_config(data, category_field, value_fields, title):
    """
    Build a grouped bar chart config for MCP ECharts server (flat data array with group field).
    - title: string
    - data: original data array
    - group: True
    - legend: always present
    - data: [{category, value, group} ...]
    """
    color_palette = [
        '#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE',
        '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC'
    ]
    flat_data = []
    for row in data:
        for idx, value_field in enumerate(value_fields):
            if category_field in row and value_field in row:
                flat_data.append({
                    "category": row[category_field],
                    "value": row[value_field],
                    "group": value_field
                })
    config = {
        "title": str(title),
        "axisXTitle": category_field,
        "axisYTitle": "Value",
        "data": flat_data,
        "height": 600,
        "width": 800,
        "theme": "default",
        "outputType": "png",
        "group": True,
        "legend": {"show": True, "orient": "horizontal", "left": "center", "bottom": "bottom"}
    }
    print("[DEBUG] Final grouped bar chart config for MCP:")
    print(json.dumps(config, indent=2))
    return config

async def create_chart_from_data(chart_type, chart_args):
    # For line charts, flatten to MCP ECharts expected format
    if chart_type == "line" and "x_field" in chart_args and "y_fields" in chart_args:
        chart_args = {
            "axisXTitle": chart_args["x_field"],
            "axisYTitle": "Value",
            "title": chart_args["title"],
            "data": flatten_multiline_chart_data(chart_args["data"], chart_args["x_field"], chart_args["y_fields"]),
            "height": 600,
            "width": 800,
            "showArea": False,
            "showSymbol": True,
            "smooth": False,
            "stack": False,
            "theme": "default",
            "outputType": "png"  # Always request PNG output for line charts
        }
        return await create_chart_with_echarts(chart_type, chart_args)
    # For bar charts, transform to MCP ECharts multi-series/grouped schema
    elif chart_type == "bar" and "data" in chart_args and "y_fields" in chart_args and "x_field" in chart_args:
        # Use build_grouped_bar_chart_config to build correct MCP-compliant grouped bar config
        bar_chart_args = build_grouped_bar_chart_config(
            chart_args["data"],
            chart_args["x_field"],
            chart_args["y_fields"],
            chart_args["title"]
        )
        return await create_chart_with_echarts(chart_type, bar_chart_args)

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

                # Inject chart smart decision resources FIRST in system context for chart requests
                with open(r"d:/GenAI/MCP/CHARTS/resources/docs_chart_smart_decision.txt", "r", encoding="utf-8") as f:
                    chart_smart_decision_resource = f.read()
                with open(r"d:/GenAI/MCP/CHARTS/prompts/chart_smart_decision.txt", "r", encoding="utf-8") as f:
                    chart_smart_decision_prompt = f.read()
                system_messages = [
                    {"role": "system", "content": chart_smart_decision_resource},
                    {"role": "system", "content": chart_smart_decision_prompt},
                    {"role": "system", "content": "IMPORTANT: If the user asks for a chart, visualization, or distribution, you MUST call the appropriate MCP ECharts chart tool (e.g., generate_line_chart, generate_bar_chart) and NOT a data tool. Only call data tools if the user requests raw data, not a chart."},
                    {"role": "system", "content": system_context}
                ]
                # Load chart tool usage guidelines and append to system context
                with open(r"d:/GenAI/MCP/CHARTS/prompts/chart_tools_usage.txt", "r", encoding="utf-8") as f:
                    chart_tools_usage = f.read()
                system_messages.append({
                    "role": "system",
                    "content": f"Chart Tool Usage:\n{chart_tools_usage}"
                })
                # Load bar chart schema and inject into LLM system context
                with open(r"d:/GenAI/MCP/CHARTS/resources/docs_chart_bar_schema.txt", "r", encoding="utf-8") as f:
                    bar_chart_schema = f.read()
                system_messages.append({
                    "role": "system",
                    "content": f"Bar Chart Tool Schema:\n{bar_chart_schema}"
                })
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
                            # Suppress redundant get_all_projects/get_all_resources calls
                            if tool_name in {"get_all_projects", "get_all_resources"}:
                                # Only allow if user query explicitly requests it
                                if any(kw in query.lower() for kw in ["all projects", "all resources"]):
                                    print(f"[INFO] Calling {tool_name} as user explicitly requested it.")
                                elif any(t for t in called_tools if not t.startswith("get_all_")):
                                    print(f"[SUPPRESS] Skipping redundant call to {tool_name} after chart/data tool.")
                                    responded_tool_call_ids.add(tool_execution.id)
                                    continue
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
                                # If the next tool call is a chart, pass the data
                                last_tool_output = data
                            else:
                                last_tool_output = tool_result
                            # If chart tool, handle image_base64 or chain to chart MCP if only data is returned
                            if "chart" in tool_name:
                                print(f"[DEBUG] Chart tool response: {tool_result}")
                                image_b64 = None
                                # Try to extract image_base64
                                if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                    image_b64 = tool_result.structuredContent.get('image_base64')
                                elif hasattr(tool_result, 'content') and isinstance(tool_result.content, dict):
                                    image_b64 = tool_result.content.get('image_base64')
                                elif isinstance(tool_result, dict):
                                    image_b64 = tool_result.get('image_base64')
                                # If image found, save/open it
                                if image_b64:
                                    import base64, datetime, platform
                                    if image_b64.startswith("data:image/png;base64,"):
                                        image_b64 = image_b64.split(",", 1)[1]
                                    images_dir = os.path.abspath("images")
                                    if not os.path.exists(images_dir):
                                        os.makedirs(images_dir)
                                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                    output_filename = f"{tool_name}_chart_{timestamp}.png"
                                    output_path = os.path.join(images_dir, output_filename)
                                    with open(output_path, "wb") as f:
                                        f.write(base64.b64decode(image_b64))
                                    print(f"✅ Chart saved as {output_path}. Opening...")
                                    if platform.system() == "Windows":
                                        os.startfile(output_path)
                                    elif platform.system() == "Darwin":
                                        os.system(f"open '{output_path}'")
                                    else:
                                        os.system(f"xdg-open '{output_path}'")
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_execution.id,
                                        "name": tool_name,
                                        "content": str(tool_result)
                                    })
                                    responded_tool_call_ids.add(tool_execution.id)
                                    continue
                                # If no image, but result looks like data, chain to chart MCP
                                # Try to extract data from tool_result
                                if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                    data = tool_result.structuredContent.get('result', tool_result.structuredContent)
                                elif hasattr(tool_result, 'content') and isinstance(tool_result.content, list):
                                    data = [json.loads(item.text) for item in tool_result.content]
                                elif isinstance(tool_result, dict):
                                    data = tool_result.get('result', tool_result)
                                else:
                                    data = None
                                if data:
                                    print("[INFO] No image found, chaining to CHARTS MCP for charting...")
                                    chart_type = "line"  # You may want to infer this from the query/tool_args
                                    chart_args = tool_args.copy()
                                    chart_args["data"] = data
                                    await create_chart_from_data(chart_type, chart_args)
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_execution.id,
                                        "name": tool_name,
                                        "content": str(tool_result)
                                    })
                                    responded_tool_call_ids.add(tool_execution.id)
                                    continue
                                print("⚠️ No image_base64 or data found in chart tool result.")
                                # Print error if present
                                if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                    error = tool_result.structuredContent.get('error')
                                    if error:
                                        print(f"[ERROR] Chart tool error: {error}")
                                elif hasattr(tool_result, 'content') and isinstance(tool_result.content, dict):
                                    error = tool_result.content.get('error')
                                    if error:
                                        print(f"[ERROR] Chart tool error: {error}")
                                elif isinstance(tool_result, dict):
                                    error = tool_result.get('error')
                                    if error:
                                        print(f"[ERROR] Chart tool error: {error}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_execution.id,
                                    "name": tool_name,
                                    "content": str(tool_result)
                                })
                                responded_tool_call_ids.add(tool_execution.id)
                                continue
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
                    # Ensure all tool_call_ids from last assistant message are responded to before reasoning
                    if hasattr(assistant_msg, "tool_calls") and assistant_msg.tool_calls:
                        existing_tool_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
                        for tc in assistant_msg.tool_calls:
                            if tc.id not in existing_tool_ids:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": tc.function.name,
                                    "content": "No result"
                                })
                    messages.append({
                        "role": "user",
                        "content": f"Here is the raw JSON result:\n{last_tool_output}\n\nNow, based on my original query ('{query}'), please compute and explain the answer."
                    })
                    reasoning_response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages
                    )
                    print("\n🤖 LLM Reasoning Response")
                    print("=" * 60)
                    print(reasoning_response.choices[0].message.content)
                    # If last_tool_output is a list of dicts (data), and no chart was generated, call chart MCP
                    if isinstance(last_tool_output, list) and all(isinstance(x, dict) for x in last_tool_output):
                        print("[INFO] No chart generated by LLM, requesting chart tool call from LLM using chart MCP smart decision prompt/resource...")
                        # Load chart MCP smart decision prompt/resource
                        with open(r"d:/GenAI/MCP/CHARTS/prompts/chart_smart_decision.txt", "r", encoding="utf-8") as f:
                            chart_smart_decision_prompt = f.read()
                        with open(r"d:/GenAI/MCP/CHARTS/resources/docs_chart_smart_decision.txt", "r", encoding="utf-8") as f:
                            chart_smart_decision_resource = f.read()
                        # Compose LLM message
                        chart_llm_messages = [
                            {"role": "system", "content": chart_smart_decision_resource},
                            {"role": "system", "content": chart_smart_decision_prompt},
                            {"role": "user", "content": f"User Query: {query}\nData: {json.dumps(last_tool_output, indent=2)}\nPlease select the best chart type and generate the correct chart tool call and arguments for CHARTS MCP."}
                        ]
                        chart_response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=chart_llm_messages,
                            tools=openai_tools,
                            tool_choice="auto",
                        )
                        chart_assistant_msg = chart_response.choices[0].message
                        chart_tool_calls = getattr(chart_assistant_msg, "tool_calls", [])
                        if chart_tool_calls:
                            print(f"[LLM Chart Tool Call] {chart_tool_calls}")
                            for chart_tool_execution in chart_tool_calls:
                                try:
                                    chart_tool_name = chart_tool_execution.function.name
                                    chart_tool_args = json.loads(chart_tool_execution.function.arguments) if chart_tool_execution.function.arguments else {}
                                    print(f"➡️ Calling chart tool '{chart_tool_name}' with params: {json.dumps(chart_tool_args, indent=2)}")
                                    # ENFORCE: If chart_tool_name is a data tool, immediately call chart MCP with the result
                                    if chart_tool_name.startswith("get_"):
                                        # Call the data tool, get the result, then call chart MCP
                                        data_tool_result = await session.call_tool(chart_tool_name, chart_tool_args)
                                        # Extract data from result
                                        if hasattr(data_tool_result, 'structuredContent') and data_tool_result.structuredContent:
                                            data = data_tool_result.structuredContent.get('result', data_tool_result.structuredContent)
                                        elif hasattr(data_tool_result, 'content') and isinstance(data_tool_result.content, list):
                                            data = [json.loads(item.text) for item in data_tool_result.content]
                                        elif isinstance(data_tool_result, dict):
                                            data = data_tool_result.get('result', data_tool_result)
                                        else:
                                            data = None
                                        if data:
                                            print("[ENFORCED] Data tool called, now chaining to MCP ECharts chart tool...")
                                            chart_args = {
                                                "data": data,
                                                "x_field": "month" if "month" in data[0] else list(data[0].keys())[0],
                                                "y_fields": [k for k in data[0].keys() if k != "month" and isinstance(data[0][k], (int, float))],
                                                "title": query.strip().replace("\n", " ")
                                            }
                                            await create_chart_from_data("line", chart_args)
                                        continue
                                    # Otherwise, call chart MCP as usual
                                    chart_tool_result = await create_chart_from_data(chart_tool_name.replace('generate_', '').replace('_chart', ''), chart_tool_args)
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": chart_tool_execution.id,
                                        "name": chart_tool_name,
                                        "content": str(chart_tool_result)
                                    })
                                except Exception as chart_tool_error:
                                    print(f"❌ Error in chart tool call: {chart_tool_error}")
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": chart_tool_execution.id,
                                        "name": chart_tool_name,
                                        "content": f"Error: {str(chart_tool_error)}"
                                    })
                        else:
                            print("⚠️ LLM did not produce a valid chart tool call. Falling back to generic chart.")
                            # Respond to all previous tool_call_ids with a tool message (empty or fallback info)
                            prev_tool_calls = getattr(chart_assistant_msg, "tool_calls", None)
                            if prev_tool_calls:
                                for prev_tool_call in prev_tool_calls:
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": prev_tool_call.id,
                                        "name": prev_tool_call.function.name,
                                        "content": "[Fallback] No valid tool call, using generic chart logic."
                                    })
                            # Fallback: try to infer chart type/fields as before
                            query_lower = query.lower()
                            if "pie" in query_lower:
                                chart_type = "pie"
                            elif "bar" in query_lower:
                                chart_type = "bar"
                            else:
                                chart_type = "line"
                            chart_title = query.strip().replace("\n", " ")
                            if chart_type == "pie":
                                possible_label_fields = [k for k in last_tool_output[0].keys() if isinstance(last_tool_output[0][k], str)]
                                possible_value_fields = [k for k in last_tool_output[0].keys() if isinstance(last_tool_output[0][k], (int, float)) and any(row[k] != 0 for row in last_tool_output)]
                                label_field = possible_label_fields[0] if possible_label_fields else list(last_tool_output[0].keys())[0]
                                value_field = possible_value_fields[0] if possible_value_fields else None
                                chart_args = {
                                    "data": last_tool_output,
                                    "label_field": label_field,
                                    "value_field": value_field,
                                    "title": chart_title
                                }
                            elif chart_type == "bar":
                                # Use project name (or first string field) as category, and all value fields as series
                                possible_label_fields = [k for k in last_tool_output[0].keys() if isinstance(last_tool_output[0][k], str)]
                                possible_value_fields = [k for k in last_tool_output[0].keys() if isinstance(last_tool_output[0][k], (int, float)) and any(row[k] != 0 for row in last_tool_output)]
                                label_field = possible_label_fields[0] if possible_label_fields else list(last_tool_output[0].keys())[0]
                                bar_chart_config = build_grouped_bar_chart_config(last_tool_output, label_field, possible_value_fields, chart_title)
                                await create_chart_with_echarts("bar", bar_chart_config)
                            else:
                                # For line charts, always create a multi-line chart with all relevant y_fields
                                x_field = "month" if "month" in last_tool_output[0] else list(last_tool_output[0].keys())[0]
                                candidate_y_fields = [k for k in ["total_capacity", "allocation_hours_planned", "allocation_hours_actual", "available_capacity"] if k in last_tool_output[0]]
                                if not candidate_y_fields:
                                    candidate_y_fields = [k for k in last_tool_output[0].keys() if k != x_field and isinstance(last_tool_output[0][k], (int, float))]
                                chart_args = {
                                    "data": last_tool_output,
                                    "x_field": x_field,
                                    "y_fields": candidate_y_fields,
                                    "title": chart_title
                                }
                                await create_chart_from_data(chart_type, chart_args)
                else:
                    print("⚠️ No tool output, assistant said:")
                    print(assistant_msg.content)
    except Exception as e:
        print(f"❌ Client Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    #query = "Please provide resource hours and cost for resource id 2 for year 2025 in line chart."
    query = "Please show project hours and costs for Market & Sell portfolio in a bar chart."
    asyncio.run(run(query))