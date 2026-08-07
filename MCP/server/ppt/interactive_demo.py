#!/usr/bin/env python3
"""
Interactive PPT MCP Client

Demonstrates various ways to create presentation content including:
- Bulleted lists
- Numbered lists
- Charts (bar, column, line, pie)
- Tables
- Two-column layouts
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def example_bulleted_content():
    """Example: Create slides with bulleted content."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating presentation with bulleted content...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create presentation
            await session.call_tool("create_presentation", {
                "presentation_id": "bulleted_example"
            })
            
            # Title slide
            await session.call_tool("add_title_slide", {
                "presentation_id": "bulleted_example",
                "title": "Project Status Update",
                "subtitle": "Q4 2025 Review"
            })
            
            # Slide with bulleted content
            await session.call_tool("add_content_slide", {
                "presentation_id": "bulleted_example",
                "title": "Key Achievements",
                "content": [
                    "Completed migration to cloud infrastructure",
                    "Launched new customer portal",
                    "Improved system performance by 40%",
                    "Reduced operational costs by 25%",
                    "Onboarded 50+ new enterprise clients"
                ]
            })
            
            # Multi-level content (use spacing/indentation in text)
            await session.call_tool("add_content_slide", {
                "presentation_id": "bulleted_example",
                "title": "Technical Architecture",
                "content": [
                    "Frontend Layer",
                    "  - React 18 with TypeScript",
                    "  - Material UI components",
                    "Backend Services",
                    "  - Node.js REST APIs",
                    "  - Python microservices",
                    "Database Layer",
                    "  - PostgreSQL for transactional data",
                    "  - Redis for caching"
                ]
            })
            
            # Save
            result = await session.call_tool("save_presentation", {
                "presentation_id": "bulleted_example",
                "output_path": "output/bulleted_example.pptx"
            })
            print(f"✓ {result.content[0].text}\n")


