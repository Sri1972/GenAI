from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
import json
from dotenv import load_dotenv
from pyecharts.charts import Line
from pyecharts import options as opts
import webbrowser
from pyecharts.render import make_snapshot
from snapshot_selenium import snapshot
import shutil
from datetime import datetime

load_dotenv(".env")

server_params = StdioServerParameters(
    command="node",
    args=[r"D:\\GenAI\\MCP\\CHARTS\\mcp-echarts\\build\\index.js"],
    env={**os.environ, "TRANSPORT_TYPE": "stdio"}
)

async def run_chart():
    try:
        print("🚀 Starting ECharts MCP client (local)...")
        async with stdio_client(server_params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                print("✅ MCP session initialized")

                # Example: generate a line chart
                tool_name = "generate_line_chart"
                tool_args = {
                    "axisXTitle": "Year",
                    "axisYTitle": "Value",
                    "title": "Sales and Profits Over Time",
                    "data": [
                        {"group": "Sales", "time": "2015", "value": 23},
                        {"group": "Sales", "time": "2016", "value": 32},
                        {"group": "Profits", "time": "2015", "value": 18},
                        {"group": "Profits", "time": "2016", "value": 27}
                    ],
                    "height": 600,
                    "width": 800,
                    "showArea": False,
                    "showSymbol": True,
                    "smooth": True,
                    "stack": False,
                    "theme": "default",
                    "outputType": "option"
                }

                # Call the tool
                result = await session.call_tool(tool_name, tool_args)
                
                # Extract JSON option
                if hasattr(result, "content"):
                    chart_option_json = result.content
                    if isinstance(chart_option_json, list):
                        chart_option_json = chart_option_json[0].text

                    # Generate unique filename
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    images_dir = os.path.join(os.path.dirname(__file__), "images")
                    os.makedirs(images_dir, exist_ok=True)
                    chart_type = "line_chart"
                    json_file = os.path.join(images_dir, f"{chart_type}_{timestamp}.json")
                    html_file = os.path.join(images_dir, f"{chart_type}_{timestamp}.html")
                    png_file = os.path.join(images_dir, f"{chart_type}_{timestamp}.png")

                    # Save to unique temp JSON file
                    with open(json_file, "w", encoding="utf-8") as f:
                        f.write(chart_option_json)

                    print(f"✅ Chart JSON saved to {json_file}")

                    # Load chart config from MCP
                    with open(json_file, "r", encoding="utf-8") as f:
                        config = json.load(f)

                    x_data = config["xAxis"]["data"]
                    series = config["series"]

                    line = Line()
                    line.add_xaxis(x_data)

                    for s in series:
                        line.add_yaxis(
                            s["name"],
                            s["data"],
                            is_smooth=s.get("smooth", False),
                            is_symbol_show=s.get("showSymbol", True),
                            label_opts=opts.LabelOpts(is_show=False)
                        )

                    line.set_global_opts(
                        title_opts=opts.TitleOpts(title=config["title"]["text"]),
                        tooltip_opts=opts.TooltipOpts(trigger=config["tooltip"]["trigger"]),
                        legend_opts=opts.LegendOpts(
                            orient=config["legend"]["orient"],
                            pos_left=config["legend"]["left"],
                            pos_bottom=config["legend"]["bottom"]
                        ),
                        xaxis_opts=opts.AxisOpts(
                            name=config["xAxis"]["name"],
                            type_=config["xAxis"]["type"],
                            boundary_gap=config["xAxis"]["boundaryGap"]
                        ),
                        yaxis_opts=opts.AxisOpts(
                            name=config["yAxis"]["name"],
                            type_=config["yAxis"]["type"]
                        )
                    )

                    # Save chart as unique HTML (required for PNG rendering)
                    line.render(html_file)

                    # Save as PNG (requires snapshot-selenium and Chrome/Chromium)
                    make_snapshot(snapshot, html_file, png_file)
                    print(f"✅ Chart PNG created: {png_file}")

                    # Display the PNG directly using Pillow
                    from PIL import Image
                    img = Image.open(png_file)
                    img.show()

                    # Delete temp files
                    for temp_file in [html_file, json_file]:
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass

    except Exception as e:
        print(f"❌ Client Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_chart())
