# PowerPoint Shapes & Diagrams Features

## Overview

The PowerPoint MCP Server now includes comprehensive support for creating professional diagrams and visualizations using PowerPoint shapes. These features provide alternatives to SmartArt graphics (which python-pptx doesn't support natively) with full customization capabilities.

## Available Shape-Based Tools

### 1. Process Flow Slides (`add_process_flow_slide`)

Creates workflow diagrams with chevron or arrow shapes.

**Parameters:**
- `presentation_id`: Presentation identifier
- `title`: Slide title
- `steps`: List of process steps (strings)
- `flow_type`: "horizontal" or "vertical" (optional, default: "horizontal")

**Features:**
- Horizontal: Chevron shapes in a left-to-right flow
- Vertical: Rounded rectangles with down arrows between steps
- Alternating colors (blue/green) for visual appeal
- Centered text with white font

**Use Cases:**
- Software development workflows (Design → Build → Test → Deploy)
- Business processes (Requirements → Approval → Implementation)
- Manufacturing pipelines
- Customer journey maps

**Example:**
```python
await session.call_tool("add_process_flow_slide", {
    "presentation_id": "demo",
    "title": "Development Lifecycle",
    "steps": ["Planning", "Design", "Development", "Testing", "Deployment"],
    "flow_type": "horizontal"
})
```

---

### 2. Timeline Slides (`add_timeline_slide`)

Creates horizontal timelines with circular markers and event descriptions.

**Parameters:**
- `presentation_id`: Presentation identifier
- `title`: Slide title
- `events`: List of events with `date` and `description` fields

**Features:**
- Horizontal timeline with blue line
- Circular markers at each event
- Date labels above timeline
- Description text below timeline
- Auto-spacing of events

**Use Cases:**
- Project roadmaps
- Historical timelines
- Product release schedules
- Milestone tracking

**Example:**
```python
await session.call_tool("add_timeline_slide", {
    "presentation_id": "demo",
    "title": "2025 Product Roadmap",
    "events": [
        {"date": "Q1 2025", "description": "Feature A Launch"},
        {"date": "Q2 2025", "description": "Platform Upgrade"},
        {"date": "Q3 2025", "description": "Mobile App"},
        {"date": "Q4 2025", "description": "International Expansion"}
    ]
})
```

---

### 3. Cycle Diagrams (`add_diagram_slide` with `diagram_type="cycle"`)

Creates circular process diagrams with items arranged in a circle.

**Parameters:**
- `presentation_id`: Presentation identifier
- `title`: Slide title
- `diagram_type`: "cycle"
- `items`: List of items (3-8 recommended)

**Features:**
- Circular arrangement around a center point
- Oval shapes with 4 alternating colors
- Automatic angle calculation for even spacing
- White text, centered and bold

**Use Cases:**
- PDCA cycles (Plan-Do-Check-Act)
- Customer lifecycle (Awareness → Consideration → Purchase → Retention)
- Continuous improvement processes
- Feedback loops
- Agile sprints

**Example:**
```python
await session.call_tool("add_diagram_slide", {
    "presentation_id": "demo",
    "title": "Continuous Improvement Cycle",
    "diagram_type": "cycle",
    "items": ["Plan", "Do", "Check", "Act"]
})
```

---

### 4. Pyramid Diagrams (`add_diagram_slide` with `diagram_type="pyramid"`)

Creates hierarchical pyramid structures with decreasing width toward the top.

**Parameters:**
- `presentation_id`: Presentation identifier
- `title`: Slide title
- `diagram_type`: "pyramid"
- `items`: List of levels from top to bottom (3-6 recommended)

**Features:**
- Trapezoid shapes stacked vertically
- Width decreases by 15% per level
- 4 alternating colors (repeating pattern)
- Top-down hierarchy visualization

**Use Cases:**
- Organizational hierarchies
- Maslow's hierarchy of needs
- Market segmentation
- Priority levels
- Food pyramids

**Example:**
```python
await session.call_tool("add_diagram_slide", {
    "presentation_id": "demo",
    "title": "Organizational Structure",
    "diagram_type": "pyramid",
    "items": [
        "Executive Leadership",
        "Senior Management",
        "Middle Management",
        "Team Leads",
        "Individual Contributors"
    ]
})
```

---

### 5. Matrix Diagrams (`add_diagram_slide` with `diagram_type="matrix"`)

Creates 2x2 grid layouts for comparative analysis.

**Parameters:**
- `presentation_id`: Presentation identifier
- `title`: Slide title
- `diagram_type`: "matrix"
- `items`: **Exactly 4 items required** (top-left, top-right, bottom-left, bottom-right)

**Features:**
- Four rounded rectangle boxes in 2x2 grid
- Distinct colors for each quadrant (blue, green, yellow, orange)
- Equal sizing for all quadrants
- Perfect for SWOT analysis and priority matrices

**Use Cases:**
- SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)
- Priority matrices (High/Low Impact vs High/Low Effort)
- Decision frameworks
- 2x2 comparisons
- Eisenhower matrices

