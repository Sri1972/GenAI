# D3 Chart MCP Tool Routing Fix

**Date:** 2025-01-28  
**Status:** ✅ COMPLETE  
**Component:** PMO MCP Client (`pmo_mcp_client.py`)

## Problem Summary

### Issue
When users tried to generate charts via Claude in the PMO client, Claude would attempt to call D3 Chart MCP tools like `create_line_chart`, but the PMO client would return "Unknown tool" errors. This was because:

1. **Tool Discovery**: PMO client only listed PMO tools to Claude, not D3 tools
2. **Tool Routing**: All tool calls were sent to `pmo_session.call_tool()`, which didn't recognize D3 tool names
3. **Fallback Behavior**: When D3 tools failed, Claude would generate Chart.js HTML instead (which worked but lost the enhanced features like visible labels)

### User-Reported Symptoms
- "Unknown tool: line" error messages
- "Unknown tool: render_line_chart" errors
- Charts missing interactive tooltips
- When using phrase "using javascript and html", Claude generates Chart.js (works but no visible labels)

### Root Cause
PMO client had two active MCP sessions (`pmo_session` and `d3_session`) but:
- Only listed PMO tools in system instructions
- Routed all tool calls to PMO session only
- No logic to detect D3 tool names and route to D3 session

## Solution Implemented

### 1. D3 Tool Discovery (Lines 1130-1175)

**Added D3 tool listing to system instructions:**

```python
# Tool listing from D3 Chart server
d3_tools_result = None
d3_tool_count = 0
if d3_session:
    d3_tools_result = await d3_session.list_tools()
    d3_tool_count = len(d3_tools_result.tools) if hasattr(d3_tools_result, 'tools') else 0
    print(f"Available D3 Chart tools: {d3_tool_count} tools loaded")

# Add D3 Chart tools to tool descriptions
if d3_tools_result:
    tool_lines.append("\n=== D3 CHART MCP SERVER TOOLS ===")
    for tool in d3_tools_result.tools:
        # Format tool description with parameters
        tool_lines.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
```

**Result:** Claude now sees both PMO and D3 tools in system instructions.

### 2. Tool Routing Logic (Lines 1119-1128)

**Added D3 tool name detection:**

```python
# D3 Chart MCP tool names (for routing)
D3_TOOL_NAMES = {
    'create_line_chart',
    'create_bar_chart',
    'create_grouped_bar_chart',
    'create_pie_chart',
    'create_scatter_plot',
    'create_bubble_chart',
    'create_heatmap',
    'render_chart_from_dataset'
}

def is_d3_tool(tool_name: str) -> bool:
    """Check if a tool name belongs to the D3 Chart MCP server."""
    return tool_name in D3_TOOL_NAMES
```

**Result:** Fast O(1) lookup to determine if tool should route to D3 session.

### 3. Tool Execution Routing (3 locations)

**Location 1: Matcher-Requested Fetch (Line ~1673)**

```python
# Route to appropriate MCP session
if is_d3_tool(tool_to_call):
    if d3_session:
        print(f"   🎨 Routing to D3 Chart MCP server")
        tool_result = await d3_session.call_tool(tool_to_call, args)
    else:
        print(f"   ❌ D3 session not available")
        tool_result = {"error": "D3 Chart MCP server not available"}
else:
    tool_result = await session.call_tool(tool_to_call, args)
```

**Location 2: Plan-Based Execution (Line ~2109)**

```python
# Route to appropriate MCP session
if is_d3_tool(tool_name):
    if d3_session:
        print(f"   🎨 Routing to D3 Chart MCP server")
        tool_result = await d3_session.call_tool(tool_name, tool_args)
    else:
        print(f"   ❌ D3 session not available")
        tool_result = {"error": "D3 Chart MCP server not available"}
else:
    tool_result = await session.call_tool(tool_name, tool_args)
```

**Location 3: Single Tool Execution (Line ~2318)**