async def example_charts():
    """Example: Create slides with different chart types."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating presentation with charts...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "chart_example"
            })
            
            await session.call_tool("add_title_slide", {
                "presentation_id": "chart_example",
                "title": "Sales Performance Analysis",
                "subtitle": "2025 Annual Review"
            })
            
            # Column chart
            await session.call_tool("add_chart_slide", {
                "presentation_id": "chart_example",
                "title": "Quarterly Revenue",
                "chart_type": "column",
                "categories": ["Q1", "Q2", "Q3", "Q4"],
                "series_data": [
                    {"name": "2024", "values": [45, 52, 48, 60]},
                    {"name": "2025", "values": [50, 58, 65, 72]}
                ]
            })
            
            # Line chart
            await session.call_tool("add_chart_slide", {
                "presentation_id": "chart_example",
                "title": "Customer Growth Trend",
                "chart_type": "line",
                "categories": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "series_data": [
                    {"name": "New Customers", "values": [120, 145, 160, 175, 200, 225]},
                    {"name": "Active Users", "values": [1000, 1150, 1300, 1480, 1700, 1950]}
                ]
            })
            
            # Pie chart
            await session.call_tool("add_chart_slide", {
                "presentation_id": "chart_example",
                "title": "Revenue by Product Category",
                "chart_type": "pie",
                "categories": ["Enterprise", "Professional", "Starter", "Free"],
                "series_data": [
                    {"name": "Revenue", "values": [45, 30, 20, 5]}
                ]
            })
            
            # Bar chart
            await session.call_tool("add_chart_slide", {
                "presentation_id": "chart_example",
                "title": "Team Productivity Metrics",
                "chart_type": "bar",
                "categories": ["Engineering", "Sales", "Marketing", "Support"],
                "series_data": [
                    {"name": "Completed Tasks", "values": [85, 72, 68, 90]}
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "chart_example",
                "output_path": "output/chart_example.pptx"
            })
            print(f"✓ {result.content[0].text}\n")


async def example_tables():
    """Example: Create slides with tables."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating presentation with tables...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "table_example"
            })
            
            await session.call_tool("add_title_slide", {
                "presentation_id": "table_example",
                "title": "Project Resource Allocation",
                "subtitle": "Team Assignment Overview"
            })
            
            # Employee table
            await session.call_tool("add_table_slide", {
                "presentation_id": "table_example",
                "title": "Team Assignments",
                "headers": ["Name", "Role", "Project", "Allocation %"],
                "rows": [
                    ["Alice Johnson", "Lead Developer", "Cloud Migration", "100%"],
                    ["Bob Smith", "DevOps Engineer", "CI/CD Pipeline", "80%"],
                    ["Carol Davis", "QA Engineer", "Testing Suite", "100%"],
                    ["David Lee", "Product Manager", "Feature Planning", "50%"],
                    ["Emma Wilson", "UX Designer", "UI Redesign", "75%"]
                ]
            })
            
            # Budget table
            await session.call_tool("add_table_slide", {
                "presentation_id": "table_example",
                "title": "Q4 Budget Breakdown",
                "headers": ["Category", "Budget", "Spent", "Remaining"],
                "rows": [
                    ["Engineering", "$500K", "$420K", "$80K"],
                    ["Marketing", "$300K", "$285K", "$15K"],
                    ["Operations", "$200K", "$180K", "$20K"],
                    ["Infrastructure", "$150K", "$145K", "$5K"]
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "table_example",
                "output_path": "output/table_example.pptx"
            })
            print(f"✓ {result.content[0].text}\n")


async def example_two_column_layout():
    """Example: Create slides with two-column layouts."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating presentation with two-column layouts...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "two_column_example"
            })
            
            await session.call_tool("add_title_slide", {
                "presentation_id": "two_column_example",
                "title": "Product Comparison",
                "subtitle": "Feature Analysis"
            })
            
            # Comparison slide
            await session.call_tool("add_two_column_slide", {
                "presentation_id": "two_column_example",
                "title": "Current vs. Proposed Solution",
                "left_content": [
                    "CURRENT SYSTEM:",
                    "• On-premise infrastructure",
                    "• Manual deployment process",
                    "• Limited scalability",
                    "• High maintenance costs",
                    "• Outdated technology stack"
                ],
                "right_content": [
                    "PROPOSED SOLUTION:",
                    "• Cloud-based infrastructure",
                    "• Automated CI/CD pipeline",
                    "• Auto-scaling capabilities",
                    "• Reduced operational costs",
                    "• Modern tech stack"
                ]
            })
            
            # Pros and Cons
            await session.call_tool("add_two_column_slide", {
                "presentation_id": "two_column_example",
                "title": "Migration Analysis",
                "left_content": [
                    "BENEFITS:",
                    "✓ Improved performance",
                    "✓ Better reliability",
                    "✓ Enhanced security",
                    "✓ Cost savings over time",
                    "✓ Easier maintenance"
                ],
                "right_content": [
                    "CHALLENGES:",
                    "• Initial migration effort",
                    "• Team training required",
                    "• Temporary downtime",
                    "• Data migration complexity",
                    "• Change management"
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "two_column_example",
                "output_path": "output/two_column_example.pptx"
            })
            print(f"✓ {result.content[0].text}\n")


async def example_complete_presentation():
    """Example: Complete presentation with mixed content types."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating complete presentation with mixed content...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "complete_example"
            })
            
            # Slide 1: Title
            print("Adding title slide...")
            await session.call_tool("add_title_slide", {
                "presentation_id": "complete_example",
                "title": "Q4 Business Review",
                "subtitle": "Executive Summary - December 2025"
            })
            
            # Slide 2: Bullet points
            print("Adding overview slide...")
            await session.call_tool("add_content_slide", {
                "presentation_id": "complete_example",
                "title": "Agenda",
                "content": [
                    "Financial Performance",
                    "Customer Metrics",
                    "Product Updates",
                    "Team Achievements",
                    "2026 Strategy"
                ]
            })
            
            # Slide 3: Chart
            print("Adding revenue chart...")
            await session.call_tool("add_chart_slide", {
                "presentation_id": "complete_example",
                "title": "Revenue Growth",
                "chart_type": "column",
                "categories": ["Q1", "Q2", "Q3", "Q4"],
                "series_data": [
                    {"name": "Revenue ($M)", "values": [2.5, 3.2, 3.8, 4.5]}
                ]
            })
            
            # Slide 4: Two columns
            print("Adding comparison slide...")
            await session.call_tool("add_two_column_slide", {
                "presentation_id": "complete_example",
                "title": "Achievements & Challenges",
                "left_content": [
                    "ACHIEVEMENTS:",
                    "• Exceeded revenue targets by 20%",
                    "• Launched 3 major features",
                    "• Expanded to 5 new markets",
                    "• Improved customer retention"
                ],
                "right_content": [
                    "CHALLENGES:",
                    "• Increased competition",
                    "• Supply chain delays",
                    "• Talent acquisition",
                    "• Technical debt"
                ]
            })
            
            # Slide 5: Table
            print("Adding metrics table...")
            await session.call_tool("add_table_slide", {
                "presentation_id": "complete_example",
                "title": "Key Performance Indicators",
                "headers": ["Metric", "Target", "Actual", "Status"],
                "rows": [
                    ["Revenue", "$15M", "$18M", "✓ Exceeded"],
                    ["Customers", "500", "625", "✓ Exceeded"],
                    ["Churn Rate", "<5%", "3.2%", "✓ Met"],
                    ["NPS Score", ">70", "78", "✓ Exceeded"]
                ]
            })
            
            # Slide 6: Next steps
            print("Adding next steps slide...")
            await session.call_tool("add_content_slide", {
                "presentation_id": "complete_example",
                "title": "2026 Priorities",
                "content": [
                    "1. Expand enterprise sales team",
                    "2. Launch AI-powered features",
                    "3. Enter European market",
                    "4. Strengthen security infrastructure",
                    "5. Build strategic partnerships"
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "complete_example",
                "output_path": "output/complete_example.pptx"
            })
            print(f"\n✓ {result.content[0].text}")
            print("Open the file to view your presentation!\n")


async def interactive_mode():
    """Interactive mode to build presentations step by step."""
    print("=== PPT MCP Interactive Demo ===\n")
    print("Choose an example to run:")
    print("1. Bulleted content")
    print("2. Charts (column, line, pie, bar)")
    print("3. Tables")
    print("4. Two-column layouts")
    print("5. Complete presentation (all types)")
    print("6. Run all examples\n")
    
    choice = input("Enter choice (1-6): ").strip()
    
    if choice == "1":
        await example_bulleted_content()
    elif choice == "2":
        await example_charts()
    elif choice == "3":
        await example_tables()
    elif choice == "4":
        await example_two_column_layout()
    elif choice == "5":
        await example_complete_presentation()
    elif choice == "6":
        print("\nRunning all examples...\n")
        await example_bulleted_content()
        await example_charts()
        await example_tables()
        await example_two_column_layout()
        await example_complete_presentation()
        print("✓ All examples completed!")
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    asyncio.run(interactive_mode())
