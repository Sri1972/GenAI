# PowerPoint Integration Guide for PMO Client

## Overview

The PMO MCP Client now integrates with the PowerPoint MCP Server to automatically generate professional presentations from PMO data. This integration allows you to create comprehensive PowerPoint presentations with data, charts, analysis, and insights.

## Architecture

```
┌─────────────────┐
│   PMO Client    │  (Natural Language Interface)
└────────┬────────┘
         │
         ├──────────┬──────────────────┬───────────────────┐
         │          │                  │                   │
    ┌────▼────┐ ┌───▼──────┐   ┌──────▼────────┐   ┌─────▼─────┐
    │   PMO   │ │  Charts  │   │  PowerPoint   │   │    LLM    │
    │  Server │ │  Server  │   │    Server     │   │  (Bedrock)│
    └────┬────┘ └───┬──────┘   └──────┬────────┘   └───────────┘
         │          │                  │
    ┌────▼────┐ ┌───▼──────────┐ ┌────▼─────────┐
    │ Project │ │ D3.js/Chart. │ │ python-pptx  │
    │  Data   │ │ js + PNG     │ │   Library    │
    └─────────┘ └──────────────┘ └──────────────┘
```

## Features

### 1. **Automatic Chart to PowerPoint Pipeline**
- Charts are generated with auto-PNG creation (194 KB html2canvas library)
- PNG files are automatically available for insertion into slides
- No manual screenshot or conversion needed

### 2. **Professional Slide Layouts**
- Title slides with presentation name and date
- Executive summary with key metrics
- Data visualization slides with PNG chart images
- Analysis slides with bullet points and insights
- Tables for detailed data breakdowns
- Two-column layouts for comparisons
- Summary/conclusion slides

### 3. **Three-Server Integration**
- **PMO Server**: Fetches project, resource, and portfolio data
- **Chart Server**: Generates D3.js/Chart.js visualizations + PNG exports
- **PPT Server**: Creates PowerPoint presentations with slides

### 4. **Intelligent Workflow**
The LLM automatically orchestrates multi-step operations:
1. Fetch PMO data
2. Generate charts (HTML + PNG)
3. Extract PNG paths
4. Create presentation
5. Add slides with data, charts, and analysis
6. Save presentation

## Usage

### Simple Example

```
Query: Create a PowerPoint presentation showing Q4 project performance
```

The client will:
1. Fetch Q4 project data from PMO server
2. Generate cost/hours charts (PNG files created automatically)
3. Create presentation with:
   - Title slide: "Q4 Project Performance Report"
   - Executive summary slide with key metrics
   - Chart slides with PNG images
   - Analysis slides with insights
   - Summary slide