```python
# Route to appropriate MCP session
if is_d3_tool(tool_name):
    if d3_session:
        print(f"   🎨 Routing to D3 Chart MCP server")
        tool_result = await d3_session.call_tool(tool_name, tool_args)
    else:
        print(f"   ❌ D3 session not available")
        tool_result = {"error": "D3 Chart MCP server not available"}
else:
    tool_result = await session.call_tool(tool_name, tool_args)
```

**Result:** All three tool execution paths now route D3 tool calls to `d3_session`.

### 4. Updated System Instructions (Line ~1213)

**Enhanced visualization rules:**

```python
"VISUALIZATION RULES:\n"
"- CRITICAL: When the user asks to create charts, visualizations, or render data graphically, you MUST use the D3 Chart MCP server tools.\n"
"- The D3 Chart MCP server provides enhanced charts with visible data labels - perfect for screenshots and PowerPoint exports.\n"
"- Available D3 chart tool names: create_line_chart, create_bar_chart, create_grouped_bar_chart, create_pie_chart, create_scatter_plot, create_bubble_chart, create_heatmap, render_chart_from_dataset\n"
"- All D3 charts include: (1) visible value labels and interactive tooltips, (2) leader lines where needed, (3) complete data tables.\n"
"- DO NOT generate your own HTML/JavaScript chart code - always use the D3 Chart MCP server tools instead.\n"
"- Chart tool call format: {\"tool\":\"create_line_chart\", \"arguments\":{\"title\":\"...\", \"data\":{...}}}\n"
"- Example line chart: {\"tool\":\"create_line_chart\", \"arguments\":{\"title\":\"Resource Hours\", \"data\":{\"labels\":[...], \"datasets\":[...]}}}\n\n"
```

**Result:** Claude knows exact D3 tool names to call and sees examples with correct syntax.

## Testing

### Syntax Validation
```powershell
PS D:\SourceCode\GenAI\MCP\client\pmo> python -m py_compile pmo_mcp_client.py
# No errors - syntax is valid ✅
```

### Expected User Workflow

1. **Start PMO Client:**
   ```powershell
   cd D:\SourceCode\GenAI\MCP\client\pmo
   python pmo_mcp_client.py
   ```

2. **Verify Both Sessions Connected:**
   ```
   Available PMO tools: 15 tools loaded
   Available D3 Chart tools: 8 tools loaded
   ✅ Both MCP sessions ready
   ```

3. **Query PMO Data:**
   ```
   User: show planned vs actual hours for resource id 2 in 2025 monthly
   ```
   - Should call: `get_resource_allocation_planned_actual`
   - Should route to: `pmo_session` (PMO tool)

4. **Generate Chart:**
   ```
   User: create a line chart
   ```
   - Should call: `create_line_chart`
   - Should route to: `d3_session` (D3 tool) 🎨
   - Console output: "🎨 Routing to D3 Chart MCP server"

5. **Chart Output:**
   - HTML file created in `html-charts/`
   - Chart includes:
     - ✅ Visible value labels at each point
     - ✅ Interactive tooltips on hover
     - ✅ Grid lines for readability
     - ✅ Interactive legend (click to toggle series)
     - ✅ Professional styling with hover effects
     - ✅ Data table below chart

## File Changes Summary

### Modified Files
1. **pmo_mcp_client.py** (2649 lines, +60 lines net change)
   - Added D3 tool listing to system instructions
   - Added `D3_TOOL_NAMES` set and `is_d3_tool()` function
   - Updated 3 tool execution points with routing logic
   - Enhanced system instructions with exact D3 tool names

