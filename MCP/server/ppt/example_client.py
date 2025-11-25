#!/usr/bin/env python3
"""
Example client for the PowerPoint MCP Server.

This demonstrates how to use the PPT MCP server to create presentations.
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def create_mcp_architecture_presentation():
    """Create a sample MCP architecture presentation."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Starting PowerPoint MCP Server...")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("✓ Connected to PPT MCP Server\n")
            
            # Create presentation
            print("Creating presentation...")
            result = await session.call_tool("create_presentation", {
                "presentation_id": "mcp_architecture"
            })
            print(f"  {result.content[0].text}\n")
            
            # Add title slide
            print("Adding title slide...")
            result = await session.call_tool("add_title_slide", {
                "presentation_id": "mcp_architecture",
                "title": "MCP Integration Architecture",
                "subtitle": "Model Context Protocol - Client-Server Integration Patterns"
            })
            print(f"  {result.content[0].text}\n")
            
            # Add overview slide
            print("Adding overview slide...")
            result = await session.call_tool("add_content_slide", {
                "presentation_id": "mcp_architecture",
                "title": "Architecture Overview",
                "content": [
                    "MCP Client connects to MCP Server",
                    "MCP Server provides Tools, Resources, and Prompts",
                    "Server integrates with external platforms, databases, and internal APIs",
                    "Unified interface for diverse data sources",
                    "Standardized authentication and security"
                ]
            })
            print(f"  {result.content[0].text}\n")
            
            # Add two-column slide
            print("Adding components slide...")
            result = await session.call_tool("add_two_column_slide", {
                "presentation_id": "mcp_architecture",
                "title": "MCP Server Components",
                "left_content": [
                    "Tools:",
                    "• Execute actions and operations",
                    "• Connect to external APIs",
                    "• Perform database queries",
                    "• Transform data",
                    "",
                    "Resources:",
                    "• Provide static/dynamic content",
                    "• Expose configuration",
                    "• Serve documentation"
                ],
                "right_content": [
                    "Prompts:",
                    "• Define query templates",
                    "• Guide AI interactions",
                    "• Standardize patterns",
                    "",
                    "Benefits:",
                    "• Unified interface",
                    "• Centralized security",
                    "• Scalable architecture",
                    "• Easy integration"
                ]
            })
            print(f"  {result.content[0].text}\n")
            
            # Add integration examples slide
            print("Adding integration examples slide...")
            result = await session.call_tool("add_content_slide", {
                "presentation_id": "mcp_architecture",
                "title": "Integration Examples",
                "content": [
                    "External Platforms: JIRA, Confluence, AWS, Salesforce, GitHub, Slack",
                    "Data Sources: PostgreSQL, MongoDB, SQL Server, CSV/Excel, JSON APIs",
                    "Internal APIs: Metadata Service, Auth API, Analytics, Charts, ETL"
                ]
            })
            print(f"  {result.content[0].text}\n")
            
            # Add chart slide
            print("Adding chart slide...")
            result = await session.call_tool("add_chart_slide", {
                "presentation_id": "mcp_architecture",
                "title": "Integration Growth",
                "chart_type": "column",
                "categories": ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"],
                "series_data": [
                    {"name": "External APIs", "values": [5, 10, 15, 20]},
                    {"name": "Databases", "values": [3, 5, 8, 12]},
                    {"name": "Internal APIs", "values": [8, 12, 18, 25]}
                ]
            })
            print(f"  {result.content[0].text}\n")
            
            # Add table slide
            print("Adding comparison table...")
            result = await session.call_tool("add_table_slide", {
                "presentation_id": "mcp_architecture",
                "title": "Integration Comparison",
                "headers": ["Type", "Example", "Protocol", "Authentication"],
                "rows": [
                    ["External Platform", "JIRA", "REST API", "OAuth 2.0"],
                    ["Database", "PostgreSQL", "SQL", "Username/Password"],
                    ["Internal API", "Metadata", "REST API", "API Key"],
                    ["Cloud Service", "AWS S3", "HTTPS", "IAM"]
                ]
            })
            print(f"  {result.content[0].text}\n")
            
            # List presentations
            print("Listing presentations...")
            result = await session.call_tool("list_presentations", {})
            print(f"  {result.content[0].text}\n")
            
            # Save presentation
            print("Saving presentation...")
            result = await session.call_tool("save_presentation", {
                "presentation_id": "mcp_architecture",
                "output_path": "output/mcp_architecture.pptx"
            })
            print(f"  {result.content[0].text}\n")
            
            print("✓ Presentation created successfully!")
            print("  Open 'output/mcp_architecture.pptx' to view the presentation")


async def create_simple_presentation():
    """Create a simple test presentation."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating a simple test presentation...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create presentation
            await session.call_tool("create_presentation", {
                "presentation_id": "test_ppt"
            })
            
            # Add title
            await session.call_tool("add_title_slide", {
                "presentation_id": "test_ppt",
                "title": "Hello from MCP!",
                "subtitle": "PowerPoint generation via Model Context Protocol"
            })
            
            # Add content
            await session.call_tool("add_content_slide", {
                "presentation_id": "test_ppt",
                "title": "Features",
                "content": [
                    "Create presentations programmatically",
                    "Add slides with various layouts",
                    "Include charts and tables",
                    "Save as standard .pptx files"
                ]
            })
            
            # Save
            result = await session.call_tool("save_presentation", {
                "presentation_id": "test_ppt",
                "output_path": "output/test.pptx"
            })
            
            print(f"✓ {result.content[0].text}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "simple":
        asyncio.run(create_simple_presentation())
    else:
        asyncio.run(create_mcp_architecture_presentation())
