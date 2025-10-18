from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv
import json
import base64
import platform

load_dotenv(".env")

server_params_charts = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\CHARTS\\charts_mcp.py"]
)

if __name__ == "__main__":
    import datetime
    async def direct_chart(chart_type, tool_args):
        try:
            print(f"🚀 Starting CHARTS MCP client for {chart_type} chart...")
            async with stdio_client(server_params_charts) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    print("✅ CHARTS MCP session initialized")
                    tool_name = f"generate_{chart_type}_chart"
                    print(f"🔧 Calling tool '{tool_name}' with args: {tool_args}")
                    tool_result = await session.call_tool(tool_name, tool_args)
                    def extract_image_b64(obj):
                        if isinstance(obj, dict):
                            if 'image_base64' in obj:
                                return obj['image_base64']
                            if 'result' in obj and isinstance(obj['result'], dict) and 'image_base64' in obj['result']:
                                return obj['result']['image_base64']
                        if isinstance(obj, str):
                            try:
                                parsed = json.loads(obj)
                                if 'image_base64' in parsed:
                                    return parsed['image_base64']
                                if 'result' in parsed and isinstance(parsed['result'], dict) and 'image_base64' in parsed['result']:
                                    return parsed['image_base64']
                            except Exception:
                                pass
                        return None
                    chart_image_b64 = None
                    result_content = None
                    if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                        result_content = json.dumps(tool_result.structuredContent, indent=2)
                        chart_image_b64 = extract_image_b64(tool_result.structuredContent)
                    elif hasattr(tool_result, 'content') and tool_result.content:
                        if isinstance(tool_result.content, list):
                            result_content = json.dumps([item if not hasattr(item,'text') else item.text for item in tool_result.content], indent=2)
                        else:
                            result_content = str(tool_result.content)
                        chart_image_b64 = extract_image_b64(tool_result.content)
                    else:
                        result_content = str(tool_result)
                        chart_image_b64 = extract_image_b64(tool_result)
                    print(f"Tool result: {result_content}")
                    if chart_image_b64:
                        if chart_image_b64.startswith("data:image/png;base64,"):
                            chart_image_b64 = chart_image_b64.split(",", 1)[1]
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        # Save chart PNG in images directory
                        images_dir = os.path.abspath("images")
                        if not os.path.exists(images_dir):
                            os.makedirs(images_dir)
                        output_filename = f"{chart_type}_chart_{timestamp}.png"
                        output_path = os.path.join(images_dir, output_filename)
                        with open(output_path, "wb") as f:
                            f.write(base64.b64decode(chart_image_b64))
                        print(f"✅ Chart saved as {output_path}. You can open it to view the chart.")
                        # Automatically open the file
                        if platform.system() == "Windows":
                            os.startfile(output_path)
                        elif platform.system() == "Darwin":
                            os.system(f"open '{output_path}'")
                        else:
                            os.system(f"xdg-open '{output_path}'")
                    else:
                        print("⚠️ No image_base64 found in tool result.")
        except Exception as e:
            print(f"❌ Client Error: {e}")
            traceback.print_exc()

    # Bar chart example
    bar_args = {
        "data": [
            {"category": "A", "value": 10},
            {"category": "B", "value": 20},
            {"category": "C", "value": 15}
        ],
        "x_field": "category",
        "y_field": "value"
    }
    asyncio.run(direct_chart("bar", bar_args))

    # Line chart example
    line_args = {
        "data": [
            {"month": "Jan", "sales": 100},
            {"month": "Feb", "sales": 120},
            {"month": "Mar", "sales": 90},
            {"month": "Apr", "sales": 150}
        ],
        "x_field": "month",
        "y_field": "sales"
    }
    asyncio.run(direct_chart("line", line_args))

    # Multi-line chart example
    multiline_args = {
        "data": [
            {"month": "Jan", "sales": 100, "expenses": 80},
            {"month": "Feb", "sales": 120, "expenses": 90},
            {"month": "Mar", "sales": 90, "expenses": 70},
            {"month": "Apr", "sales": 150, "expenses": 110}
        ],
        "x_field": "month",
        "y_fields": ["sales", "expenses"]
    }
    asyncio.run(direct_chart("line", multiline_args))

    # Pie chart example
    pie_args = {
        "data": [
            {"segment": "A", "amount": 40},
            {"segment": "B", "amount": 35},
            {"segment": "C", "amount": 25}
        ],
        "label_field": "segment",
        "value_field": "amount"
    }
    asyncio.run(direct_chart("pie", pie_args))

