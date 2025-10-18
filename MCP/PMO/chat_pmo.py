import asyncio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from types import SimpleNamespace

# 🔑 OpenAI setup
client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

# 🔧 MCP server configuration (unbuffered Python)
pmoserver = SimpleNamespace(
    command="python",
    args=["-u", r"D:\GenAI\MCP\PMO\pmo.py"],  # -u = unbuffered stdout
    env=None,
    cwd=None,
    encoding="utf-8",
    encoding_error_handler="strict",
    name="PMO"
)

async def chat_with_pmo(user_query: str):
    print("🚀 Starting stdio_client to MCP server...")
    try:
        # 1️⃣ Connect to MCP server
        async with stdio_client(pmoserver) as (reader, writer):
            print("✅ Connected to MCP server")
            session = ClientSession(reader, writer)

            print("🔧 Initializing MCP session...")
            await session.initialize()
            print("✅ MCP session initialized")

            # 2️⃣ List available tools
            tools = await session.list_tools()
            tool_names = [t.name for t in tools]
            print("📌 Available tools:", tool_names)

            # 3️⃣ Ask OpenAI GPT how to handle the query
            system_prompt = f"""
            You are an assistant that can call MCP tools.
            Available tools: {tool_names}

            When answering user queries:
            - If a tool is relevant, suggest calling it.
            - If not, answer directly.
            """

            print("💬 Sending user query to OpenAI GPT...")
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ]
            )

            decision = response.choices[0].message.content
            print("🤖 LLM decision:", decision)

            # 4️⃣ Dynamically call a tool if mentioned
            for t in tool_names:
                if t in decision:
                    print(f"🔧 Calling tool '{t}'...")
                    result = await session.call_tool(t, {})
                    print(f"🛠 Tool '{t}' result:", result)

                    print("💬 Sending tool output back to GPT for formatting...")
                    followup = client.chat.completions.create(
                        model="gpt-4.1",
                        messages=[
                            {"role": "system", "content": "Format results into a nice human-readable answer."},
                            {"role": "user", "content": f"Tool output: {result}"}
                        ]
                    )
                    print("✅ Final Answer:", followup.choices[0].message.content)
                    break
            else:
                print("✅ Final Answer:", decision)

    except Exception as e:
        print("⚠️ Exception occurred:", e)

if __name__ == "__main__":
    user_q = input("Ask me something: ")
    print("📝 User query received:", user_q)
    asyncio.run(chat_with_pmo(user_q))