from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv
import json
from openai import OpenAI

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

async def run(query: str):
    try:
        print("🚀 Starting PMO MCP client...")
        async with stdio_client(server_params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                print("✅ MCP session initialized")

                # Fetch tools, resources & prompts
                tools_result = await session.list_tools()
                resources_result = await session.list_resources()
                prompts_result = await session.list_prompts()
                resources = resources_result.resources
                prompts = prompts_result.prompts
                print(f"📊 Loaded: {len(tools_result.tools)} tools, {len(resources)} resources, {len(prompts)} prompts")

                system_messages = [{"role": "system", "content": system_context}]

                # Inject MCP resources
                for resource in resources:
                    content = getattr(resource, "content", None) or getattr(resource, "_content", None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({
                            "role": "system", 
                            "content": f"[{resource.name}] {wrap_content(content)}"
                        })

                # Add available fields for get_filtered_projects from docs_filtered_projects.txt
                with open(r"d:/GenAI/MCP/PMO/resources/docs_filtered_projects.txt", "r", encoding="utf-8") as f:
                    filtered_projects_fields = f.read()
                system_messages.append({
                    "role": "system",
                    "content": f"Available fields for get_filtered_projects (costs, hours, and more):\n{filtered_projects_fields}"
                })

                # Inject MCP prompts
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

                # Phase 1: Tool calling
                while tool_calls and iteration < max_iterations:
                    iteration += 1
                    tool_names = [tc.function.name for tc in tool_calls]
                    print(f"🔧 Iteration {iteration}: Calling {', '.join(tool_names)}")
                    for tool_execution in tool_calls:
                        try:
                            tool_name = tool_execution.function.name
                            tool_args = json.loads(tool_execution.function.arguments) if tool_execution.function.arguments else {}
                            print(f"➡️ Calling tool '{tool_name}' with params: {json.dumps(tool_args, indent=2)}")
                            tool_result = await session.call_tool(tool_name, tool_args)
                            if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                result_content = json.dumps(tool_result.structuredContent, indent=2)
                            elif hasattr(tool_result, 'content') and tool_result.content:
                                if isinstance(tool_result.content, list):
                                    result_content = json.dumps([item if not hasattr(item,'text') else item.text for item in tool_result.content], indent=2)
                                else:
                                    result_content = str(tool_result.content)
                            else:
                                result_content = str(tool_result)
                            last_tool_output = result_content
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_execution.id,
                                "name": tool_name,
                                "content": result_content
                            })
                        except Exception as tool_error:
                            print(f"❌ Error in {tool_name}: {tool_error}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_execution.id,
                                "name": tool_name,
                                "content": f"Error: {str(tool_error)}"
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
                    #print(last_tool_output)
                    # Print parsed data if possible
                    try:
                        result_json = json.loads(last_tool_output)
                        #print("[INFO] Tool output (parsed):")
                        #import pprint
                        #pprint.pprint(result_json)
                    except Exception as parse_error:
                        print(f"[WARN] Could not parse tool output as JSON: {parse_error}")
                        print(last_tool_output)
                    # Ask LLM to reason over the JSON
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
                else:
                    print("⚠️ No tool output, assistant said:")
                    print(assistant_msg.content)
    except Exception as e:
        print(f"❌ Client Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    query = "Please provide project hours and costs in Market & Sell portfolio."
    asyncio.run(run(query))