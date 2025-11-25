#!/usr/bin/env python3
"""
Demo: Advanced Visualizations - Gantt Charts and Diagrams

Shows how to create Gantt charts and include external diagrams/flowcharts.
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def example_gantt_chart():
    """Example: Create a Gantt chart for project timeline."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("Creating Gantt chart presentation...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "gantt_example"
            })
            
            await session.call_tool("add_title_slide", {
                "presentation_id": "gantt_example",
                "title": "Project Timeline",
                "subtitle": "Q1 2026 Development Roadmap"
            })
            
            # Gantt chart slide
            print("Adding Gantt chart...")
            await session.call_tool("add_gantt_chart_slide", {
                "presentation_id": "gantt_example",
                "title": "Development Schedule",
                "tasks": [
                    {
                        "name": "Requirements Analysis",
                        "start": "Jan 1",
                        "end": "Jan 15",
                        "duration": "2 weeks",
                        "status": "Complete"
                    },
                    {
                        "name": "System Design",
                        "start": "Jan 16",
                        "end": "Feb 5",
                        "duration": "3 weeks",
                        "status": "Complete"
                    },
                    {
                        "name": "Backend Development",
                        "start": "Feb 6",
                        "end": "Mar 15",
                        "duration": "6 weeks",
                        "status": "In Progress"
                    },
                    {
                        "name": "Frontend Development",
                        "start": "Feb 20",
                        "end": "Mar 30",
                        "duration": "6 weeks",
                        "status": "In Progress"
                    },
                    {
                        "name": "Integration Testing",
                        "start": "Mar 15",
                        "end": "Apr 5",
                        "duration": "3 weeks",
                        "status": "Not Started"
                    },
                    {
                        "name": "UAT & Bug Fixes",
                        "start": "Apr 6",
                        "end": "Apr 20",
                        "duration": "2 weeks",
                        "status": "Not Started"
                    },
                    {
                        "name": "Production Deployment",
                        "start": "Apr 21",
                        "end": "Apr 25",
                        "duration": "1 week",
                        "status": "Not Started"
                    }
                ]
            })
            
            # Milestones slide
            await session.call_tool("add_content_slide", {
                "presentation_id": "gantt_example",
                "title": "Key Milestones",
                "content": [
                    "✓ Requirements Signed Off - Jan 15",
                    "✓ Design Review Complete - Feb 5",
                    "→ Backend API Ready - Mar 15 (In Progress)",
                    "→ Frontend Integration - Mar 30 (In Progress)",
                    "○ QA Approval - Apr 5 (Pending)",
                    "○ Go-Live Date - Apr 25 (Pending)"
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "gantt_example",
                "output_path": "output/gantt_example.pptx"
            })
            print(f"\n✓ {result.content[0].text}")


async def example_dataflow_with_description():
    """Example: Data flow slide using text-based description."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    print("\nCreating data flow presentation (text-based)...\n")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("create_presentation", {
                "presentation_id": "dataflow_example"
            })
            
            await session.call_tool("add_title_slide", {
                "presentation_id": "dataflow_example",
                "title": "System Architecture",
                "subtitle": "Data Flow & Integration Points"
            })
            
            # Data flow using two columns
            await session.call_tool("add_two_column_slide", {
                "presentation_id": "dataflow_example",
                "title": "Data Flow Overview",
                "left_content": [
                    "INPUT SOURCES:",
                    "📱 Mobile App",
                    "  → REST API calls",
                    "  → User authentication",
                    "",
                    "🌐 Web Portal",
                    "  → GraphQL queries",
                    "  → Real-time updates",
                    "",
                    "🔌 Third-Party APIs",
                    "  → Data synchronization",
                    "  → Webhook events"
                ],
                "right_content": [
                    "PROCESSING LAYER:",
                    "⚙️ API Gateway",
                    "  → Load balancing",
                    "  → Authentication",
                    "",
                    "🔄 Message Queue",
                    "  → Async processing",
                    "  → Event streaming",
                    "",
                    "💾 Database Layer",
                    "  → Data persistence",
                    "  → Caching"
                ]
            })
            
            # Architecture components
            await session.call_tool("add_content_slide", {
                "presentation_id": "dataflow_example",
                "title": "System Components",
                "content": [
                    "1. Client Layer",
                    "   • Mobile apps (iOS/Android)",
                    "   • Web application (React)",
                    "",
                    "2. API Layer",
                    "   • REST API (Node.js)",
                    "   • GraphQL API (Apollo Server)",
                    "",
                    "3. Processing Layer",
                    "   • Message Queue (RabbitMQ)",
                    "   • Background Workers (Python)",
                    "",
                    "4. Data Layer",
                    "   • PostgreSQL (Primary DB)",
                    "   • Redis (Cache)",
                    "   • S3 (File Storage)"
                ]
            })
            
            # Integration table
            await session.call_tool("add_table_slide", {
                "presentation_id": "dataflow_example",
                "title": "Integration Points",
                "headers": ["Source", "Protocol", "Data Type", "Frequency"],
                "rows": [
                    ["Mobile App", "REST/HTTPS", "JSON", "Real-time"],
                    ["Web Portal", "GraphQL/WSS", "JSON", "Real-time"],
                    ["Payment Gateway", "REST/HTTPS", "JSON", "On-demand"],
                    ["Analytics Service", "Webhook", "JSON", "Batch (hourly)"],
                    ["CRM System", "REST/HTTPS", "XML", "Scheduled (daily)"]
                ]
            })
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "dataflow_example",
                "output_path": "output/dataflow_example.pptx"
            })
            print(f"✓ {result.content[0].text}")


async def main():
    """Run all advanced visualization examples."""
    print("=== Advanced Visualizations Demo ===\n")
    
    await example_gantt_chart()
    await example_dataflow_with_description()
    
    print("\n" + "="*50)
    print("✓ All presentations created!")
    print("\nNOTE: For complex diagrams with icons and shapes,")
    print("you can also create them externally (e.g., in Draw.io,")
    print("Lucidchart, or PowerPoint itself) and use the")
    print("'add_image_slide' tool to insert them.")
    print("\nExample:")
    print("  await session.call_tool('add_image_slide', {")
    print("      'presentation_id': 'my_ppt',")
    print("      'title': 'System Architecture',")
    print("      'image_path': 'diagrams/architecture.png',")
    print("      'width': 8")
    print("  })")


if __name__ == "__main__":
    asyncio.run(main())
