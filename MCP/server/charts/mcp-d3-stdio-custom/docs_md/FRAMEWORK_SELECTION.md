# Framework Selection Feature - D3.js vs Chart.js

## Overview

The chart generation system now supports **explicit framework selection** between D3.js and Chart.js. This gives you full control over which rendering engine is used for your charts.

## Why This Matters

Previously, the system would:
- Use D3.js templates by default
- Automatically fall back to Chart.js when D3 templates failed or data formats were incompatible
- You had no explicit control over which framework was used

Now you can:
- **Explicitly choose D3.js** for modern, interactive visualizations
- **Explicitly choose Chart.js** for simpler, more compatible charts
- **Let the system auto-select** based on chart type and data format (smart default)

## How to Use

### 1. In MCP Tool Calls

All chart tools now accept a `framework` parameter:

```python
# Use D3.js (default)
create_line_chart(
    title="Sales Trend",
    data=my_data,
    framework="d3"
)

# Use Chart.js explicitly
create_line_chart(
    title="Sales Trend",
    data=my_data,
    framework="chartjs"
)

# Let system auto-select
create_line_chart(
    title="Sales Trend",
    data=my_data,
    framework="auto"
)
```

### 2. In PMO Client Queries

When using the PMO client, you can specify the framework in your natural language query:

```text
"Create a line chart of project budgets using Chart.js"
"Generate a bar chart with D3.js showing resource allocation"
"Show me a pie chart (use D3)"
```

The LLM will extract the framework preference and pass it to the chart generation tools.

### 3. Framework Parameter Values

| Value | Behavior | Use When |
|-------|----------|----------|
| `"d3"` | Always use D3.js templates | You want modern, interactive D3 visualizations (default) |
| `"chartjs"` | Always use Chart.js renderer | You want simpler, more compatible charts |
| `"auto"` | Intelligently select based on chart type | You want the system to choose the best option |

## Framework Comparison

### D3.js
**Pros:**
- Modern, interactive visualizations
- Smooth animations and transitions
- Better for complex, custom charts
- SVG-based (crisp at any zoom level)
- More control over styling and interactions

**Cons:**
- Larger file sizes
- More complex templates
- May not work in very old browsers

### Chart.js
**Pros:**
- Simpler, more predictable rendering
- Smaller file sizes
- Better cross-browser compatibility
- Canvas-based (better for many data points)
- Easier to debug

**Cons:**
- Less interactive
- Less customizable styling
- Fixed chart types

## Default Behavior

When you **don't specify** a framework parameter:
- **Default: `"d3"`**
- The system will use D3.js templates
- If D3 rendering fails, it automatically falls back to Chart.js

This ensures backward compatibility while giving you D3 by default.

## Examples

### Example 1: D3 Line Chart (Default)

```python
# Implicitly uses D3
response = d3_session.call_tool('create_line_chart', {
    'title': 'Project Timeline',
    'data': {
        'labels': ['Jan', 'Feb', 'Mar'],
        'datasets': [{
            'label': 'Progress',
            'data': [30, 60, 85]
        }]
    }
})
```

Result: **D3.js line chart** with smooth curves and hover interactions

### Example 2: Chart.js Bar Chart (Explicit)

```python
# Explicitly request Chart.js
response = d3_session.call_tool('create_bar_chart', {
    'title': 'Budget by Project',
    'data': {
        'labels': ['Alpha', 'Beta', 'Gamma'],
        'datasets': [{
            'label': 'Budget',
            'data': [50000, 75000, 60000]
        }]
    },
    'framework': 'chartjs'
})
```

Result: **Chart.js bar chart** with simpler rendering

### Example 3: Auto-Select Framework

```python
# Let system choose
response = d3_session.call_tool('render_chart_from_dataset', {
    'title': 'Resource Allocation',
    'data': my_complex_data,
    'chart_type': 'grouped_bar',
    'framework': 'auto'
})
```

Result: System chooses **D3.js grouped bar** (optimal for this chart type)

## Technical Details

### Implementation

The framework selection is implemented in three layers:

1. **MCP Server (`d3_chart_mcp.py`)**
   - All `@mcp.tool()` functions accept `framework` parameter
   - Default value: `"d3"`
   - Passes framework to API server

2. **API Server (`d3_chart_api_server.py`)**
   - `handle_template()` extracts framework from args
   - Routes to D3 templates or Chart.js renderer based on framework
   - Validates framework value (must be 'd3', 'chartjs', or 'auto')

3. **Chart Renderer (`chart_renderer.py`)**
   - Used when `framework="chartjs"` or as fallback
   - Handles data normalization and Chart.js HTML generation
   - No changes needed for framework feature

### Validation

The system validates the framework parameter:
- Valid values: `'d3'`, `'chartjs'`, `'auto'`
- Invalid values default to `'d3'`
- Case-insensitive (e.g., `'D3'`, `'ChartJS'` work)

### File Naming

Generated HTML files are prefixed with framework info:
- D3 charts: `packed_20251121_123456_abc123.html`
- Chart.js charts: `chartjs_render_20251121_123456_def456.html`
- Auto-selected: Uses framework that was chosen

## Testing

Run the test suite to verify framework selection:

```powershell
cd D:\SourceCode\GenAI\MCP\server\charts\mcp-d3-stdio-custom
python test_framework_selection.py
```

Tests verify:
- ✅ Explicit `framework='d3'` uses D3.js
- ✅ Explicit `framework='chartjs'` uses Chart.js
- ✅ `framework='auto'` intelligently selects
- ✅ Default (no framework) uses D3.js
- ✅ Line charts work with both frameworks
- ✅ Bar charts work with both frameworks

## Migration Guide

### For Existing Code

No changes required! Your existing code will continue to work:

```python
# This still works - uses D3 by default
create_line_chart(title="Sales", data=my_data)
```

### To Explicitly Use Chart.js

Add `framework='chartjs'` parameter:

```python
# Change from implicit D3
create_line_chart(title="Sales", data=my_data)

# To explicit Chart.js
create_line_chart(title="Sales", data=my_data, framework='chartjs')
```

### To Let System Auto-Select

Use `framework='auto'`:

```python
create_line_chart(title="Sales", data=my_data, framework='auto')
```

## Recommendations

### When to Use D3.js (Default)
- Interactive dashboards
- Complex visualizations (network graphs, hierarchies)
- When you need smooth animations
- When SVG quality matters
- Modern browser environments

### When to Use Chart.js
- Simple statistical charts (line, bar, pie)
- When you need maximum compatibility
- When file size matters
- When you want predictable rendering
- Legacy browser support needed

### When to Use Auto
- You're not sure which is better
- You want the system to optimize
- You're generating many different chart types

## Summary

✅ **Default framework: D3.js** - Modern, interactive visualizations by default  
✅ **Explicit Chart.js available** - Use `framework='chartjs'` when needed  
✅ **Smart auto-selection** - Use `framework='auto'` for intelligent routing  
✅ **Backward compatible** - Existing code continues to work  
✅ **Fully tested** - Test suite verifies all combinations  
✅ **Clean implementation** - Simple parameter addition, no breaking changes

---

**Created:** November 21, 2025  
**Author:** AI Code Assistant  
**Test Status:** ✅ All 5 tests passing
