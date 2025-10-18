from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import traceback

server_params = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"] # -y = yes to prompts
)

async def run():
    try:
        print("🚀 Starting stdio_client to MCP server...")
        async with stdio_client(server_params) as (reader, writer): # Instantiate server
            print("✅ Connected to PMO MCP server")
            async with ClientSession(reader, writer) as session: # Instantiate client session
                print("🔧 Initializing MCP session...")
                await session.initialize()
                print("✅ MCP session initialized")

                # Tool listing
                print("Listing tools...")
                tools_result = await session.list_tools()
                print("Available tools:", tools_result)

                # Calling a tool
                tool_name = "get_all_projects"
                result = await session.call_tool(tool_name, {})
                print(f"Tool '{tool_name}' result:", result)

                # Listing resources
                print("Listing resources...")
                resources = await session.list_resources()
                print("Available resources:", resources)

                # Listing resource templates
                print("Listing resource templates...")
                resource_templates = await session.list_resource_templates()
                print("Available resource templates:", resource_templates)

                # Listing prompts
                print("Listing prompts...")
                prompts = await session.list_prompts()
                print("Available prompts:", prompts)

    except Exception as e:
        print("Error during MCP session:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())