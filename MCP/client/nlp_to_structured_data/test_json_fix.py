#!/usr/bin/env python3
"""
Test script to verify JSON metadata loading fix
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_json_loading():
    server_params = StdioServerParameters(
        command="python", 
        args=["D:/SourceCode/GenAI/MCP/server/nlp_to_structured_data/nlp_to_structured_data_mcp_server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # Test JSON loading
            print("Testing JSON file loading...")
            
            result = await session.call_tool(
                "load_data_file",
                {
                    "file_path": "restaurant_project/restaurant_data",
                    "file_type": "json",
                    "metadata_path": ""
                }
            )
            
            print("=== JSON LOADING RESULT ===")
            print(json.dumps(result.content, indent=2))

if __name__ == "__main__":
    asyncio.run(test_json_loading())