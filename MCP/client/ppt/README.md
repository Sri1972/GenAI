# PowerPoint LLM Client

Natural language interface for creating PowerPoint presentations using Claude and MCP.

## Overview

This client allows you to create professional PowerPoint presentations using **natural language**. The LLM (Claude) handles all the complexity:
- Interprets your natural language requests
- Chooses appropriate shapes, layouts, and tools
- Determines colors, sizes, and positioning
- Structures data correctly for MCP tool calls

You just describe what you want, and the AI figures out how to build it!

## Setup

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

**Note**: The requirements include all LLM providers. You only need to install the ones you plan to use:
- **Bedrock** (default): `pip install boto3 botocore`
- **Anthropic**: `pip install anthropic`
- **OpenAI**: `pip install openai`
- **Gemini**: `pip install google-generativeai`

### 2. Configure Environment

Copy the `.env` file and configure your preferred provider:

```powershell
# The .env file is already configured with credentials
# Default provider is Bedrock (LLM_PROVIDER=bedrock)
```

**LLM Provider Options:**
- `bedrock` - AWS Bedrock (default, uses Claude Sonnet 4)
- `anthropic` - Anthropic Claude API
- `openai` - OpenAI GPT models
- `gemini` - Google Gemini

**To switch providers**, edit `.env`:
```bash
LLM_PROVIDER=bedrock  # or anthropic, openai, gemini
```

### 3. Verify MCP Server Path

The client expects the MCP server at: `../../server/ppt/ppt_mcp_server.py`

If your path is different, update line 173 in `ppt_llm_client.py`:
```python
args=["your/path/to/ppt_mcp_server.py"]
```

## Usage

### Interactive Mode

Start an interactive chat session:

```powershell
python ppt_llm_client.py
```

Then just describe what you want:

```
💬 You: Create a presentation about AI trends in 2025

💬 You: Add a slide with 3 key benefits of AI: efficiency, accuracy, and scalability

💬 You: Create an org chart showing CEO, 3 VPs, and 5 managers

💬 You: Add a metrics dashboard with our KPIs: 95% satisfaction, 1M users, $5M revenue

💬 You: save
Output path: output/ai_trends.pptx
```

### Demo Mode

Run pre-built examples:

```powershell
python ppt_llm_client.py demo
```

### Programmatic Usage

```python
import asyncio
from ppt_llm_client import PowerPointLLMClient

async def main():
    # Initialize with default provider from .env (Bedrock)
    client = PowerPointLLMClient()
    
    # Or specify a provider explicitly
    # client = PowerPointLLMClient(provider="anthropic")
    # client = PowerPointLLMClient(provider="openai")
    # client = PowerPointLLMClient(provider="gemini")
    
    await client.start_mcp_session()
    
    # Natural language requests
    await client.chat(
        "Create a presentation about Q4 results with a title slide",
        presentation_id="q4_report"
    )
    
    await client.chat(
        "Add a slide with our revenue chart showing growth from $1M to $5M over 4 quarters",
        presentation_id="q4_report"
    )
    
    await client.chat(
        "Create a team org chart with 5 departments",
        presentation_id="q4_report"
    )
    
    await client.save_presentation("q4_report", "output/q4_report.pptx")
    await client.close_mcp_session()

asyncio.run(main())
```

## Example Requests

### Simple Slides
- "Create a presentation titled 'Sales Strategy 2025'"
- "Add a title slide with subtitle 'Q1 Planning'"
- "Add a bullet point slide about our values"

### Org Charts & Hierarchies
- "Create an org chart with CEO at top and 3 departments"
- "Show our team structure: engineering, sales, marketing"
- "Add a hierarchy showing reporting lines"

### Dashboards & Metrics
- "Create a dashboard with 4 KPIs in circles"
- "Show metrics: 85% uptime, 1.2M users, $5.2M revenue"
- "Add performance indicators with traffic light colors"

### Process Flows
- "Show the customer journey: Awareness → Interest → Purchase → Loyalty"
- "Create a development process with 5 stages"
- "Add a timeline from January to December"

### Custom Shapes & Diagrams
- "Create a Venn diagram with 3 overlapping circles"
- "Show a cycle with 4 stages"
- "Add a pyramid with 5 levels"
- "Create a matrix with 4 quadrants"

### Charts & Data
- "Add a bar chart comparing sales across regions"
- "Show revenue growth in a line chart"
- "Create a pie chart of market share"

## How It Works

### Architecture

```
User (Natural Language)
    ↓
LLM Client (ppt_llm_client.py)
    ↓
Claude AI (interprets & structures)
    ↓
MCP Protocol (tool calls)
    ↓
PowerPoint MCP Server (ppt_mcp_server.py)
    ↓
PowerPoint Service (creates slides)
    ↓
.pptx File
```

### Key Features

