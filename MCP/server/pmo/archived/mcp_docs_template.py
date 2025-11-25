#!/usr/bin/env python3
"""
Generic MCP Server Documentation Generator Template
===================================================

This is a reusable template for generating HTML documentation for any MCP server.
It can be customized for different MCP servers by modifying the configuration section.

Usage:
1. Copy this file to your MCP server directory
2. Update the CONFIGURATION section below
3. Implement server-specific metadata loading if needed
4. Run: python generate_mcp_docs.py

For the D3 Chart MCP Server:
- Set SERVER_NAME = "D3 Chart MCP Server"
- Set SOURCE_FILE = "mcp_d3_server.py" (or whatever the main file is)
- Implement load_chart_metadata() function
- Update tool categorization logic

"""

import json
import os
import re
import inspect
from typing import Dict, List, Any, Optional
from datetime import datetime

# ================================
# CONFIGURATION - Modify for your MCP server
# ================================

SERVER_NAME = "PMO MCP Server"
SERVER_DESCRIPTION = "MCP server exposing PMO (Project & Resource Management) tools"
SOURCE_FILE = "pmo_mcp_server.py"
DOCS_DIR = "docs"

# Categories for organizing tools - customize for your server
TOOL_CATEGORIES = {
    "metadata": {
        "name": "Metadata Tools",
        "description": "Tools for accessing API metadata, field definitions, and endpoint information",
        "keywords": ["metadata", "field_definitions", "endpoints_summary"]
    },
    "projects": {
        "name": "Project Tools", 
        "description": "Tools for managing projects, timelines, and project-related operations",
        "keywords": ["project"]
    },
    "resources": {
        "name": "Resource Tools",
        "description": "Tools for managing resources, capacity allocation, and availability", 
        "keywords": ["resource", "capacity"]
    },
    "business": {
        "name": "Business Structure Tools",
        "description": "Tools for organizational structure, portfolios, and business lines",
        "keywords": ["business", "portfolio", "strategic"]
    },
    "charts": {
        "name": "Chart Tools",
        "description": "Tools for generating and managing charts and visualizations",
        "keywords": ["chart", "graph", "viz", "d3", "render"]
    }
}

# ================================
# CORE TEMPLATE FUNCTIONS
# ================================

def extract_tool_info_from_source(source_file: str) -> List[Dict[str, Any]]:
    """Extract tool information from MCP server source code."""
    tools = []
    
    if not os.path.exists(source_file):
        print(f"Warning: Source file {source_file} not found")
        return tools
    
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all @mcp.tool() decorated functions
    tool_pattern = r'@mcp\.tool\(\)\s*\ndef\s+(\w+)\s*\((.*?)\)\s*->\s*(.*?):\s*"""(.*?)"""'
    matches = re.finditer(tool_pattern, content, re.DOTALL)
    
    for match in matches:
        func_name = match.group(1)
        params_str = match.group(2)
        return_type = match.group(3).strip()
        docstring = match.group(4).strip()
        
        # Parse parameters
        params = []
        if params_str.strip():
            param_parts = [p.strip() for p in params_str.split(',') if p.strip()]
            for param_part in param_parts:
                if ':' in param_part:
                    param_name = param_part.split(':')[0].strip()
                    param_type = param_part.split(':')[1].split('=')[0].strip()
                    has_default = '=' in param_part
                    default_val = param_part.split('=')[1].strip() if has_default else None
                    
                    params.append({
                        "name": param_name,
                        "type": param_type,
                        "default": default_val,
                        "required": not has_default
                    })
        
        tools.append({
            "name": func_name,
            "function": func_name,
            "docstring": docstring,
            "parameters": params,
            "return_type": return_type,
            "signature": f"({params_str}) -> {return_type}",
            "description": docstring.split('\n')[0] if docstring else ""
        })
    
    return tools

