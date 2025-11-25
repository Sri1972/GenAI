"""
Demo script for PowerPoint MCP Server - Custom Shapes

This script demonstrates the add_shape_slide tool which allows:
1. Adding any shape (circles, squares, rectangles, stars, hearts, etc.)
2. Auto-sizing shapes based on text content
3. Custom colors and positioning
4. Multiple shapes on a single slide
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def example_basic_shapes():
    """Example 1: Basic shapes with text"""
    print("\n=== Example 1: Basic Shapes with Text ===")
    
    # Basic shapes with auto-sizing
    return {
        "presentation_id": "shapes_demo",
        "title": "Basic Shapes (Auto-sized)",
        "shapes": [
            {
                "shape_type": "circle",
                "text": "Circle",
                "left": 1.5,
                "top": 2.5,
                "color": [68, 114, 196]
            },
            {
                "shape_type": "square",
                "text": "Square",
                "left": 4,
                "top": 2.5,
                "color": [112, 173, 71]
            },
            {
                "shape_type": "rounded_rectangle",
                "text": "Rounded Rectangle",
                "left": 6.5,
                "top": 2.5,
                "color": [255, 192, 0]
            }
        ]
    }


async def example_special_shapes():
    """Example 2: Special shapes (stars, hearts, arrows)"""
    print("\n=== Example 2: Special Shapes ===")
    
    return {
        "presentation_id": "shapes_demo",
        "title": "Special Shapes",
        "shapes": [
            {
                "shape_type": "star",
                "text": "★ Star",
                "left": 1,
                "top": 2,
                "color": [255, 192, 0]
            },
            {
                "shape_type": "heart",
                "text": "♥",
                "left": 3.5,
                "top": 2,
                "color": [237, 125, 49]
            },
            {
                "shape_type": "arrow",
                "text": "Next →",
                "left": 6,
                "top": 2,
                "color": [68, 114, 196]
            },
            {
                "shape_type": "diamond",
                "text": "Diamond",
                "left": 1,
                "top": 4.5,
                "color": [112, 173, 71]
            },
            {
                "shape_type": "hexagon",
                "text": "Hexagon",
                "left": 3.5,
                "top": 4.5,
                "color": [68, 114, 196]
            },
            {
                "shape_type": "octagon",
                "text": "STOP",
                "left": 6,
                "top": 4.5,
                "color": [192, 0, 0],
                "font_size": 18
            }
        ]
    }


async def example_custom_sizing():
    """Example 3: Custom sizing and colors"""
    print("\n=== Example 3: Custom Sizing & Colors ===")
    
    return {
        "presentation_id": "shapes_demo",
        "title": "Custom Sizing & Colors",
        "shapes": [
            {
                "shape_type": "rectangle",
                "text": "Large Rectangle\nWith Multiple Lines\nOf Text",
                "left": 1,
                "top": 2,
                "width": 3.5,
                "height": 2.5,
                "color": [68, 114, 196],
                "font_size": 16
            },
            {
                "shape_type": "circle",
                "text": "Small\nCircle",
                "left": 5,
                "top": 2,
                "width": 2,
                "height": 2,
                "color": [112, 173, 71],
                "font_size": 12
            },
            {
                "shape_type": "oval",
                "text": "Wide Oval",
                "left": 2.5,
                "top": 5,
                "width": 4,
                "height": 1.5,
                "color": [255, 192, 0],
                "text_color": [0, 0, 0]  # Black text
            }
        ]
    }


async def example_organizational_chart():
    """Example 4: Simple organizational chart using shapes"""
    print("\n=== Example 4: Organizational Chart ===")
    
    return {
        "presentation_id": "shapes_demo",
        "title": "Organizational Structure",
        "shapes": [
            # Top level - CEO
            {
                "shape_type": "rounded_rectangle",
                "text": "CEO",
                "left": 3.5,
                "top": 1.5,
                "width": 2.5,
                "height": 1,
                "color": [68, 114, 196]
            },
            # Second level - Directors
            {
                "shape_type": "rounded_rectangle",
                "text": "Director\nEngineering",
                "left": 1,
                "top": 3,
                "width": 2,
                "height": 1.2,
                "color": [112, 173, 71]
            },
            {
                "shape_type": "rounded_rectangle",
                "text": "Director\nSales",
                "left": 3.75,
                "top": 3,
                "width": 2,
                "height": 1.2,
                "color": [112, 173, 71]
            },
            {
                "shape_type": "rounded_rectangle",
                "text": "Director\nOperations",
                "left": 6.5,
                "top": 3,
                "width": 2,
                "height": 1.2,
                "color": [112, 173, 71]
            },
            # Third level - Managers
            {
                "shape_type": "rectangle",
                "text": "Dev Team",
                "left": 0.5,
                "top": 5,
                "width": 1.5,
                "height": 0.8,
                "color": [255, 192, 0],
                "font_size": 11
            },
            {
                "shape_type": "rectangle",
                "text": "QA Team",
                "left": 2.25,
                "top": 5,
                "width": 1.5,
                "height": 0.8,
                "color": [255, 192, 0],
                "font_size": 11
            },
            {
                "shape_type": "rectangle",
                "text": "Sales East",
                "left": 4,
                "top": 5,
                "width": 1.5,
                "height": 0.8,
                "color": [255, 192, 0],
                "font_size": 11
            },
            {
                "shape_type": "rectangle",
                "text": "Sales West",
                "left": 5.75,
                "top": 5,
                "width": 1.5,
                "height": 0.8,
                "color": [255, 192, 0],
                "font_size": 11
            },
            {
                "shape_type": "rectangle",
                "text": "Logistics",
                "left": 7.5,
                "top": 5,
                "width": 1.5,
                "height": 0.8,
                "color": [255, 192, 0],
                "font_size": 11
            }
        ]
    }


async def example_infographic():
    """Example 5: Infographic-style slide"""
    print("\n=== Example 5: Infographic Style ===")
    
    return {
        "presentation_id": "shapes_demo",
        "title": "Key Metrics Dashboard",
        "shapes": [
            # Metric 1
            {
                "shape_type": "circle",
                "text": "85%\nUptime",
                "left": 1,
                "top": 2.5,
                "width": 2,
                "height": 2,
                "color": [112, 173, 71],
                "font_size": 18
            },
            # Metric 2
            {
                "shape_type": "circle",
                "text": "1.2M\nUsers",
                "left": 3.75,
                "top": 2.5,
                "width": 2,
                "height": 2,
                "color": [68, 114, 196],
                "font_size": 18
            },
            # Metric 3
            {
                "shape_type": "circle",
                "text": "$5.2M\nRevenue",
                "left": 6.5,
                "top": 2.5,
                "width": 2,
                "height": 2,
                "color": [255, 192, 0],
                "font_size": 18
            },
            # Status indicator
            {
                "shape_type": "star",
                "text": "⭐",
                "left": 4,
                "top": 5.5,
                "width": 1.5,
                "height": 1.5,
                "color": [255, 192, 0],
                "font_size": 48
            }
        ]
    }


async def example_complete_presentation():
    """Example 6: Complete presentation with all shape features"""
    print("\n=== Example 6: Complete Presentation ===")
    
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
                "title": "Custom Shapes Demo",
                "subtitle": "Auto-sized shapes with custom styling"
            })
            
            # Add all example slides
            examples = [
                await example_basic_shapes(),
                await example_special_shapes(),
                await example_custom_sizing(),
                await example_organizational_chart(),
                await example_infographic()
            ]
            
            for example in examples:
                await session.call_tool("add_shape_slide", example)
                print(f"✓ {example['title']} slide created")
            
            # Save
            result = await session.call_tool("save_presentation", {
                "presentation_id": "shapes_demo",
                "output_path": "output/custom_shapes_demo.pptx"
            })
            
            print(f"\n✓ Complete presentation saved: {result.content[0].text}")


async def run_single_example(name: str, example_data: dict):
    """Run a single example in its own session"""
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
                "title": "Custom Shapes Demo",
                "subtitle": example_data["title"]
            })
            
            # Add the example slide
            await session.call_tool("add_shape_slide", example_data)
            print(f"✓ {example_data['title']} slide created")
            
            # Save
            result = await session.call_tool("save_presentation", {
                "presentation_id": "shapes_demo",
                "output_path": f"output/{name}_shapes_demo.pptx"
            })
            
            print(f"✓ Saved: {result.content[0].text}")


async def interactive_mode():
    """Interactive menu for demonstrations"""
    print("\n" + "="*60)
    print("PowerPoint MCP Server - Custom Shapes Demo")
    print("="*60)
    print("\nThis demo showcases the add_shape_slide tool:")
    print("- Any shape type (circles, squares, stars, hearts, etc.)")
    print("- Auto-sizing based on text content")
    print("- Custom colors and positioning")
    print("- Multiple shapes per slide")
    print("\nSelect an example to run:")
    print("1. Basic Shapes (Circle, Square, Rectangle)")
    print("2. Special Shapes (Stars, Hearts, Arrows)")
    print("3. Custom Sizing & Colors")
    print("4. Organizational Chart")
    print("5. Infographic Style")
    print("6. Complete Presentation (All Examples)")
    print("7. Exit")
    
    choice = input("\nEnter choice (1-7): ")
    
    if choice == "1":
        await run_single_example("basic", await example_basic_shapes())
    elif choice == "2":
        await run_single_example("special", await example_special_shapes())
    elif choice == "3":
        await run_single_example("sizing", await example_custom_sizing())
    elif choice == "4":
        await run_single_example("org", await example_organizational_chart())
    elif choice == "5":
        await run_single_example("infographic", await example_infographic())
    elif choice == "6":
        await example_complete_presentation()
    elif choice == "7":
        print("\nExiting...")
        return
    else:
        print("\nInvalid choice. Please select 1-7.")
        return
    
    print("\n" + "="*60)
    print("Demo complete! Check the 'output/' folder for .pptx files")
    print("="*60)


async def save_demo():
    """Save the demo presentation"""
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool("save_presentation", {
                "presentation_id": "shapes_demo",
                "output_path": "output/custom_shapes_demo.pptx"
            })
            
            print(f"\n✓ Saved: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(interactive_mode())