1. **Natural Language Processing**: Describe what you want in plain English
2. **Intelligent Layout**: LLM chooses appropriate layouts and spacing
3. **Color Selection**: AI picks professional color schemes
4. **Auto-sizing**: Shapes automatically size based on content
5. **Context Awareness**: Maintains conversation history for follow-ups
6. **Error Recovery**: Handles errors gracefully

### Available Tools

The LLM can use these MCP tools:

| Tool | Purpose | Example |
|------|---------|---------|
| `create_presentation` | Create new presentation | "Create a presentation" |
| `add_title_slide` | Title slide | "Add a title slide" |
| `add_content_slide` | Bullet points | "Add key points about..." |
| `add_shape_slide` | Custom shapes | "Create an org chart" |
| `add_chart_slide` | Charts/graphs | "Show revenue growth" |
| `add_process_flow_slide` | Process flows | "Show the process..." |
| `add_timeline_slide` | Timelines | "Create a timeline" |
| `add_diagram_slide` | Cycle/pyramid/matrix | "Add a cycle diagram" |
| `add_table_slide` | Tables | "Add a comparison table" |
| `save_presentation` | Save to file | "save" command |

### Shape Types Supported

The LLM can use 20+ shape types:
- Basic: circle, square, rectangle, rounded_rectangle, oval
- Polygons: pentagon, hexagon, octagon, triangle, diamond
- Arrows: arrow (right arrow)
- Stars: star, star5, star6, star7
- Special: cloud, heart, lightning, sun, moon

## Examples Output

### Example 1: Simple Request
```
💬 You: Create a sales presentation with a title slide and 3 key metrics

LLM Output:
1. Creates presentation
2. Adds title slide "Sales Performance"
3. Adds shape slide with 3 circles showing metrics
4. Chooses professional colors (blue, green, gold)
5. Positions shapes evenly across slide
```

### Example 2: Complex Layout
```
💬 You: Build an org chart with 10 people across 3 levels

LLM Output:
1. Calculates positions for 10 shapes
2. Arranges in hierarchy: 1 top, 3 middle, 6 bottom
3. Sizes boxes appropriately
4. Color-codes by level
5. Centers the layout
```

### Example 3: Dashboard
```
💬 You: Create a KPI dashboard with traffic lights

LLM Output:
1. Creates 4-6 shapes for KPIs
2. Uses red/yellow/green colors for status
3. Adds large readable numbers
4. Positions in grid layout
5. Adds icons or symbols
```

## Customization

### Modify System Prompt

Edit the `_build_system_prompt()` method to change:
- Default colors
- Layout preferences
- Naming conventions
- Design guidelines

### Add Custom Tools

1. Add tool to MCP server
2. Document in `tools_documentation` string
3. LLM will automatically use it

### Change LLM Model

Update line 184:
```python
model="claude-3-5-sonnet-20241022",  # or another model
```

## Tips for Best Results

### Be Specific
❌ "Add some shapes"
✅ "Add 3 circles with our revenue, users, and satisfaction metrics"

### Describe Layout
❌ "Show the team"
✅ "Create an org chart with CEO at top, 3 directors below, and 5 managers at bottom"

### Mention Colors
❌ "Make it look good"
✅ "Use blue for leadership, green for teams, and gold for metrics"

### Break Complex Requests
❌ "Create a complete sales deck with everything"
✅ Multiple requests:
1. "Create a title slide"
2. "Add our mission statement"
3. "Show Q4 results in a chart"
4. "Add customer testimonials"

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Set your API key: `$env:ANTHROPIC_API_KEY = "sk-..."`

### "MCP session not started"
Call `await client.start_mcp_session()` first

### "Presentation 'X' not found"
Create the presentation first: "Create a presentation"

### Shapes not visible
Check the fix in `services/ppt_service.py` line 812 - should use `STAR_5_POINT` not `STAR_5`

### JSON parsing errors
LLM response wasn't valid JSON - check system prompt

## Advanced Usage

### Multiple Presentations

```python
await client.chat("Create a sales deck", "sales_deck")
await client.chat("Create a marketing deck", "marketing_deck")
await client.save_presentation("sales_deck", "output/sales.pptx")
await client.save_presentation("marketing_deck", "output/marketing.pptx")
```

### Conversation Context

The client maintains conversation history:
```python
await client.chat("Create a presentation about AI")
await client.chat("Add a slide about machine learning")  # Knows context
await client.chat("Add another about neural networks")   # Still knows context
```

### Batch Operations

```python
requests = [
    "Create a presentation",
    "Add title slide",
    "Add 5 slides about our products",
    "Add a contact slide"
]

for req in requests:
    await client.chat(req, "my_presentation")
```

## Files

- `ppt_llm_client.py` - Main LLM client
- `README.md` - This file
- `examples/` - Example scripts (to be created)

## Related

- PowerPoint MCP Server: `../../server/ppt/`
- Custom Shapes Guide: `../../server/ppt/CUSTOM_SHAPES_GUIDE.md`
- Shapes Features: `../../server/ppt/SHAPES_FEATURES.md`

## License

MIT