def categorize_tools_generic(tools: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize tools using the configured categories."""
    categories = {cat_id: [] for cat_id in TOOL_CATEGORIES.keys()}
    categories["other"] = []  # Catch-all category
    
    for tool in tools:
        tool_name = tool["name"].lower()
        categorized = False
        
        for cat_id, cat_info in TOOL_CATEGORIES.items():
            if any(keyword in tool_name for keyword in cat_info["keywords"]):
                categories[cat_id].append(tool)
                categorized = True
                break
        
        if not categorized:
            categories["other"].append(tool)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}

def load_server_metadata() -> Dict[str, Any]:
    """Load server-specific metadata. Override this for your MCP server."""
    # For PMO server, load from metadata directory
    if SERVER_NAME == "PMO MCP Server":
        try:
            from pmo_comprehensive import get_cached_metadata
            return get_cached_metadata()
        except ImportError:
            pass
    
    # For D3 Chart server or others, implement custom loading
    # Example:
    # if SERVER_NAME == "D3 Chart MCP Server":
    #     return load_chart_metadata()
    
    return {}

def generate_html_template() -> str:
    """Generate the base HTML template for all pages."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title} - {server_name}</title>
  <style>
    body{{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;padding:28px;max-width:1000px;margin:auto;color:#1b1b1b}}
    h1,h2,h3{{color:#0b4a6f}}
    h1{{border-bottom:2px solid #0b4a6f;padding-bottom:8px}}
    pre{{background:#f6f8fa;padding:12px;border-radius:6px;overflow:auto;border-left:4px solid #0b66a7}}
    code{{background:#f2f4f6;padding:2px 6px;border-radius:4px}}
    .signature{{background:#e8f4f8;padding:10px;border-radius:6px;font-family:monospace;margin:10px 0}}
    .param{{margin:8px 0;padding:8px;background:#f8f9fa;border-left:3px solid #28a745}}
    .param-name{{font-weight:bold;color:#0366d6}}
    .param-type{{color:#6f42c1;font-style:italic}}
    .required{{color:#d73a49;font-size:0.9em}}
    .optional{{color:#586069;font-size:0.9em}}
    .section{{margin-bottom:26px}}
    .muted{{color:#586069;font-size:0.95em}}
    .nav-links{{background:#f1f3f4;padding:12px;border-radius:6px;margin-bottom:20px}}
    .nav-links a{{color:#0b66a7;text-decoration:none;margin-right:15px}}
    .nav-links a:hover{{text-decoration:underline}}
    .example{{background:#fff8dc;padding:12px;border-radius:6px;border-left:4px solid #ffa500}}
    .metadata-info{{background:#e6f3ff;padding:12px;border-radius:6px;margin:10px 0}}
    .business-context{{background:#f0f8f0;padding:12px;border-radius:6px;margin:10px 0}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:20px 0}}
  </style>
</head>
<body>
  <div class="nav-links">
    <a href="index.html">← Back to Overview</a>
    {category_links}
  </div>
  
  {content}
  
  <footer class="muted">Generated: {date} — Source: <code>{source_file}</code></footer>
</body>
</html>"""

def generate_tool_page_generic(tool: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """Generate HTML page for a single tool."""
    
    # Parse docstring
    docstring = tool["docstring"]
    doc_lines = docstring.split('\n') if docstring else []
    
    description = ""
    args_section = ""
    returns_section = ""
    
    current_section = "description"
    for line in doc_lines:
        line = line.strip()
        if line.lower().startswith("args:"):
            current_section = "args"
        elif line.lower().startswith("returns:"):
            current_section = "returns"
        elif current_section == "description" and line:
            description += line + " "
        elif current_section == "args" and line and not line.lower().startswith("args:"):
            args_section += line + "\n"
        elif current_section == "returns" and line and not line.lower().startswith("returns:"):
            returns_section += line + "\n"
    
    # Generate parameter documentation
    params_html = ""
    for param in tool["parameters"]:
        required_badge = '<span class="required">(required)</span>' if param["required"] else '<span class="optional">(optional)</span>'
        default_info = f' = {param["default"]}' if param["default"] else ''
        
        params_html += f'''
        <div class="param">
          <span class="param-name">{param["name"]}</span>
          <span class="param-type">{param["type"]}</span>{default_info}
          {required_badge}
        </div>'''
    
    # Server-specific business context
    business_context = ""
    if metadata and "description" in str(metadata):
        business_context = f"<div class='business-context'><strong>Server Context:</strong> Part of {SERVER_NAME}</div>"
    
    content = f'''
  <h1>{tool["name"]}</h1>
  <p class="muted">MCP Tool Function: <code>{tool["function"]}</code></p>
  
  <div class="section">
    <h2>Description</h2>
    <p>{description.strip() or "No description available."}</p>
    {business_context}
  </div>
  
  <div class="section">
    <h2>Function Signature</h2>
    <div class="signature">{tool["name"]}{tool["signature"]}</div>
    <p><strong>Returns:</strong> <code>{tool["return_type"]}</code></p>
  </div>
  
  <div class="section">
    <h2>Parameters</h2>
    {params_html if params_html else "<p><em>No parameters required.</em></p>"}
  </div>
  
  {f'<div class="section"><h2>Arguments Documentation</h2><pre>{args_section.strip()}</pre></div>' if args_section.strip() else ''}
  
  {f'<div class="section"><h2>Return Value</h2><pre>{returns_section.strip()}</pre></div>' if returns_section.strip() else ''}
  
  <div class="section">
    <h2>Error Handling</h2>
    <p>This tool includes automatic error handling for common issues like network connectivity and API validation errors.</p>
  </div>
'''
    
    return content

def generate_category_page_generic(category_id: str, tools: List[Dict[str, Any]]) -> str:
    """Generate a category overview page."""
    
    category_info = TOOL_CATEGORIES.get(category_id, {
        "name": category_id.title(),
        "description": f"Tools in the {category_id} category"
    })
    
    tools_list = ""
    for tool in tools:
        description = tool["docstring"].split('\n')[0] if tool["docstring"] else "No description available"
        tools_list += f'''
        <div class="param">
          <a href="{tool['name']}.html"><strong>{tool['name']}</strong></a><br>
          <span class="muted">{description}</span>
        </div>'''
    
    content = f'''
  <h1>{category_info["name"]}</h1>
  <p>{category_info["description"]}</p>
  
  <div class="section">
    <h2>Available Tools</h2>
    {tools_list}
  </div>
'''
    
    return content

def generate_index_page(categories: Dict[str, List[Dict[str, Any]]]) -> str:
    """Generate the main index page."""
    
    # Generate category overview
    category_grid = ""
    for cat_id, tools in categories.items():
        if not tools:
            continue
        cat_info = TOOL_CATEGORIES.get(cat_id, {"name": cat_id.title(), "description": f"Tools in {cat_id}"})
        category_grid += f'''
      <div class="param">
        <a href="{cat_id}.html"><strong>{cat_info["name"]}</strong></a><br>
        <span class="muted">{cat_info["description"]} ({len(tools)} tools)</span>
      </div>'''
    
    # Generate tool summary table
    tools_table = ""
    for cat_id, tools in categories.items():
        for tool in tools:
            description = tool["description"][:100] + "..." if len(tool["description"]) > 100 else tool["description"]
            tools_table += f'<tr><td><a href="{tool["name"]}.html">{tool["name"]}</a></td><td><code>{tool["signature"]}</code></td><td>{description}</td></tr>'
    
    content = f'''
  <h1>{SERVER_NAME} — Documentation</h1>
  <p class="muted">Generated documentation for MCP tools and components</p>

  <div class="section">
    <h2>Overview</h2>
    <p>{SERVER_DESCRIPTION}</p>
  </div>

  <div class="section">
    <h2>Tool Categories & Reference</h2>
    <p class="muted">Click on a category to see detailed documentation for each tool in that category.</p>
    
    <div class="grid">
      {category_grid}
    </div>
  </div>

  <div class="section">
    <h2>All Tools Summary</h2>
    <table>
      <thead>
        <tr><th>Tool</th><th>Signature</th><th>Purpose</th></tr>
      </thead>
      <tbody>
        {tools_table}
      </tbody>
    </table>
  </div>
'''
    
    return content

def main():
    """Main function to generate all documentation."""
    print(f"Generating {SERVER_NAME} documentation...")
    
    # Extract tool information
    source_path = os.path.join(os.path.dirname(__file__), SOURCE_FILE)
    tools = extract_tool_info_from_source(source_path)
    metadata = load_server_metadata()
    
    if not tools:
        print(f"No tools found in {SOURCE_FILE}. Please check the source file path and @mcp.tool() decorators.")
        return
    
    # Categorize tools
    categories = categorize_tools_generic(tools)
    
    # Create docs directory
    docs_dir = os.path.join(os.path.dirname(__file__), DOCS_DIR)
    os.makedirs(docs_dir, exist_ok=True)
    
    # Generate category links for navigation
    category_links = " | ".join([f'<a href="{cat}.html">{TOOL_CATEGORIES.get(cat, {}).get("name", cat.title())}</a>' for cat in categories.keys() if categories[cat]])
    
    # Generate main index page
    index_content = generate_index_page(categories)
    index_html = generate_html_template().format(
        title="Documentation",
        server_name=SERVER_NAME,
        category_links=category_links,
        content=index_content,
        source_file=SOURCE_FILE,
        date=datetime.now().strftime("%B %d, %Y")
    )
    
    index_file = os.path.join(docs_dir, "index.html")
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f"Generated: index.html")
    
    # Generate category and tool pages
    for category_id, category_tools in categories.items():
        if not category_tools:
            continue
            
        # Generate category overview page
        category_content = generate_category_page_generic(category_id, category_tools)
        category_html = generate_html_template().format(
            title=f"{TOOL_CATEGORIES.get(category_id, {}).get('name', category_id.title())} Tools",
            server_name=SERVER_NAME,
            category_links=category_links,
            content=category_content,
            source_file=SOURCE_FILE,
            date=datetime.now().strftime("%B %d, %Y")
        )
        
        category_file = os.path.join(docs_dir, f"{category_id}.html")
        with open(category_file, 'w', encoding='utf-8') as f:
            f.write(category_html)
        print(f"Generated: {category_id}.html")
        
        # Generate individual tool pages
        for tool in category_tools:
            tool_content = generate_tool_page_generic(tool, metadata)
            tool_html = generate_html_template().format(
                title=tool["name"],
                server_name=SERVER_NAME,
                category_links=category_links,
                content=tool_content,
                source_file=SOURCE_FILE,
                date=datetime.now().strftime("%B %d, %Y")
            )
            
            tool_file = os.path.join(docs_dir, f"{tool['name']}.html")
            with open(tool_file, 'w', encoding='utf-8') as f:
                f.write(tool_html)
            print(f"Generated: {tool['name']}.html")
    
    print(f"Documentation generation complete! Generated {len(tools)} tool pages and {len(categories)} category pages.")
    print(f"Files created in: {docs_dir}")

if __name__ == "__main__":
    main()