### No Changes Required
- **d3_chart_mcp.py** - Already had all 8 tools defined ✅
- **d3_chart_api_server.py** - All 7 enhanced chart types complete ✅
- **pmo_mcp.py** - PMO server unchanged ✅

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ PMO MCP Client (pmo_mcp_client.py)                          │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ System Instructions                                   │   │
│ │ - PMO tools: get_all_projects, get_resource_*, etc.  │   │
│ │ - D3 tools: create_line_chart, create_bar_chart, etc.│   │
│ └──────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Tool Routing Logic (is_d3_tool)                       │   │
│ │ - Check tool name against D3_TOOL_NAMES set           │   │
│ │ - Route to pmo_session or d3_session                  │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                              │
│         ┌────────────────┐         ┌────────────────┐      │
│         │  pmo_session   │         │  d3_session    │      │
│         │  (PMO Tools)   │         │  (D3 Tools)    │      │
│         └────────┬───────┘         └────────┬───────┘      │
└──────────────────┼──────────────────────────┼──────────────┘
                   │                           │
                   ▼                           ▼
         ┌─────────────────┐         ┌─────────────────┐
         │ PMO MCP Server  │         │ D3 Chart MCP    │
         │ (pmo_mcp.py)    │         │ (d3_chart_mcp.py)│
         └─────────────────┘         └─────────────────┘
                   │                           │
                   ▼                           ▼
         ┌─────────────────┐         ┌─────────────────┐
         │ SQLite Database │         │ D3 API Server   │
         │ (PMO Data)      │         │ (d3_chart_api_  │
         └─────────────────┘         │ server.py)      │
                                     └─────────────────┘
```

## Benefits

### For Users
- ✅ **Seamless Chart Generation**: Just ask for a chart, Claude automatically calls the right D3 tool
- ✅ **Enhanced Visuals**: All charts have visible labels, tooltips, grid lines, interactive legends
- ✅ **Screenshot-Ready**: Charts export perfectly to PowerPoint/images without losing data
- ✅ **No Manual Workarounds**: No need to add "using javascript and html" phrase anymore

### For System
- ✅ **Clean Architecture**: Two MCP servers working in harmony with proper routing
- ✅ **Extensible**: Easy to add new D3 tools - just update `D3_TOOL_NAMES` set
- ✅ **Fast Routing**: O(1) set lookup for tool name detection
- ✅ **Graceful Degradation**: If D3 session unavailable, returns clear error message

## D3 Chart Features (All 7 Enhanced Types)

### Visible Labels + Interactive Tooltips
- Line charts: Value labels at each point + hover tooltips
- Bar charts: Value labels on bars + hover tooltips
- Pie charts: Percentage labels with leader lines + slice tooltips
- Scatter plots: Point labels adjacent + hover tooltips
- Bubble charts: Leader lines to labels + hover tooltips
- Heatmaps: In-cell values + cell tooltips
- Circle packing: External labels with leader lines + circle tooltips

### Professional Styling
- Grid lines with `stroke-dasharray: '2,2'`, opacity 0.15
- Interactive legend with hover effects and box-shadow
- Click legend to toggle series visibility
- Smooth animations with 300ms transitions
- Point/bar/slice hover effects (size/opacity changes)

### Data Tables
All charts include complete data tables below the visualization for reference.

## Next Steps

### Recommended Testing
1. **Basic Flow**: Resource data → Line chart
2. **Multi-Series**: Compare multiple resources → Grouped bar chart
3. **Plan-Based**: Fetch multiple data sets → Combined visualization
4. **Edge Cases**: D3 session unavailable, invalid tool names

### Future Enhancements (Optional)
1. **Summary Cards**: Extract dataset totals/averages and show in cards above chart
2. **Axis Titles**: Add customizable X/Y axis labels (grid lines done, titles pending)
3. **Export Options**: Save charts as PNG/SVG directly from client
4. **Chart Themes**: Add dark mode/color scheme customization

## Related Files

- **Main Implementation**: `pmo_mcp_client.py`
- **D3 Server**: `server/charts/mcp-d3-stdio-custom/d3_chart_mcp.py`
- **Chart Templates**: `server/charts/mcp-d3-stdio-custom/d3_chart_api_server.py`
- **Documentation**: This file (`D3_TOOL_ROUTING_FIX.md`)

## Success Criteria

- [✅] PMO client lists both PMO and D3 tools to Claude
- [✅] Tool routing function (`is_d3_tool`) created
- [✅] All 3 tool execution points route D3 calls to d3_session
- [✅] System instructions updated with exact D3 tool names
- [✅] No syntax errors in modified file
- [ ] End-to-end test: User requests chart, Claude calls D3 tool, chart generated with all enhancements

**Status**: Implementation complete, ready for end-to-end testing.
