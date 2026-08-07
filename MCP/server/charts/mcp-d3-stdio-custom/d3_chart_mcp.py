#!/usr/bin/env python3
"""
================================================================================
D3 Chart Generation MCP Server (FastMCP Implementation)
================================================================================

PURPOSE:
    This is the MAIN MCP SERVER that provides a proper Model Context Protocol
    (MCP) interface using the FastMCP framework. It serves as the entry point
    for MCP clients (like Claude Desktop) to generate D3.js charts.

ARCHITECTURE ROLE:
    - **Layer 1 (Top)**: MCP Server Interface
    - Exposes MCP tools and resources following the MCP specification
    - Handles tool registration, parameter validation, and response formatting
    - Provides documentation resources about available chart types

DEPENDENCIES:
    1. **d3_chart_api_server.py** (Layer 2 - Backend)
       - This server WRAPS the d3_chart_api_server.py as its backend
       - Communicates via subprocess + STDIO (JSON-RPC style)
       - Translates MCP tool calls into d3_chart_api_server requests
       - Receives HTML chart generation results
    
    2. **chart_renderer.py** (Layer 3 - Used by API Server)
       - Indirectly used through d3_chart_api_server.py
       - Not directly imported or called by this file
       - Handles Chart.js fallback rendering when D3 templates unavailable

KEY FUNCTIONS:
    - call_d3_api(): Bridge function that spawns d3_chart_api_server.py
                     process and sends/receives JSON requests
    - @mcp.tool() decorated functions: 9 chart type tools exposed to MCP clients
    - @mcp.resource() decorated functions: Documentation resources

COMMUNICATION FLOW:
    MCP Client -> d3_chart_mcp.py (this file) -> d3_chart_api_server.py -> HTML Chart
    
    1. MCP client calls tool (e.g., create_line_chart)
    2. This server validates parameters and formats request
    3. Spawns d3_chart_api_server.py subprocess via call_d3_api()
    4. API server generates HTML using D3 templates or Chart.js fallback
    5. Returns file path and success/error status to MCP client

CHART TYPES SUPPORTED:
    - Line, Bar, Grouped Bar, Pie/Donut
    - Scatter, Bubble, Heatmap
    - Stacked Bar, Horizontal Bar
    - Universal render_chart_from_dataset() for intelligent routing

OUTPUT:
    All charts saved to: ./html-charts/
    Returns: Absolute file path to generated HTML file

USAGE:
    Start server: python d3_chart_mcp.py
    Configure in Claude Desktop's claude_desktop_config.json
    Or use with any MCP-compatible client

================================================================================
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, TextResourceContents
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import asyncio
import tempfile

# Initialize MCP server
mcp = FastMCP("D3-Charts")

# Configuration
CHARTS_DIR = Path(__file__).resolve().parent
# Path to the existing D3 API server (STDIO JSON-RPC, not true MCP)
D3_API_SERVER = CHARTS_DIR / 'd3_chart_api_server.py'

def call_d3_api(tool_name: str, arguments: dict, timeout: int = 30) -> dict:
    """
    Call the D3 chart API server with the given tool and arguments.
    
    Args:
        tool_name (str): Name of the chart tool to call
        arguments (dict): Arguments to pass to the chart tool
        timeout (int): Timeout in seconds for the API call
    
    Returns:
        dict: Response from the D3 API server with status, path, and HTML content
    """
    if not D3_API_SERVER.exists():
        return {
            'status': 'error', 
            'message': f'D3 API server not found at {D3_API_SERVER}'
        }
    
    # Prepare the API call payload
    api_payload = {
        'tool': tool_name,
        'arguments': arguments
    }
    
    try:
        # Start the D3 API server process
        proc = subprocess.Popen(
            [sys.executable, str(D3_API_SERVER)], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        # Send the request and get response
        input_json = json.dumps(api_payload)
        stdout, stderr = proc.communicate(input=input_json + '\n', timeout=timeout)
        
        if proc.returncode != 0:
            return {
                'status': 'error',
                'message': f'D3 API server returned exit code {proc.returncode}: {stderr.strip()[:500]}',
                'stderr': stderr
            }
        
        # Parse the response
        if stdout.strip():
            try:
                response = json.loads(stdout.strip())
                return response
            except json.JSONDecodeError as e:
                return {
                    'status': 'error',
                    'message': f'Failed to parse API response: {e}',
                    'raw_output': stdout
                }
        else:
            return {
                'status': 'error',
                'message': 'No output from D3 API server',
                'stderr': stderr
            }
            
    except subprocess.TimeoutExpired:
        proc.kill()
        return {
            'status': 'error',
            'message': f'D3 API server timed out after {timeout} seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error calling D3 API server: {str(e)}'
        }

# ================================================================================
# CHART GENERATION TOOLS
# ================================================================================

@mcp.tool()
def create_line_chart(
    title: str = "Line Chart",
    data: Union[Dict, List] = None,
    labels: Optional[List[str]] = None,
    datasets: Optional[List[Dict]] = None,
    framework: str = "d3"
) -> str:
    """
    Create an interactive line chart.
    
    Args:
        title: Chart title
        data: Chart data in Chart.js format {labels: [], datasets: []} or raw data
        labels: X-axis labels (if data not provided in Chart.js format)
        datasets: Data series (if data not provided in Chart.js format)
        framework: Rendering framework - 'd3' (default), 'chartjs', or 'auto'
    
    Returns:
        Path to the generated HTML file containing the interactive chart
    """
    # Normalize data format
    if data is None and labels is not None and datasets is not None:
        chart_data = {'labels': labels, 'datasets': datasets}
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    arguments = {
        'title': title,
        'data': chart_data,
        'framework': framework
    }
    
    response = call_d3_api('line', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Line chart created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating line chart: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_bar_chart(
    title: str = "Bar Chart",
    data: Union[Dict, List] = None,
    labels: Optional[List[str]] = None,
    datasets: Optional[List[Dict]] = None,
    stacked: bool = False,
    framework: str = "d3"
) -> str:
    """
    Create an interactive bar chart.
    
    Args:
        title: Chart title
        data: Chart data in Chart.js format {labels: [], datasets: []} or raw data
        labels: X-axis labels (if data not provided in Chart.js format)
        datasets: Data series (if data not provided in Chart.js format)  
        stacked: Whether to create a stacked bar chart
        framework: Rendering framework - 'd3' (default), 'chartjs', or 'auto'
    
    Returns:
        Path to the generated HTML file containing the interactive chart
    """
    # Normalize data format
    if data is None and labels is not None and datasets is not None:
        chart_data = {'labels': labels, 'datasets': datasets}
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    tool_name = 'stacked_bar' if stacked else 'bar'
    arguments = {
        'title': title,
        'data': chart_data,
        'framework': framework
    }
    
    response = call_d3_api(tool_name, arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Bar chart created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating bar chart: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_grouped_bar_chart(
    title: str = "Grouped Bar Chart",
    data: Union[Dict, List] = None,
    labels: Optional[List[str]] = None,
    datasets: Optional[List[Dict]] = None,
    framework: str = "d3"
) -> str:
    """
    Create an interactive grouped bar chart with legend and tooltips.
    
    Args:
        title: Chart title
        data: Chart data in Chart.js format {labels: [], datasets: []} or raw data
        labels: Month/category labels (if data not provided in Chart.js format)
        datasets: Data series with project names (if data not provided in Chart.js format)
        framework: Rendering framework - 'd3' (default), 'chartjs', or 'auto'
    
    Returns:
        Path to the generated HTML file containing the interactive chart with legend and tooltips
    """
    # Normalize data format
    if data is None and labels is not None and datasets is not None:
        chart_data = {'labels': labels, 'datasets': datasets}
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    arguments = {
        'title': title,
        'data': chart_data,
        'framework': framework
    }
    
    response = call_d3_api('grouped_bar', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Grouped bar chart created with legend and tooltips: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating grouped bar chart: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_pie_chart(
    title: str = "Pie Chart", 
    data: Union[Dict, List] = None,
    labels: Optional[List[str]] = None,
    values: Optional[List[float]] = None,
    donut: bool = False
) -> str:
    """
    Create an interactive D3.js pie or donut chart.
    
    Args:
        title: Chart title
        data: Chart data as list of {label, value} objects or Chart.js format
        labels: Category labels (if data not provided as objects)
        values: Values for each category (if data not provided as objects)
        donut: Whether to create a donut chart (with inner radius)
    
    Returns:
        Path to the generated HTML file containing the interactive chart
    """
    # Normalize data format
    if data is None and labels is not None and values is not None:
        chart_data = [{'label': l, 'value': v} for l, v in zip(labels, values)]
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        chart_data = data
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    tool_name = 'donut' if donut else 'pie'
    arguments = {
        'title': title,
        'data': chart_data
    }
    
    response = call_d3_api(tool_name, arguments)
    
    if response.get('status') == 'ok':
        chart_type = "donut" if donut else "pie"
        return f"[DONE] {chart_type.capitalize()} chart created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating pie chart: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_scatter_plot(
    title: str = "Scatter Plot",
    data: Union[Dict, List] = None,
    points: Optional[List[Dict]] = None
) -> str:
    """
    Create an interactive D3.js scatter plot.
    
    Args:
        title: Chart title
        data: Chart data with points array or direct points data
        points: List of point objects with x, y, and optional r, color, label properties
    
    Returns:
        Path to the generated HTML file containing the interactive scatter plot
    """
    # Normalize data format
    if data is None and points is not None:
        chart_data = {'points': points}
    elif isinstance(data, dict):
        chart_data = data
    elif isinstance(data, list):
        chart_data = {'points': data}
    else:
        chart_data = {'points': []} if data is None else {'data': data}
    
    arguments = {
        'title': title,
        'data': chart_data
    }
    
    response = call_d3_api('scatter', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Scatter plot created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating scatter plot: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_bubble_chart(
    title: str = "Bubble Chart",
    data: Union[Dict, List] = None,
    datasets: Optional[List[Dict]] = None
) -> str:
    """
    Create an interactive D3.js bubble chart.
    
    Args:
        title: Chart title
        data: Chart data with datasets containing bubble data points
        datasets: List of dataset objects with data: [{x, y, r}] arrays
    
    Returns:
        Path to the generated HTML file containing the interactive bubble chart
    """
    # Normalize data format
    if data is None and datasets is not None:
        chart_data = {'datasets': datasets}
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    arguments = {
        'title': title,
        'data': chart_data
    }
    
    response = call_d3_api('bubble', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Bubble chart created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating bubble chart: {response.get('message', 'Unknown error')}"

@mcp.tool()
def create_heatmap(
    title: str = "Heatmap",
    data: Union[Dict, List] = None,
    x_labels: Optional[List[str]] = None,
    y_labels: Optional[List[str]] = None,
    values: Optional[List[List[float]]] = None
) -> str:
    """
    Create an interactive D3.js heatmap.
    
    Args:
        title: Chart title
        data: Chart data with xLabels, yLabels, and values matrix
        x_labels: X-axis category labels
        y_labels: Y-axis category labels  
        values: 2D array where values[y][x] represents the intensity
    
    Returns:
        Path to the generated HTML file containing the interactive heatmap
    """
    # Normalize data format
    if data is None and all(v is not None for v in [x_labels, y_labels, values]):
        chart_data = {
            'xLabels': x_labels,
            'yLabels': y_labels,
            'values': values
        }
    elif isinstance(data, dict):
        chart_data = data
    else:
        chart_data = {'data': data} if data else {}
    
    arguments = {
        'title': title,
        'data': chart_data
    }
    
    response = call_d3_api('heatmap', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] Heatmap created: {response.get('path', 'Unknown path')}"
    else:
        return f"[ERROR] Error creating heatmap: {response.get('message', 'Unknown error')}"

@mcp.tool()
def render_chart_from_dataset(
    title: str = "Chart",
    data: Union[Dict, List] = None,
    chart_type: str = "line",
    framework: str = "d3",
    output_dir: Optional[str] = None
) -> str:
    """
    Universal chart renderer that intelligently routes to appropriate chart types.
    
    Args:
        title: Chart title
        data: Chart data in various formats (Chart.js, raw arrays, objects)
        chart_type: Chart type to create. Supported types vary by framework:
                   
                   Chart.js supports: line, bar, grouped_bar, pie, donut, scatter, bubble
                   D3.js supports: line, bar, grouped_bar, pie, donut, bubble, heatmap, 
                                  packed, treemap, sankey, chord, force, horizontal_bar
                   
                   D3-only types: heatmap, packed, treemap, sankey, chord, force, horizontal_bar
        
        framework: Rendering framework - 'd3' (default), 'chartjs', or 'auto'
                  Use 'd3' for advanced visualizations like heatmaps, treemaps, network graphs
                  Use 'chartjs' for simple, fast charts with good mobile support
        
        output_dir: Optional output directory path (defaults to server's html-charts dir)
    
    Returns:
        Path to the generated HTML file containing the interactive chart
        
    Raises:
        Error if chart_type is not supported by the selected framework
    """
    arguments = {
        'title': title,
        'data': data,
        'chart_type': chart_type,
        'framework': framework
    }
    if output_dir:
        arguments['output_dir'] = output_dir
    
    response = call_d3_api('render_from_dataset', arguments)
    
    if response.get('status') == 'ok':
        return f"[DONE] {chart_type.replace('_', ' ').title()} chart created: {response.get('path', 'Unknown path')}"
    else:
        error_msg = response.get('message', 'Unknown error')
        error_details = response.get('details', '')
        if error_details:
            raise ValueError(f"{error_msg}\n\n{error_details}")
        raise ValueError(f"{error_msg}")

# ================================================================================
# RESOURCES AND DOCUMENTATION  
# ================================================================================

@mcp.resource("d3-charts://docs/overview")
def chart_overview() -> Resource:
    """Overview of available D3 chart types and capabilities."""
    content = """
# D3 Chart Generation MCP Server

This server provides tools for creating interactive D3.js visualizations from data.

## Available Chart Types

### Basic Statistical Charts
- **Line Charts**: Multi-line time series with smooth curves and hover interactions
- **Bar Charts**: Vertical bars (single/multi-series) with automatic scaling  
- **Grouped Bar Charts**: Side-by-side bars with legend and tooltips (enhanced)
- **Stacked Bar Charts**: Cumulative stacking for part-to-whole analysis
- **Horizontal Bar Charts**: Suitable for long category names

### Distribution & Correlation  
- **Pie/Donut Charts**: Proportional slices with hover animations
- **Scatter Plots**: Two-dimensional correlation analysis
- **Bubble Charts**: Three-dimensional data (x, y, radius)
- **Heatmaps**: 2D intensity grids with color mapping

### Specialized Visualizations
- **Histograms**: Distribution analysis of numerical data
- **Treemaps**: Hierarchical space-filling rectangles  
- **Force Networks**: Node-link diagrams with physics simulation
- **Circle Packing**: Proportional bubble hierarchies

## Data Formats Supported

### Chart.js Compatible Format
```json
{
  "labels": ["Jan", "Feb", "Mar"],
  "datasets": [{
    "label": "Sales",
    "data": [100, 150, 200],
    "backgroundColor": "#1f77b4"
  }]
}
```

### Simple Arrays
```json
[10, 20, 30, 25, 40]
```

### Object Arrays  
```json
[
  {"month": "Jan", "value": 100},
  {"month": "Feb", "value": 150}
]
```

## Features

- **Interactive**: Hover tooltips, zoom, pan capabilities
- **Responsive**: Automatic sizing and mobile-friendly
- **Accessible**: ARIA labels and keyboard navigation
- **Customizable**: Colors, styling, and layout options
- **Export Ready**: High-quality SVG output for reports

All charts are saved as standalone HTML files that can be opened in any modern web browser.
"""
    return Resource(
        uri="d3-charts://docs/overview",
        name="D3 Chart Overview",
        mimeType="text/markdown", 
        contents=TextResourceContents(text=content)
    )

@mcp.resource("d3-charts://docs/data-formats") 
def data_formats() -> Resource:
    """Documentation for supported data formats and examples."""
    content = """
# Data Format Guide

## Chart.js Format (Recommended)

The most flexible format supporting multiple data series:

```json
{
  "labels": ["Q1", "Q2", "Q3", "Q4"],
  "datasets": [
    {
      "label": "Revenue",
      "data": [120000, 150000, 180000, 200000],
      "backgroundColor": "#1f77b4",
      "borderColor": "#1f77b4"
    },
    {
      "label": "Expenses", 
      "data": [80000, 95000, 110000, 120000],
      "backgroundColor": "#ff7f0e",
      "borderColor": "#ff7f0e"
    }
  ]
}
```

## Project Allocation Format (for PMO data)

Special format for resource allocation across projects:

```json
[
  {
    "month": "2025-01",
    "resource_id": 1,
    "project_allocation_details": [
      {"project_name": "Project Alpha", "planned_percentage": 60},
      {"project_name": "Project Beta", "planned_percentage": 40}
    ]
  }
]
```

## Scatter Plot Format

For correlation analysis:

```json
{
  "points": [
    {"x": 10, "y": 20, "r": 5, "label": "Point A"},
    {"x": 15, "y": 25, "r": 8, "label": "Point B"}
  ]
}
```

## Heatmap Format

For intensity matrices:

```json
{
  "xLabels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
  "yLabels": ["Week 1", "Week 2", "Week 3"],
  "values": [
    [10, 15, 12, 18, 20],
    [8, 12, 16, 14, 22], 
    [12, 18, 20, 16, 24]
  ]
}
```

## Simple Arrays

For quick single-series charts:

```json
[100, 150, 200, 175, 225]
```

The server will automatically detect the format and convert as needed.
"""
    return Resource(
        uri="d3-charts://docs/data-formats",
        name="Data Format Guide", 
        mimeType="text/markdown",
        contents=TextResourceContents(text=content)
    )

if __name__ == "__main__":
    # Verify D3 API server exists
    if not D3_API_SERVER.exists():
        print(f"[ERROR] Error: D3 API server not found at {D3_API_SERVER}")
        print("Please ensure d3_chart_api_server.py exists in the same directory.")
        sys.exit(1)
    
    print("[EMOJI] Starting D3 Chart Generation MCP Server...")
    print(f"[CHART] D3 API backend: {D3_API_SERVER}")
    print("[DONE] Server ready to generate interactive charts!")
    
    mcp.run()