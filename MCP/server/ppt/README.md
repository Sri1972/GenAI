# PowerPoint MCP Server

An MCP (Model Context Protocol) server that provides tools for creating and manipulating PowerPoint presentations using the python-pptx library.

## Features

### Tools Available

1. **create_presentation** - Create a new PowerPoint presentation
   - Parameters: `presentation_id`, optional `template_path`
   - Returns: Presentation ID for use in subsequent operations

2. **add_title_slide** - Add a title slide
   - Parameters: `presentation_id`, `title`, optional `subtitle`

3. **add_content_slide** - Add a slide with title and bullet points
   - Parameters: `presentation_id`, `title`, `content` (array of strings)

4. **add_two_column_slide** - Add a slide with two columns of content
   - Parameters: `presentation_id`, `title`, `left_content`, `right_content`

5. **add_chart_slide** - Add a slide with a chart (bar, line, pie, column)
   - Parameters: `presentation_id`, `title`, `chart_type`, `categories`, `series_data`

6. **add_table_slide** - Add a slide with a table
   - Parameters: `presentation_id`, `title`, `headers`, `rows`

7. **add_image_slide** - Add a slide with an image (for external diagrams)
   - Parameters: `presentation_id`, `title`, `image_path`, optional `left`, `top`, `width`, `height`

8. **add_gantt_chart_slide** - Add a Gantt chart with color-coded status
   - Parameters: `presentation_id`, `title`, `tasks` (with name, start, end, duration, status)

9. **add_process_flow_slide** - Add a process flow with chevron/arrow shapes
   - Parameters: `presentation_id`, `title`, `steps`, optional `flow_type` (horizontal/vertical)

10. **add_timeline_slide** - Add a timeline with circular markers and events
    - Parameters: `presentation_id`, `title`, `events` (with date and description)

11. **add_diagram_slide** - Add diagrams using shapes (cycle, pyramid, matrix)
    - Parameters: `presentation_id`, `title`, `diagram_type`, `items`
    - Diagram types:
      - **cycle**: Circular process diagram (PDCA, customer lifecycle, etc.)
      - **pyramid**: Hierarchical structure (organizational levels, priorities)
      - **matrix**: 2x2 grid (SWOT analysis, priority matrix - requires exactly 4 items)

12. **save_presentation** - Save the presentation to a file
    - Parameters: `presentation_id`, `output_path`

13. **list_presentations** - List all active presentations in memory

### Resources Available

The server exposes configuration templates, layout guides, and content guidelines:

- **config://** - Presentation configuration templates (standard, technical, modern)
- **layout://** - Layout guides for different slide types
- **guidelines://content** - Best practices for presentation content

### Prompts Available

Pre-configured prompts to guide presentation creation:

- **create_business_presentation** - Standard business deck structure
- **create_technical_presentation** - Architecture and system design
- **create_data_analysis_presentation** - Charts and insights focus
- **create_project_status_presentation** - Progress reports with timelines
- **slide_design_guidelines** - Best practices for slide design
- **chart_selection_guide** - When to use different chart types

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Running the Server

```bash
python ppt_mcp_server.py
```

### Example Usage from MCP Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def create_presentation_example():
    server_params = StdioServerParameters(
        command="python",
        args=["ppt_mcp_server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create presentation
            result = await session.call_tool("create_presentation", {
                "presentation_id": "my_presentation"
            })
            print(result)
            
            # Add title slide
            result = await session.call_tool("add_title_slide", {
                "presentation_id": "my_presentation",
                "title": "MCP Architecture Overview",
                "subtitle": "Model Context Protocol Integration Patterns"
            })
            print(result)
            
            # Add content slide
            result = await session.call_tool("add_content_slide", {
                "presentation_id": "my_presentation",
                "title": "Key Features",
                "content": [
                    "Unified interface for diverse data sources",
                    "Standardized tool definitions",
                    "Centralized authentication",
                    "Scalable architecture"
                ]
            })
            print(result)
            
            # Add chart
            result = await session.call_tool("add_chart_slide", {
                "presentation_id": "my_presentation",
                "title": "Integration Statistics",
                "chart_type": "column",
                "categories": ["Q1", "Q2", "Q3", "Q4"],
                "series_data": [
                    {"name": "APIs", "values": [10, 15, 20, 25]},
                    {"name": "Databases", "values": [5, 8, 12, 15]}
                ]
            })
            print(result)
            
            # Save presentation
            result = await session.call_tool("save_presentation", {
                "presentation_id": "my_presentation",
                "output_path": "output/mcp_architecture.pptx"
            })
            print(result)

if __name__ == "__main__":
    asyncio.run(create_presentation_example())
```

## Configuration for Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ppt": {
      "command": "python",
      "args": ["D:\\SourceCode\\GenAI\\MCP\\server\\ppt\\ppt_mcp_server.py"]
    }
  }
}
```

## Output

Presentations are saved as `.pptx` files that can be opened in:
- Microsoft PowerPoint
- Google Slides
- LibreOffice Impress
- Apple Keynote

## Architecture

The server follows proper MCP design patterns with separation of concerns:

- **MCP Server Layer** (`ppt_mcp_server.py`) - Thin orchestration layer handling protocol
- **Service Layer** (`services/ppt_service.py`) - Business logic for PowerPoint operations
- **Resources Layer** (`resources/ppt_resources.py`) - Configuration templates and guidelines
- **Prompts Layer** (`prompts/ppt_prompts.py`) - Pre-configured presentation scenarios

Presentations are maintained in memory during the session, allowing incremental building via multiple tool calls. Each presentation is identified by a unique `presentation_id`.

## Supported Features

### Chart Types
- `bar` - Horizontal bar chart
- `column` - Vertical column chart
- `line` - Line chart
- `pie` - Pie chart

### Shape-Based Visualizations
- **Process Flows**: Chevron shapes for horizontal/vertical workflows
- **Timelines**: Circular markers with date labels and descriptions
- **Cycle Diagrams**: Circular arrangement for continuous processes (PDCA, etc.)
- **Pyramid Diagrams**: Hierarchical structures (organizational levels, priorities)
- **Matrix Diagrams**: 2x2 grids (SWOT analysis, priority matrices)

### Gantt Charts
- Color-coded task status (Complete, In Progress, Not Started, Blocked)
- Timeline visualization with start/end dates and duration

## Demo Scripts

Three demo scripts are provided to showcase capabilities:

1. **interactive_demo.py** - Basic features (slides, charts, tables)
2. **advanced_demo.py** - Gantt charts and data flow diagrams
3. **shapes_demo.py** - Process flows, timelines, and shape-based diagrams

Run any demo:
```bash
python interactive_demo.py
python advanced_demo.py
python shapes_demo.py
```

## Limitations

- Presentations exist in memory until saved
- SmartArt graphics use shape-based approximations (python-pptx doesn't support native SmartArt)
- Matrix diagrams require exactly 4 items for 2x2 layout
- No support for animations or transitions yet

## Future Enhancements

- [x] Support for images and shapes
- [x] Gantt charts and timelines
- [x] Diagram support (cycle, pyramid, matrix)
- [ ] Native SmartArt graphics (if python-pptx adds support)
- [ ] Custom themes and color schemes
- [ ] Advanced text formatting options
- [ ] Slide notes and comments
- [ ] Export to PDF
- [ ] More chart types (scatter, area, bubble)
