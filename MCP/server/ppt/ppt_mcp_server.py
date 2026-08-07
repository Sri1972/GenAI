#!/usr/bin/env python3
"""
PowerPoint MCP Server

An MCP server that provides tools, resources, and prompts for creating and 
manipulating PowerPoint presentations. Follows proper separation of concerns
with LLM client → MCP Server → PowerPoint Service architecture.
"""

import asyncio
import logging
from typing import Any, Optional
from pathlib import Path
import json

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource, Prompt, GetPromptResult, PromptMessage

# Import service layer
from services.ppt_service import PresentationManager

# Import resources and prompts
from resources.ppt_resources import ResourceManager
from prompts.ppt_prompts import get_prompt, list_prompts as list_prompt_templates, get_prompt_template

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ppt-mcp-server")

# Initialize service layer
ppt_service = PresentationManager()
resource_manager = ResourceManager()

# Server instance
app = Server("ppt-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available PowerPoint manipulation tools."""
    return [
        Tool(
            name="create_presentation",
            description="Create a new PowerPoint presentation. Returns a presentation ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Unique identifier for this presentation"
                    },
                    "template_path": {
                        "type": "string",
                        "description": "Optional path to a template .pptx file"
                    }
                },
                "required": ["presentation_id"]
            }
        ),
        Tool(
            name="add_title_slide",
            description="Add a title slide to the presentation",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Main title text"
                    },
                    "subtitle": {
                        "type": "string",
                        "description": "Subtitle text"
                    }
                },
                "required": ["presentation_id", "title"]
            }
        ),
        Tool(
            name="add_content_slide",
            description="Add a slide with title and content (bullet points or text) with optional styling",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "content": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of bullet points or content items"
                    },
                    "layout": {
                        "type": "string",
                        "enum": ["title_and_content", "two_content", "blank"],
                        "description": "Slide layout type (default: title_and_content)"
                    },
                    "font_size": {
                        "type": "integer",
                        "description": "Optional font size in points (e.g., 18, 24). Default uses template settings."
                    },
                    "font_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional font color as RGB array [R, G, B] (e.g., [0, 0, 0] for black, [255, 0, 0] for red)"
                    },
                    "title_font_size": {
                        "type": "integer",
                        "description": "Optional title font size in points"
                    },
                    "title_font_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional title font color as RGB array"
                    },
                    "border_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional border color as RGB array (e.g., [0, 0, 0] for black)"
                    },
                    "border_width": {
                        "type": "number",
                        "description": "Optional border width in points (e.g., 1.5, 2.0)"
                    }
                },
                "required": ["presentation_id", "title", "content"]
            }
        ),
        Tool(
            name="add_two_column_slide",
            description="Add a slide with title and two columns of content with optional styling",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "left_content": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Left column content (bullet points)"
                    },
                    "right_content": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Right column content (bullet points)"
                    },
                    "font_size": {
                        "type": "integer",
                        "description": "Optional font size in points (e.g., 18, 24)"
                    },
                    "font_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional font color as RGB array [R, G, B]"
                    },
                    "title_font_size": {
                        "type": "integer",
                        "description": "Optional title font size in points"
                    },
                    "title_font_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional title font color as RGB array"
                    },
                    "border_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "Optional border color as RGB array"
                    },
                    "border_width": {
                        "type": "number",
                        "description": "Optional border width in points"
                    }
                },
                "required": ["presentation_id", "title", "left_content", "right_content"]
            }
        ),
        Tool(
            name="add_chart_slide",
            description="Add a slide with a chart (bar, line, or pie)",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "column"],
                        "description": "Type of chart to create"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Category labels for chart"
                    },
                    "series_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "values": {"type": "array", "items": {"type": "number"}}
                            }
                        },
                        "description": "Series data with name and values"
                    }
                },
                "required": ["presentation_id", "title", "chart_type", "categories", "series_data"]
            }
        ),
        Tool(
            name="add_table_slide",
            description="Add a slide with a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Table column headers"
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "description": "Table rows data"
                    }
                },
                "required": ["presentation_id", "title", "headers", "rows"]
            }
        ),
        Tool(
            name="add_image_slide",
            description="Add a slide with an image (for diagrams, Gantt charts, flowcharts, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to image file (PNG, JPG, SVG)"
                    },
                    "left": {
                        "type": "number",
                        "description": "Left position in inches (default: 1.0)"
                    },
                    "top": {
                        "type": "number",
                        "description": "Top position in inches (default: 2.0)"
                    },
                    "width": {
                        "type": "number",
                        "description": "Width in inches (optional)"
                    },
                    "height": {
                        "type": "number",
                        "description": "Height in inches (optional)"
                    }
                },
                "required": ["presentation_id", "title", "image_path"]
            }
        ),
        Tool(
            name="add_gantt_chart_slide",
            description="Add a slide with a Gantt chart (timeline with color-coded status)",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to add slide to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Slide title"
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "duration": {"type": "string"},
                                "status": {"type": "string"}
                            }
                        },
                        "description": "List of tasks with name, start, end, duration, and status"
                    }
                },
                "required": ["presentation_id", "title", "tasks"]
            }
        ),
        Tool(
            name="add_process_flow_slide",
            description="Add a process flow slide with chevron/arrow shapes",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {"type": "string"},
                    "title": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of process steps"
                    },
                    "flow_type": {
                        "type": "string",
                        "enum": ["horizontal", "vertical"],
                        "description": "Direction of flow (default: horizontal)"
                    }
                },
                "required": ["presentation_id", "title", "steps"]
            }
        ),
        Tool(
            name="add_timeline_slide",
            description="Add a timeline slide with events and dates using shapes",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {"type": "string"},
                    "title": {"type": "string"},
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        },
                        "description": "List of events with date and description"
                    }
                },
                "required": ["presentation_id", "title", "events"]
            }
        ),
        Tool(
            name="add_diagram_slide",
            description="Add a diagram slide (cycle, pyramid, or matrix) using shapes",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {"type": "string"},
                    "title": {"type": "string"},
                    "diagram_type": {
                        "type": "string",
                        "enum": ["cycle", "pyramid", "matrix"],
                        "description": "Type of diagram to create"
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Items to display in diagram (4 items required for matrix)"
                    }
                },
                "required": ["presentation_id", "title", "diagram_type", "items"]
            }
        ),
        Tool(
            name="add_shape_slide",
            description="Add a slide with custom shapes (circles, squares, rectangles, etc.) with auto-sizing based on text",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {"type": "string"},
                    "title": {"type": "string"},
                    "shapes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "shape_type": {
                                    "type": "string",
                                    "enum": ["circle", "square", "rectangle", "rounded_rectangle", 
                                           "oval", "pentagon", "hexagon", "octagon", "triangle",
                                           "diamond", "arrow", "star", "star5", "star6", "star7",
                                           "cloud", "heart", "lightning", "sun", "moon"],
                                    "description": "Type of shape to create"
                                },
                                "text": {
                                    "type": "string",
                                    "description": "Text to display in shape (optional)"
                                },
                                "left": {
                                    "type": "number",
                                    "description": "Left position in inches"
                                },
                                "top": {
                                    "type": "number",
                                    "description": "Top position in inches"
                                },
                                "width": {
                                    "type": "number",
                                    "description": "Width in inches (auto-sized if text provided and omitted)"
                                },
                                "height": {
                                    "type": "number",
                                    "description": "Height in inches (auto-sized if text provided and omitted)"
                                },
                                "color": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "RGB color as [R, G, B] (default: [68, 114, 196])"
                                },
                                "font_size": {
                                    "type": "number",
                                    "description": "Font size in points (default: 14)"
                                },
                                "text_color": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Text RGB color as [R, G, B] (default: [255, 255, 255])"
                                }
                            },
                            "required": ["shape_type", "left", "top"]
                        },
                        "description": "List of shapes to add to slide"
                    }
                },
                "required": ["presentation_id", "title", "shapes"]
            }
        ),
        Tool(
            name="save_presentation",
            description="Save the presentation to a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "presentation_id": {
                        "type": "string",
                        "description": "Presentation ID to save"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output file path (e.g., 'output/presentation.pptx')"
                    }
                },
                "required": ["presentation_id", "output_path"]
            }
        ),
        Tool(
            name="list_presentations",
            description="List all active presentations in memory",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available PowerPoint resources (configs, templates, guidelines)."""
    resources = []
    
    # Configuration templates
    for config in resource_manager.list_configs():
        resources.append(Resource(
            uri=f"config://{config['name']}",
            name=f"Config: {config['name']}",
            description=config['description'],
            mimeType="application/json"
        ))
    
    # Layout guides
    for layout in resource_manager.list_layouts():
        resources.append(Resource(
            uri=f"layout://{layout['name']}",
            name=f"Layout: {layout['name']}",
            description=layout['description'],
            mimeType="application/json"
        ))
    
    # Content guidelines
    resources.append(Resource(
        uri="guidelines://content",
        name="Content Guidelines",
        description="Best practices for presentation content",
        mimeType="application/json"
    ))
    
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific resource by URI."""
    try:
        if uri.startswith("config://"):
            config_name = uri.replace("config://", "")
            config = resource_manager.get_config(config_name)
            return json.dumps(config, indent=2)
        
        elif uri.startswith("layout://"):
            layout_name = uri.replace("layout://", "")
            layout = resource_manager.get_layout_guide(layout_name)
            return json.dumps(layout, indent=2)
        
        elif uri == "guidelines://content":
            guidelines = resource_manager.get_content_guidelines()
            return json.dumps(guidelines, indent=2)
        
        else:
            return json.dumps({"error": "Resource not found"})
            
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {str(e)}")
        return json.dumps({"error": str(e)})


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available PowerPoint generation prompts."""
    prompts = []
    
    for prompt_info in list_prompt_templates():
        prompts.append(Prompt(
            name=prompt_info["name"],
            description=prompt_info["description"]
        ))
    
    return prompts


@app.get_prompt()
async def get_prompt_handler(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Get a specific prompt template."""
    template = get_prompt_template(name)
    
    if not template:
        raise ValueError(f"Prompt '{name}' not found")
    
    return GetPromptResult(
        description=get_prompt(name).get("description", ""),
        messages=[
            PromptMessage(
                role="user",
                content={
                    "type": "text",
                    "text": template
                }
            )
        ]
    )


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls for PowerPoint operations."""
    
    try:
        if name == "create_presentation":
            return await create_presentation(arguments)
        elif name == "add_title_slide":
            return await add_title_slide(arguments)
        elif name == "add_content_slide":
            return await add_content_slide(arguments)
        elif name == "add_two_column_slide":
            return await add_two_column_slide(arguments)
        elif name == "add_chart_slide":
            return await add_chart_slide(arguments)
        elif name == "add_table_slide":
            return await add_table_slide(arguments)
        elif name == "add_image_slide":
            return await add_image_slide(arguments)
        elif name == "add_gantt_chart_slide":
            return await add_gantt_chart_slide(arguments)
        elif name == "add_process_flow_slide":
            return await add_process_flow_slide(arguments)
        elif name == "add_timeline_slide":
            return await add_timeline_slide(arguments)
        elif name == "add_diagram_slide":
            return await add_diagram_slide(arguments)
        elif name == "add_shape_slide":
            return await add_shape_slide(arguments)
        elif name == "save_presentation":
            return await save_presentation(arguments)
        elif name == "list_presentations":
            return await list_presentations_tool(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def create_presentation(args: dict) -> list[TextContent]:
    """Create a new PowerPoint presentation using the service layer."""
    presentation_id = args["presentation_id"]
    template_path = args.get("template_path")
    
    result = ppt_service.create_presentation(presentation_id, template_path)
    
    return [TextContent(type="text", text=result["message"])]


async def add_title_slide(args: dict) -> list[TextContent]:
    """Add a title slide using the service layer."""
    result = ppt_service.add_title_slide(
        args["presentation_id"],
        args["title"],
        args.get("subtitle", "")
    )
    return [TextContent(type="text", text=result["message"])]


async def add_content_slide(args: dict) -> list[TextContent]:
    """Add a content slide using the service layer."""
    result = ppt_service.add_content_slide(
        args["presentation_id"],
        args["title"],
        args["content"],
        font_size=args.get("font_size"),
        font_color=args.get("font_color"),
        title_font_size=args.get("title_font_size"),
        title_font_color=args.get("title_font_color"),
        border_color=args.get("border_color"),
        border_width=args.get("border_width")
    )
    return [TextContent(type="text", text=result["message"])]


async def add_two_column_slide(args: dict) -> list[TextContent]:
    """Add a two-column slide using the service layer."""
    result = ppt_service.add_two_column_slide(
        args["presentation_id"],
        args["title"],
        args["left_content"],
        args["right_content"],
        font_size=args.get("font_size"),
        font_color=args.get("font_color"),
        title_font_size=args.get("title_font_size"),
        title_font_color=args.get("title_font_color"),
        border_color=args.get("border_color"),
        border_width=args.get("border_width")
    )
    return [TextContent(type="text", text=result["message"])]


async def add_chart_slide(args: dict) -> list[TextContent]:
    """Add a chart slide using the service layer."""
    result = ppt_service.add_chart_slide(
        args["presentation_id"],
        args["title"],
        args["chart_type"],
        args["categories"],
        args["series_data"]
    )
    return [TextContent(type="text", text=result["message"])]


async def add_table_slide(args: dict) -> list[TextContent]:
    """Add a table slide using the service layer."""
    result = ppt_service.add_table_slide(
        args["presentation_id"],
        args["title"],
        args["headers"],
        args["rows"]
    )
    return [TextContent(type="text", text=result["message"])]


async def add_image_slide(args: dict) -> list[TextContent]:
    """Add an image slide using the service layer."""
    result = ppt_service.add_image_slide(
        args["presentation_id"],
        args["title"],
        args["image_path"],
        args.get("left", 1.0),
        args.get("top", 2.0),
        args.get("width"),
        args.get("height")
    )
    return [TextContent(type="text", text=result["message"])]


async def add_gantt_chart_slide(args: dict) -> list[TextContent]:
    """Add a Gantt chart slide using the service layer."""
    result = ppt_service.add_gantt_chart_slide(
        args["presentation_id"],
        args["title"],
        args["tasks"]
    )
    return [TextContent(type="text", text=result["message"])]


async def add_process_flow_slide(args: dict) -> list[TextContent]:
    """Add a process flow slide with chevron shapes."""
    result = ppt_service.add_process_flow_slide(
        args["presentation_id"],
        args["title"],
        args["steps"],
        args.get("flow_type", "horizontal")
    )
    return [TextContent(type="text", text=result["message"])]


async def add_timeline_slide(args: dict) -> list[TextContent]:
    """Add a timeline slide with events."""
    result = ppt_service.add_timeline_slide(
        args["presentation_id"],
        args["title"],
        args["events"]
    )
    return [TextContent(type="text", text=result["message"])]


async def add_diagram_slide(args: dict) -> list[TextContent]:
    """Add a diagram slide (cycle, pyramid, matrix)."""
    result = ppt_service.add_diagram_slide(
        args["presentation_id"],
        args["title"],
        args["diagram_type"],
        args["items"]
    )
    return [TextContent(type="text", text=result["message"])]


async def add_shape_slide(args: dict) -> list[TextContent]:
    """Add a slide with custom shapes."""
    result = ppt_service.add_shape_slide(
        args["presentation_id"],
        args["title"],
        args["shapes"]
    )
    return [TextContent(type="text", text=result["message"])]


async def save_presentation(args: dict) -> list[TextContent]:
    """Save presentation using the service layer."""
    result = ppt_service.save_presentation(
        args["presentation_id"],
        args["output_path"]
    )
    return [TextContent(type="text", text=result["message"])]


async def list_presentations_tool(args: dict) -> list[TextContent]:
    """List presentations using the service layer."""
    result = ppt_service.list_presentations()
    
    if not result["presentations"]:
        return [TextContent(type="text", text=result["message"])]
    
    presentation_list = [
        f"- {p['id']}: {p['slide_count']} slides"
        for p in result["presentations"]
    ]
    
    return [TextContent(
        type="text",
        text=f"{result['message']}:\n" + "\n".join(presentation_list)
    )]


async def main():
    """Main entry point for the MCP server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info("PowerPoint MCP Server starting...")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
