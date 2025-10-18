import asyncio
import traceback
import os
from dotenv import load_dotenv
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# You need to install the Google Gemini SDK: pip install google-generativeai
import google.generativeai as genai

load_dotenv(".env")
gemini_api_key = os.getenv("GEMINI_API_KEY")

server_params_pmo = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\GenAI\MCP\PMO\pmo.py"]
)
server_params_charts = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\GenAI\MCP\CHARTS\charts_mcp.py"]
)

def wrap_content(content: str):
    return content

async def run(query: str):
    try:
        print("🚀 Starting MCP clients...")
        async with stdio_client(server_params_pmo) as (reader_pmo, writer_pmo), \
                   stdio_client(server_params_charts) as (reader_charts, writer_charts):
            async with ClientSession(reader_pmo, writer_pmo) as session_pmo, \
                       ClientSession(reader_charts, writer_charts) as session_charts:
                await session_pmo.initialize()
                await session_charts.initialize()
                print("✅ MCP sessions initialized")

                # Fetch tools, resources & prompts from both MCPs
                tools_result_pmo = await session_pmo.list_tools()
                resources_result_pmo = await session_pmo.list_resources()
                prompts_result_pmo = await session_pmo.list_prompts()

                tools_result_charts = await session_charts.list_tools()
                resources_result_charts = await session_charts.list_resources()
                prompts_result_charts = await session_charts.list_prompts()

                resources = resources_result_pmo.resources + resources_result_charts.resources
                prompts = prompts_result_pmo.prompts + prompts_result_charts.prompts
                all_tools = tools_result_pmo.tools + tools_result_charts.tools

                print(f"📊 Loaded: {len(all_tools)} tools, {len(resources)} resources, {len(prompts)} prompts")

                system_context = """
                You are a PMO and Charting assistant.
                Guidelines:
                - Always call a tool instead of guessing answers.
                - When a tool returns data, output ONLY the raw JSON from that tool.
                - Use PMO tools for project/resource/business queries.
                - Use CHARTS tools for chart generation (line, bar, pie) from JSON data.
                - If a chart is requested, use the appropriate chart tool and provide the chart as a base64 PNG.
                - Always use the raw JSON from the tool outputs.
                """

                # Only inject resources and prompts relevant to the query to reduce token usage
                relevant_resources = []
                relevant_prompts = []
                query_lower = query.lower()
                for resource in resources:
                    name = getattr(resource, "name", "").lower()
                    if name and (name in query_lower or any(word in query_lower for word in name.split('_'))):
                        content = getattr(resource, "content", None) or getattr(resource, "_content", None)
                        if isinstance(content, str) and content.strip():
                            relevant_resources.append({
                                "role": "system",
                                "content": f"[{resource.name}] {wrap_content(content)}"
                            })
                for prompt in prompts:
                    name = getattr(prompt, "name", "").lower()
                    if name and (name in query_lower or any(word in query_lower for word in name.split('_'))):
                        content = getattr(prompt, "content", None) or getattr(prompt, "_content", None)
                        if isinstance(content, str) and content.strip():
                            relevant_prompts.append({
                                "role": "system",
                                "content": f"[{prompt.name}] {wrap_content(content)}"
                            })

                system_messages = [{"role": "system", "content": system_context}] + relevant_resources + relevant_prompts

                # Gemini does not support function calling, so we pass tool info in the prompt
                tool_descriptions = "\n".join(
                    [f"- {tool.name}: {tool.description}" for tool in all_tools]
                )

                gemini_prompt = f"""You are connected to PMO and CHARTS MCP servers.
The following tools are available for you to request when needed:
{tool_descriptions}

When the user asks something that needs a tool, respond in JSON:
{{"tool": "<tool_name>", "arguments": {{...}}}}
Otherwise, answer directly.
"""

                # Compose the full prompt for Gemini
                full_prompt = gemini_prompt + "\n" + "\n".join([msg["content"] for msg in system_messages]) + f"\nUser query: {query}"

                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")
                response = model.generate_content(full_prompt)
                assistant_text = response.text
                print("Gemini response:", assistant_text)

                # If Gemini returned a tool call in JSON, try executing it
                try:
                    parsed = json.loads(assistant_text)
                    if "tool" in parsed:
                        tool_name = parsed["tool"]
                        tool_args = parsed.get("arguments", {})
                        print(f"➡️ Executing tool: {tool_name} with args {tool_args}")
                        if tool_name in [tool.name for tool in tools_result_pmo.tools]:
                            tool_result = await session_pmo.call_tool(tool_name, tool_args)
                        elif tool_name in [tool.name for tool in tools_result_charts.tools]:
                            tool_result = await session_charts.call_tool(tool_name, tool_args)
                        else:
                            tool_result = f"Tool {tool_name} not found in either MCP server."
                        print("Tool result:", tool_result)
                        return tool_result
                except Exception:
                    # Not JSON → just a normal response
                    return assistant_text

    except Exception as e:
        print(f"❌ Client Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    query = "Please provide resource capacity and allocation for resource id 2 in a line chart. " \
             "The start date is 2025-01-01 and end date is 2025-12-31. The interval is weekly. " \
             "Show all the data and the line chart as well using the charts MCP"
    asyncio.run(run(query))
