import asyncio
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from mcp.client.sse import sse_client
from mcp import ClientSession

# Load OpenAI API key from .env
load_dotenv(".env")
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)

D3_MCP_SERVER_URL = "http://localhost:3000/sse"

async def run_chart(chart_type, data, features=None, chart_type_hint=None):
    features = features or []
    # Use ai-generate-d3 for non-bar/line chart types
    use_ai = chart_type not in ("bar", "line")
    if use_ai:
        # Use OpenAI LLM directly to generate D3 code
        prompt = f"Generate a complete D3.js v7 {chart_type} chart with the following data (as JSON):\n{json.dumps(data, indent=2)}\nFeatures: {', '.join(features)}. Output a complete HTML file with embedded JS and CSS."
        print(f"\n=== {chart_type.upper()} CHART TEST (OpenAI LLM) ===")
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a D3.js expert. Generate beautiful, robust, and safe D3.js v7 code for the user's request. Always output a complete HTML file."},
                {"role": "user", "content": prompt}
            ]
        )
        chart_code = response.choices[0].message.content
        print("\n[Generated D3 Chart Code/Markup]:\n")
        print(chart_code[:500] + ("..." if len(chart_code) > 500 else ""))
        if chart_code:
            output_path = f"output_{chart_type}_chart.html"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(chart_code)
            print(f"\n✅ Chart HTML saved to: {output_path}")
        else:
            print("❌ No chart code generated.")
    else:
        chart_args = {
            "chartType": chart_type,
            "dataFormat": "Array of objects with sample fields",
            "features": features
        }
        print(f"\n=== {chart_type.upper()} CHART TEST (D3 MCP Server) ===")
        async with sse_client(D3_MCP_SERVER_URL) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.call_tool("generate-d3-chart", chart_args)
                chart_code = None
                if hasattr(result, "content") and isinstance(result.content, list):
                    for item in result.content:
                        if getattr(item, "type", None) == "text" and hasattr(item, "text"):
                            chart_code = item.text
                            print("\n[Generated D3 Chart Code/Markup]:\n")
                            print(chart_code[:500] + ("..." if len(chart_code) > 500 else ""))
                if chart_code:
                    output_path = f"output_{chart_type}_chart.html"
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(chart_code)
                    print(f"\n✅ Chart HTML saved to: {output_path}")
                else:
                    print("❌ No chart code generated.")

async def main():
    # Multi-line chart sample data
    multiline_data = [
        {"month": "2025-01", "planned": 10, "actual": 8},
        {"month": "2025-02", "planned": 12, "actual": 11},
        {"month": "2025-03", "planned": 15, "actual": 13},
        {"month": "2025-04", "planned": 14, "actual": 14},
        {"month": "2025-05", "planned": 16, "actual": 15}
    ]
    # Bar chart sample data
    bar_data = [
        {"category": "A", "value": 30},
        {"category": "B", "value": 45},
        {"category": "C", "value": 22},
        {"category": "D", "value": 17}
    ]
    # Pie chart sample data
    pie_data = [
        {"label": "Red", "value": 40},
        {"label": "Blue", "value": 25},
        {"label": "Green", "value": 35}
    ]
    # Test multi-line chart (OpenAI LLM)
    await run_chart("multi-line", multiline_data, features=["legend", "tooltip"], chart_type_hint="multi-line")
    # Test bar chart (D3 MCP Server)
    await run_chart("bar", bar_data, features=["tooltip"], chart_type_hint="bar")
    # Test pie chart (OpenAI LLM)
    await run_chart("pie", pie_data, features=["legend"], chart_type_hint="pie")

if __name__ == "__main__":
    asyncio.run(main())