4. Save to: `D:\SourceCode\GenAI\MCP\client\pmo\presentations\`

### Advanced Example

```
Query: Create a comprehensive PMO presentation with:
- Portfolio overview by product line
- Resource capacity analysis
- Project status breakdown
- Cost and hours trends
- Recommendations
```

The LLM will create a multi-step plan:
1. Get all projects grouped by portfolio
2. Get resource allocation data
3. Generate 4-5 charts (each with auto-PNG)
4. Create presentation with 10+ slides
5. Add title, summary, chart, analysis, and conclusion slides
6. Save presentation

## Output Locations

### Charts (PNG + HTML)
```
D:\SourceCode\GenAI\MCP\client\pmo\html-charts\
├── project_costs_bar_d3_20251124_143022.html
├── project_costs_bar_d3_20251124_143022.png      ← Auto-generated
├── resource_capacity_line_d3_20251124_143045.html
└── resource_capacity_line_d3_20251124_143045.png ← Auto-generated
```

### Presentations
```
D:\SourceCode\GenAI\MCP\client\pmo\presentations\
├── q4_project_performance_20251124.pptx
├── portfolio_analysis_20251124.pptx
└── executive_summary_20251124.pptx
```

## PowerPoint Tools Available

### Presentation Management
- `create_presentation` - Create new presentation
- `list_presentations` - List active presentations in memory
- `save_presentation` - Save presentation to file

### Slide Types
- `add_title_slide` - Title and subtitle
- `add_content_slide` - Title with bullet points
- `add_two_column_slide` - Two columns of bullet points
- `add_image_slide` - Chart PNG images (from Chart server)
- `add_chart_slide` - Native PowerPoint charts
- `add_table_slide` - Data tables
- `add_process_flow_slide` - Chevron/arrow process flows
- `add_timeline_slide` - Timeline with events
- `add_diagram_slide` - Cycle, pyramid, matrix diagrams
- `add_shape_slide` - Custom shapes and org charts
- `add_gantt_chart_slide` - Gantt chart timelines

## Workflow Details

### Step 1: Data Fetching
```json
{
  "tool": "get_all_projects",
  "arguments": {}
}
```

### Step 2: Chart Generation (Auto-PNG)
```json
{
  "tool": "render_chart_from_dataset",
  "arguments": {
    "title": "Project Costs by Portfolio",
    "data": {
      "labels": ["Market & Sell", "Auto Insights", "Plan & Build"],
      "datasets": [{
        "label": "Costs",
        "data": [150000, 200000, 80000]
      }]
    },
    "chart_type": "bar",
    "framework": "d3"
  }
}
```
Output: HTML + **PNG file automatically created**

### Step 3: Create Presentation
```json
{
  "tool": "create_presentation",
  "arguments": {
    "presentation_id": "q4_report"
  }
}
```

### Step 4: Add Title Slide
```json
{
  "tool": "add_title_slide",
  "arguments": {
    "presentation_id": "q4_report",
    "title": "Q4 Project Performance Report",
    "subtitle": "November 2025"
  }
}
```

### Step 5: Add Chart Slide with PNG
```json
{
  "tool": "add_image_slide",
  "arguments": {
    "presentation_id": "q4_report",
    "title": "Project Costs by Portfolio",
    "image_path": "D:\\SourceCode\\GenAI\\MCP\\client\\pmo\\html-charts\\project_costs_bar_d3_20251124_143022.png"
  }
}
```

### Step 6: Add Analysis Slide
```json
{
  "tool": "add_content_slide",
  "arguments": {
    "presentation_id": "q4_report",
    "title": "Key Insights",
    "content": [
      "Auto Insights portfolio shows highest investment at $200K",
      "Market & Sell portfolio accounts for 35% of total costs",
      "Plan & Build remains lean at $80K",
      "Overall trend indicates strategic focus on AI initiatives"
    ]
  }
}
```

### Step 7: Save Presentation
```json
{
  "tool": "save_presentation",
  "arguments": {
    "presentation_id": "q4_report",
    "output_path": "D:\\SourceCode\\GenAI\\MCP\\client\\pmo\\presentations\\q4_report_20251124.pptx"
  }
}
```

## Best Practices

### 1. **Always Generate Charts First**
Charts must be created before PPT generation to ensure PNG files exist:
```
Step 1: Fetch data
Step 2: Generate charts (PNG created automatically)
Step 3: Create PPT with PNG paths
```

### 2. **Use Descriptive Filenames**
```
Good: presentations/q4_portfolio_analysis_20251124.pptx
Bad:  presentations/output.pptx
```

### 3. **Structure Presentations Professionally**
- Title slide
- Executive summary (key metrics)
- Detailed slides (charts + analysis)
- Data tables (supporting detail)
- Summary/recommendations

### 4. **Leverage Chart Auto-PNG**
The chart server automatically creates PNG alongside HTML:
- ✅ No manual screenshots needed
- ✅ High resolution (1400x900 @ 2x scale)
- ✅ Same filename as HTML
- ✅ Ready for PPT insertion

### 5. **Multi-Step Plans**
For complex presentations, use multi-step plans:
```json
{
  "plan": [
    {"id": "s1", "tool": "get_all_projects", "arguments": {}},
    {"id": "s2", "tool": "render_chart_from_dataset", "arguments": {...}},
    {"id": "s3", "tool": "create_presentation", "arguments": {...}},
    {"id": "s4", "tool": "add_title_slide", "arguments": {...}},
    {"id": "s5", "tool": "add_image_slide", "arguments": {...}},
    {"id": "s6", "tool": "save_presentation", "arguments": {...}}
  ]
}
```

## Example Queries

### Portfolio Analysis
```
Create a PowerPoint presentation analyzing all portfolios with:
- Title slide
- Portfolio breakdown chart
- Resource allocation by portfolio
- Project status summary
- Recommendations
```

### Resource Utilization
```
Generate a presentation showing resource capacity and utilization:
- Executive summary with capacity metrics
- Capacity vs planned hours chart
- Available capacity chart
- Resource allocation table
- Recommendations for balancing workload
```

### Executive Dashboard
```
Create an executive dashboard presentation with:
- Title slide: "PMO Executive Dashboard - November 2025"
- Key metrics: total projects, total hours, total costs
- Portfolio cost breakdown (pie chart)
- Monthly hours trend (line chart)
- Project status distribution (bar chart)
- Resource capacity summary (table)
- Strategic recommendations
```

## Troubleshooting

### Issue: "PowerPoint server not available"
**Solution**: Check that PPT server path is correct:
```python
D:\SourceCode\GenAI\MCP\server\ppt\ppt_mcp_server.py
```

### Issue: "Image file not found"
**Solution**: Ensure chart was generated first with auto-PNG enabled:
```python
# Charts automatically create PNG files
# Check html-charts folder for .png files
```

### Issue: "Presentation not saving"
**Solution**: Verify output directory exists:
```powershell
New-Item -ItemType Directory -Force -Path "D:\SourceCode\GenAI\MCP\client\pmo\presentations"
```

### Issue: "Chart PNG quality low"
**Solution**: Charts are generated at high resolution automatically:
- 1400x900px viewport
- 2x scale (2800x1800 effective)
- PNG compression optimized for presentations

## Technical Details

### Server Initialization Order
```
1. PMO Server    (required) - Data source
2. Chart Server  (optional) - Visualization + PNG
3. PPT Server    (optional) - Presentation generation
```

### Tool Routing Logic
```python
# PPT tools checked first
is_ppt_tool = tool_name in ['create_presentation', 'add_title_slide', ...]

