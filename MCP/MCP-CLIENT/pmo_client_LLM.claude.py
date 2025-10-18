from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv

import json
import anthropic

load_dotenv('.env')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')  # Put your Claude API key in .env

server_params = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"]
)

async def run(query: str):
    try:
        print("🚀 Starting stdio_client to MCP server...")
        async with stdio_client(server_params) as (reader, writer):
            print("✅ Connected to PMO MCP server")
            async with ClientSession(reader, writer) as session:
                print("🔧 Initializing MCP session...")
                await session.initialize()
                print("✅ MCP session initialized")

                # Tool listing
                tools_result = await session.list_tools()
                print("Available tools:", tools_result)

                # Anthropic doesn’t support function-calling like OpenAI yet,
                # so we’ll just pass tools info into the prompt.
                tool_descriptions = "\n".join(
                    [f"- {tool.name}: {tool.description}" for tool in tools_result.tools]
                )

                system_prompt = f"""You are connected to a PMO MCP server.
The following tools are available for you to request when needed:
{tool_descriptions}

When the user asks something that needs a tool, respond in JSON:
{{"tool": "<tool_name>", "arguments": {{...}}}}
Otherwise, answer directly.
"""

                claude = anthropic.Anthropic(api_key=anthropic_api_key)

                response = claude.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": query}]
                )

                assistant_text = response.content[0].text
                print("Claude response:", assistant_text)

                # If Claude returned a tool call in JSON, try executing it
                try:
                    parsed = json.loads(assistant_text)
                    if "tool" in parsed:
                        tool_name = parsed["tool"]
                        tool_args = parsed.get("arguments", {})
                        print(f"➡️ Executing tool: {tool_name} with args {tool_args}")
                        tool_result = await session.call_tool(tool_name, tool_args)
                        print("Tool result:", tool_result)
                        return tool_result
                except Exception:
                    # Not JSON → just a normal response
                    return assistant_text

    except Exception as e:
        print("Error during MCP session:")
        traceback.print_exc()

if __name__ == "__main__":
    query = "List all projects in the PMO system."
    asyncio.run(run(query))
