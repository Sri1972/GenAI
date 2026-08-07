#!/usr/bin/env python3
"""
Generate per-tool HTML documentation pages from PMO MCP server metadata and tool signatures.
This script analyzes pmo_mcp_server.py and metadata files to create detailed reference docs.
"""

import json
import os
import re
import inspect
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import the MCP server to extract tool information
import sys
sys.path.append(os.path.dirname(__file__))

def extract_tool_info() -> List[Dict[str, Any]]:
    """Extract tool information from the MCP server source code."""
    tools = []
    
    # Read the source file and extract @mcp.tool decorated functions
    source_file = os.path.join(os.path.dirname(__file__), "pmo_mcp_server.py")
    
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
            # Simple parameter parsing - this could be enhanced
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

def categorize_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize tools by functionality."""
    categories = {
        "metadata": [],
        "projects": [],
        "resources": [], 
        "allocations": [],
        "business": []
    }
    
    for tool in tools:
        name = tool["name"]
        if "metadata" in name or "field_definitions" in name or "endpoints_summary" in name:
            categories["metadata"].append(tool)
        elif "project" in name:
            categories["projects"].append(tool)
        elif "resource" in name or "capacity" in name:
            categories["resources"].append(tool)
        elif "allocation" in name:
            categories["allocations"].append(tool)
        elif "business" in name or "portfolio" in name or "strategic" in name:
            categories["business"].append(tool)
        else:
            categories["metadata"].append(tool)  # default
    
    return categories

def generate_html_template() -> str:
    """Generate the base HTML template for tool pages."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title} - PMO MCP Server</title>
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
  </style>
</head>
<body>
  <div class="nav-links">
    <a href="index.html">← Back to Overview</a>
    {category_links}
  </div>
  
  {content}
  
    <footer class="muted">Generated: {date} — Source: <code>server/pmo/pmo_mcp_server.py</code></footer>
</body>
</html>"""

def generate_tool_page(tool: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """Generate HTML page for a single tool."""
    
    # Parse docstring for description and sections
    docstring = tool["docstring"]
    doc_lines = docstring.split('\n') if docstring else []
    
    # Extract main description (first paragraph)
    description = ""
    args_section = ""
    returns_section = ""
    
    current_section = "description"
    for line in doc_lines:
        line = line.strip()
        if line.lower().startswith("args:") or line.lower().startswith("arguments:"):
            current_section = "args"
        elif line.lower().startswith("returns:") or line.lower().startswith("return:"):
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
    
    # Find related metadata information
    metadata_info = ""
    business_context = ""
    
    # Try to match tool to metadata categories
    tool_name = tool["name"]
    if "project" in tool_name:
        projects_meta = metadata.get("projects_api", {})
        if projects_meta.get("description"):
            business_context = f"<div class='business-context'><strong>Business Context:</strong> {projects_meta['description']}</div>"
    elif "resource" in tool_name:
        resources_meta = metadata.get("resources_api", {})
        if resources_meta.get("description"):
            business_context = f"<div class='business-context'><strong>Business Context:</strong> {resources_meta['description']}</div>"
    
    # Generate usage examples based on tool type
    examples_html = ""
    if "get_all_projects" in tool_name:
        examples_html = '''
        <div class="example">
          <strong>Example Usage:</strong><br>
          <code>result = client.call_tool("get_all_projects")</code><br>
          <em>Returns list of all projects with metadata summary as first element.</em>
        </div>'''
    elif "get_project_by_id" in tool_name:
        examples_html = '''
        <div class="example">
          <strong>Example Usage:</strong><br>
          <code>result = client.call_tool("get_project_by_id", project_id=123)</code><br>
          <em>Returns detailed information for project with ID 123.</em>
        </div>'''
    elif "get_resource_capacity_allocation" in tool_name:
        examples_html = '''
        <div class="example">
          <strong>Example Usage:</strong><br>
          <code>result = client.call_tool("get_resource_capacity_allocation", 
                         resource_id=456, start_date="2025-01-01", 
                         end_date="2025-03-31", interval="Monthly")</code><br>
          <em>Returns capacity allocation data for resource 456 in Q1 2025.</em>
        </div>'''
    
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
  
  {f'<div class="section"><h2>Usage Examples</h2>{examples_html}</div>' if examples_html else ''}
  
  <div class="section">
    <h2>Related API Endpoints</h2>
    <p class="muted">This tool may call the following backend API endpoints:</p>
    <ul>
      <li><code>GET {metadata.get("master_index", {}).get("api_service_info", {}).get("base_url", "http://localhost:5000")}/...</code></li>
    </ul>
  </div>
  
  <div class="section">
    <h2>Error Handling</h2>
    <p>This tool includes automatic error handling for:</p>
    <ul>
      <li>Network connectivity issues</li>
      <li>API validation errors (422 status)</li>
      <li>Resource not found errors (404 status)</li>
      <li>Response format normalization</li>
    </ul>
  </div>
'''
    
    return content

def generate_category_page(category_name: str, tools: List[Dict[str, Any]]) -> str:
    """Generate a category overview page."""
    
    category_descriptions = {
        "metadata": "Tools for accessing API metadata, field definitions, and endpoint information",
        "projects": "Tools for managing projects, timelines, and project-related operations", 
        "resources": "Tools for managing resources, capacity allocation, and availability",
        "allocations": "Tools for managing resource allocations and project assignments",
        "business": "Tools for organizational structure, portfolios, and business lines"
    }
    
    tools_list = ""
    for tool in tools:
        description = tool["docstring"].split('\n')[0] if tool["docstring"] else "No description available"
        tools_list += f'''
        <div class="param">
          <a href="{tool['name']}.html"><strong>{tool['name']}</strong></a><br>
          <span class="muted">{description}</span>
        </div>'''
    
    content = f'''
  <h1>{category_name.title()} Tools</h1>
  <p>{category_descriptions.get(category_name, "Tools in this category")}</p>
  
  <div class="section">
    <h2>Available Tools</h2>
    {tools_list}
  </div>
'''
    
    return content

def main():
    """Main function to generate all documentation."""
    print("Generating PMO MCP tool documentation...")
    
    # Extract tool information
    tools = extract_tool_info()
    
    # Load metadata separately
    from pmo_comprehensive import get_cached_metadata
    metadata = get_cached_metadata()
    
    # Categorize tools
    categories = categorize_tools(tools)
    
    # Create docs directory if it doesn't exist
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    # Generate category links for navigation
    category_links = " | ".join([f'<a href="{cat}.html">{cat.title()}</a>' for cat in categories.keys()])
    
    # Generate individual tool pages
    for category_name, category_tools in categories.items():
        if not category_tools:
            continue
            
        # Generate category overview page
        category_content = generate_category_page(category_name, category_tools)
        category_html = generate_html_template().format(
            title=f"{category_name.title()} Tools",
            category_links=category_links,
            content=category_content,
            date=datetime.now().strftime("%B %d, %Y")
        )
        
        category_file = os.path.join(docs_dir, f"{category_name}.html")
        with open(category_file, 'w', encoding='utf-8') as f:
            f.write(category_html)
        print(f"Generated: {category_name}.html")
        
        # Generate individual tool pages
        for tool in category_tools:
            tool_content = generate_tool_page(tool, metadata)
            tool_html = generate_html_template().format(
                title=tool["name"],
                category_links=category_links,
                content=tool_content,
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