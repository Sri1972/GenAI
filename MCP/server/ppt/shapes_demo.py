"""
Demo script for PowerPoint MCP Server - Shapes and SmartArt Graphics

This script demonstrates:
1. Process flow with chevron shapes (horizontal and vertical)
2. Timeline with circular markers and events
3. Cycle diagrams (circular process)
4. Pyramid diagrams (hierarchical structure)
5. Matrix diagrams (2x2 grid)
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def example_process_flows():
    """Example 1: Process flows with chevron/arrow shapes"""
    print("\n=== Example 1: Process Flows ===")
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create presentation
            await session.call_tool("create_presentation", {
                "presentation_id": "shapes_demo",
            })
            
            # Add title slide
            await session.call_tool("add_title_slide", {
                "presentation_id": "shapes_demo",
                "title": "PowerPoint Shapes Demo",
                "subtitle": "Process Flows, Timelines, and Diagrams"
            })
            
            # Horizontal process flow
            await session.call_tool("add_process_flow_slide", {
                "presentation_id": "shapes_demo",
                "title": "Horizontal Process Flow",
                "steps": [
                    "Requirements Gathering",
                    "Design & Planning",
                    "Development",
                    "Testing",
                    "Deployment"
                ],
                "flow_type": "horizontal"
            })
            
            # Vertical process flow
            await session.call_tool("add_process_flow_slide", {
                "presentation_id": "shapes_demo",
                "title": "Vertical Process Flow",
                "steps": [
                    "Customer Request",
                    "Approval Process",
                    "Implementation",
                    "Quality Check",
                    "Delivery"
                ],
                "flow_type": "vertical"
            })
            
            print("✓ Process flow slides created with chevron shapes")


async def example_timeline():
    """Example 2: Timeline with events"""
    print("\n=== Example 2: Timeline ===")
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            await session.call_tool("add_timeline_slide", {
                "presentation_id": "shapes_demo",
                "title": "Project Timeline",
                "events": [
                    {"date": "Q1 2024", "description": "Project Kickoff & Team Formation"},
                    {"date": "Q2 2024", "description": "Requirements & Design"},
                    {"date": "Q3 2024", "description": "Development Phase"},
                    {"date": "Q4 2024", "description": "Testing & Quality Assurance"},
                    {"date": "Q1 2025", "description": "Launch & Deployment"}
                ]
            })
            
            print("✓ Timeline slide created with circular markers")


async def example_diagrams():
    """Example 3: Various diagram types"""
    print("\n=== Example 3: Diagrams ===")
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Cycle diagram
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "shapes_demo",
                "title": "Continuous Improvement Cycle",
                "diagram_type": "cycle",
                "items": [
                    "Plan",
                    "Do",
                    "Check",
                    "Act"
                ]
            })
            
            # Pyramid diagram
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "shapes_demo",
                "title": "Organizational Hierarchy",
                "diagram_type": "pyramid",
                "items": [
                    "Executive Leadership",
                    "Senior Management",
                    "Middle Management",
                    "Team Leads",
                    "Individual Contributors"
                ]
            })
            
            # Matrix diagram (SWOT Analysis)
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "shapes_demo",
                "title": "SWOT Analysis",
                "diagram_type": "matrix",
                "items": [
                    "Strengths:\n• Strong brand\n• Loyal customers\n• Innovative products",
                    "Weaknesses:\n• Limited resources\n• Small market share\n• High costs",
                    "Opportunities:\n• Market expansion\n• New technologies\n• Strategic partnerships",
                    "Threats:\n• Competition\n• Economic downturn\n• Regulatory changes"
                ]
            })
            
            print("✓ Diagram slides created (cycle, pyramid, matrix)")


async def example_complete_shapes_presentation():
    """Example 4: Complete presentation with all shape types"""
    print("\n=== Example 4: Complete Shapes Presentation ===")
    
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create presentation
            await session.call_tool("create_presentation", {
                "presentation_id": "complete_shapes",
            })
            
            # Title slide
            await session.call_tool("add_title_slide", {
                "presentation_id": "complete_shapes",
                "title": "Strategic Planning Review",
                "subtitle": "Q4 2024 Update"
            })
            
            # Executive summary with bullets
            await session.call_tool("add_content_slide", {
                "presentation_id": "complete_shapes",
                "title": "Executive Summary",
                "content": [
                    "Successfully completed all major initiatives",
                    "Exceeded revenue targets by 15%",
                    "Launched 3 new product features",
                    "Expanded team by 20 members",
                    "Improved customer satisfaction to 92%"
                ]
            })
            
            # Process flow
            await session.call_tool("add_process_flow_slide", {
                "presentation_id": "complete_shapes",
                "title": "Product Development Process",
                "steps": [
                    "Ideation",
                    "Validation",
                    "Development",
                    "Launch",
                    "Iterate"
                ],
                "flow_type": "horizontal"
            })
            
            # Timeline
            await session.call_tool("add_timeline_slide", {
                "presentation_id": "complete_shapes",
                "title": "2025 Roadmap",
                "events": [
                    {"date": "Jan", "description": "Feature A Launch"},
                    {"date": "Mar", "description": "Market Expansion"},
                    {"date": "Jun", "description": "Platform V2.0"},
                    {"date": "Sep", "description": "Mobile App Release"},
                    {"date": "Dec", "description": "Year-End Review"}
                ]
            })
            
            # Cycle diagram
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "complete_shapes",
                "title": "Customer Success Framework",
                "diagram_type": "cycle",
                "items": [
                    "Onboard",
                    "Engage",
                    "Support",
                    "Retain",
                    "Expand"
                ]
            })
            
            # Matrix (2x2)
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "complete_shapes",
                "title": "Priority Matrix",
                "diagram_type": "matrix",
                "items": [
                    "High Impact\nHigh Effort\n• Major features\n• Platform rebuild",
                    "High Impact\nLow Effort\n• Quick wins\n• Bug fixes",
                    "Low Impact\nHigh Effort\n• Nice-to-haves\n• Future considerations",
                    "Low Impact\nLow Effort\n• Minor improvements\n• Cosmetic changes"
                ]
            })
            
            # Pyramid
            await session.call_tool("add_diagram_slide", {
                "presentation_id": "complete_shapes",
                "title": "Feature Adoption",
                "diagram_type": "pyramid",
                "items": [
                    "Power Users (5%)",
                    "Active Users (20%)",
                    "Regular Users (35%)",
                    "Occasional Users (40%)"
                ]
            })
            
            # Save
            result = await session.call_tool("save_presentation", {
                "presentation_id": "complete_shapes",
                "output_path": "output/complete_shapes_presentation.pptx"
            })
            
            print(f"✓ Complete presentation saved: {result.content[0].text}")


async def interactive_mode():
    """Interactive menu for demonstrations"""
    print("\n" + "="*60)
    print("PowerPoint MCP Server - Shapes & SmartArt Demo")
    print("="*60)
    print("\nThis demo showcases PowerPoint shapes and diagrams:")
    print("- Chevron process flows (horizontal & vertical)")
    print("- Timeline with circular markers")
    print("- Cycle diagrams (circular process)")
    print("- Pyramid diagrams (hierarchical)")
    print("- Matrix diagrams (2x2 grid)")
    print("\nSelect an example to run:")
    print("1. Process Flows (Chevrons)")
    print("2. Timeline")
    print("3. Diagrams (Cycle, Pyramid, Matrix)")
    print("4. Complete Presentation (All Features)")
    print("5. Run All Examples")
    print("6. Exit")
    
    choice = input("\nEnter choice (1-6): ")
    
    if choice == "1":
        await example_process_flows()
    elif choice == "2":
        await example_timeline()
    elif choice == "3":
        await example_diagrams()
    elif choice == "4":
        await example_complete_shapes_presentation()
    elif choice == "5":
        await example_process_flows()
        await example_timeline()
        await example_diagrams()
        await example_complete_shapes_presentation()
    elif choice == "6":
        print("\nExiting...")
        return
    else:
        print("\nInvalid choice. Please select 1-6.")
        return
    
    # Save the demo presentation
    if choice in ["1", "2", "3", "5"]:
        server_params = StdioServerParameters(
            command="python",
            args=["ppt_mcp_server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool("save_presentation", {
                    "presentation_id": "shapes_demo",
                    "output_path": "output/shapes_demo.pptx"
                })
                
                print(f"\n✓ Saved: {result.content[0].text}")
    
    print("\n" + "="*60)
    print("Demo complete! Check the 'output/' folder for .pptx files")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(interactive_mode())