**Example:**
```python
await session.call_tool("add_diagram_slide", {
    "presentation_id": "demo",
    "title": "SWOT Analysis",
    "diagram_type": "matrix",
    "items": [
        "Strengths:\n• Strong brand\n• Loyal customers",
        "Weaknesses:\n• Limited resources\n• High costs",
        "Opportunities:\n• Market expansion\n• New tech",
        "Threats:\n• Competition\n• Economic downturn"
    ]
})
```

---

## Color Scheme

All shape-based diagrams use a consistent, professional color palette:

- **Blue**: RGB(68, 114, 196) - Primary color
- **Green**: RGB(112, 173, 71) - Secondary color
- **Yellow**: RGB(255, 192, 0) - Accent color
- **Orange**: RGB(237, 125, 49) - Accent color
- **White**: RGB(255, 255, 255) - Text color

## Shape Types Used

The implementation leverages various PowerPoint shapes from `MSO_SHAPE`:

- `CHEVRON` - For horizontal process flows
- `ROUNDED_RECTANGLE` - For vertical flows and matrix diagrams
- `DOWN_ARROW` - For connecting vertical flow steps
- `OVAL` - For cycle diagrams and timeline markers
- `TRAPEZOID` - For pyramid diagrams
- Straight connectors - For timeline base line

## Design Principles

1. **Consistency**: All diagrams use the same color palette and font sizing
2. **Readability**: White text on colored backgrounds for high contrast
3. **Spacing**: Adequate white space between elements
4. **Scalability**: Works well with 3-8 items (fewer or more may need adjustment)
5. **Professional**: Corporate-friendly colors and clean layouts

## Limitations & Workarounds

### Native SmartArt Not Supported
`python-pptx` doesn't support native PowerPoint SmartArt objects. These shape-based implementations provide similar functionality with benefits:
- ✅ Full customization control
- ✅ Consistent styling
- ✅ Compatible with all PowerPoint versions
- ❌ Not editable as SmartArt in PowerPoint (but shapes are editable)

### Matrix Requires 4 Items
The 2x2 matrix requires exactly 4 items. For 3x3 or other layouts, consider:
- Custom implementation
- Table-based approach
- Image slide with pre-created diagram

### Cycle Diagram Spacing
Optimal for 3-8 items. More items may appear crowded. Consider:
- Adjusting radius in code
- Using smaller font sizes
- Splitting into multiple cycles

## Testing

Run the comprehensive demo:

```bash
cd d:\SourceCode\GenAI\MCP\server\ppt
python shapes_demo.py
```

Options:
1. Process Flows (Chevrons)
2. Timeline
3. Diagrams (Cycle, Pyramid, Matrix)
4. Complete Presentation (All Features) ← Recommended
5. Run All Examples
6. Exit

## Output

All presentations are saved to `output/` directory as `.pptx` files, compatible with:
- Microsoft PowerPoint (Windows, Mac)
- Google Slides (import)
- LibreOffice Impress
- Apple Keynote

## Integration Example

Complete presentation with all shape features:

```python
# Create presentation
await session.call_tool("create_presentation", {
    "presentation_id": "strategic_planning"
})

# Title slide
await session.call_tool("add_title_slide", {
    "presentation_id": "strategic_planning",
    "title": "Strategic Planning 2025",
    "subtitle": "Q4 Review & Roadmap"
})

# Process flow
await session.call_tool("add_process_flow_slide", {
    "presentation_id": "strategic_planning",
    "title": "Product Development Process",
    "steps": ["Ideation", "Validation", "Development", "Launch"],
    "flow_type": "horizontal"
})

# Timeline
await session.call_tool("add_timeline_slide", {
    "presentation_id": "strategic_planning",
    "title": "2025 Milestones",
    "events": [
        {"date": "Jan", "description": "Planning"},
        {"date": "Apr", "description": "Development"},
        {"date": "Oct", "description": "Launch"}
    ]
})

# Cycle diagram
await session.call_tool("add_diagram_slide", {
    "presentation_id": "strategic_planning",
    "title": "Customer Success Framework",
    "diagram_type": "cycle",
    "items": ["Onboard", "Engage", "Support", "Retain"]
})

# Priority matrix
await session.call_tool("add_diagram_slide", {
    "presentation_id": "strategic_planning",
    "title": "Initiative Prioritization",
    "diagram_type": "matrix",
    "items": [
        "High Impact\nHigh Effort",
        "High Impact\nLow Effort",
        "Low Impact\nHigh Effort",
        "Low Impact\nLow Effort"
    ]
})

# Save
await session.call_tool("save_presentation", {
    "presentation_id": "strategic_planning",
    "output_path": "output/strategic_planning.pptx"
})
```

## Summary

The PowerPoint MCP Server now provides **15 total tools** including:
- 8 basic slide tools (title, content, charts, tables, etc.)
- 4 shape-based diagram tools (process flows, timelines, cycles, pyramids, matrices)
- 3 utility tools (create, save, list)

This makes it a comprehensive solution for automated presentation generation with professional-quality diagrams and visualizations.