# Then chart tools
is_chart_tool = tool_name.startswith('render_chart')

# Else PMO tools
```

### PNG File Detection
```python
# Charts saved with descriptive filenames:
# {title}_{chart_type}_{framework}_{timestamp}.png

# Example:
# project_costs_bar_d3_20251124_143022.png
```

### Presentation ID Management
```python
# Use descriptive, unique IDs:
presentation_id = "q4_report_2025"

# Avoid generic IDs:
presentation_id = "my_presentation"  # Bad - may conflict
```

## Performance

### Chart Generation + PPT Creation
- **Fetch data**: ~100-500ms
- **Generate chart + PNG**: ~2-3 seconds (Playwright screenshot)
- **Create PPT slide**: ~50-100ms
- **Total for 5-slide presentation**: ~15-20 seconds

### Optimization Tips
1. Fetch all data in one call when possible
2. Generate charts in parallel (multi-step plan)
3. Reuse data from conversation history
4. Use cached PNG files if charts already exist

## Future Enhancements

### Planned Features
- [ ] Template-based presentations
- [ ] Custom themes and branding
- [ ] Animation and transitions
- [ ] Speaker notes generation
- [ ] Batch presentation generation
- [ ] PowerPoint → PDF export
- [ ] Integration with SharePoint/Teams

### Potential Improvements
- Smart chart selection (LLM chooses best chart type)
- Automatic slide layout optimization
- AI-generated speaker notes
- Multi-language support
- Real-time collaboration

## Examples in Action

### Q4 Performance Report (Complete Workflow)
```
User: Create a Q4 performance report PowerPoint

LLM Output:
{
  "plan": [
    {"id": "data", "tool": "get_all_projects", "arguments": {}},
    {
      "id": "cost_chart",
      "tool": "render_chart_from_dataset",
      "arguments": {
        "title": "Q4 Project Costs",
        "data": {"labels": [...], "datasets": [...]},
        "chart_type": "bar"
      }
    },
    {"id": "ppt", "tool": "create_presentation", "arguments": {"presentation_id": "q4_report"}},
    {
      "id": "title",
      "tool": "add_title_slide",
      "arguments": {
        "presentation_id": "q4_report",
        "title": "Q4 Performance Report",
        "subtitle": "November 2025"
      }
    },
    {
      "id": "chart_slide",
      "tool": "add_image_slide",
      "arguments": {
        "presentation_id": "q4_report",
        "title": "Project Costs by Portfolio",
        "image_path": "D:\\...\\q4_project_costs_bar_d3_20251124_143022.png"
      }
    },
    {
      "id": "save",
      "tool": "save_presentation",
      "arguments": {
        "presentation_id": "q4_report",
        "output_path": "D:\\...\\presentations\\q4_report_20251124.pptx"
      }
    }
  ]
}
```

Result: Professional 5-slide PowerPoint presentation in ~20 seconds! 🎯

## Summary

The PowerPoint integration enables:
- ✅ **Automatic** presentation generation from PMO data
- ✅ **Professional** layouts and formatting
- ✅ **Integrated** charts with auto-PNG generation
- ✅ **Intelligent** multi-step orchestration
- ✅ **Fast** end-to-end workflow (~20 seconds for 5 slides)

Perfect for executive briefings, status reports, portfolio reviews, and strategic planning sessions!

---

**Last Updated**: November 24, 2025  
**Version**: 1.0.0  
**Integration**: PMO + Charts + PowerPoint MCP Servers
