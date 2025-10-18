import json
import os
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
import requests
from urllib.parse import quote

api_url = "http://localhost:5000"

mcp = FastMCP("PMO")

# Load resources and prompts from JSON files
PMO_DIR = os.path.dirname(os.path.abspath(__file__))

def load_resource_txt(filename: str) -> str:
    PMO_DIR = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(PMO_DIR, "resources")
    with open(os.path.join(resources_dir, filename), encoding="utf-8") as f:
        return f.read()

def load_prompt_txt(filename: str) -> str:
    PMO_DIR = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(PMO_DIR, "prompts")
    with open(os.path.join(prompts_dir, filename), encoding="utf-8") as f:
        return f.read()

# ================================================================================
# SERVER INSTRUCTIONS AND GENERAL RESOURCES
# ================================================================================

'''
@mcp.resource("pmo://system/instructions")
def server_instructions() -> str:
    return """
PMO (Project Management Office) Server - Provides access to project data and business intelligence.

QUERY ROUTING:
- For "all projects" (no filters) → use get_all_projects()
- For specific area queries → use get_business_lines() then get_all_projects_filtered()

DATA HANDLING:
- strategic_portfolio and product_line are case-sensitive
- Handle approximate/partial names by matching against business_lines
- technology_project accepts only "YES"/"NO" values
- Missing data fields may be null - always check before processing

WORKFLOW PATTERNS:
- Always validate user input against business_lines for filtered queries
- Use exact case-sensitive values from business_lines data
- Provide structured summaries with counts and resource breakdowns
"""
'''

# ================================================================================
# BUSINESS LINES SECTION
# ================================================================================

@mcp.tool()
def get_business_lines() -> List[Dict[str, Any]]:
    """
    Fetch all available business lines (strategic portfolios and product lines).
    Use this for validation and to understand the data structure before filtering.
    """
    try:
        url = f"{api_url}/business_lines"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_business_lines: {str(e)}"}]

@mcp.resource("pmo://docs/business_lines")
def business_lines_doc() -> str:
    return load_resource_txt("docs_business_lines.txt")

@mcp.prompt("business_lines_validation")
def business_lines_prompt() -> str:
    return load_prompt_txt("business_lines_validation.txt")

# ================================================================================
# ALL PROJECTS SECTION (Unfiltered)
# ================================================================================

@mcp.tool()
def get_all_projects() -> List[Dict[str, Any]]:
    """
    Fetch all projects without any filters. Use for comprehensive overviews.
    Returns complete project dataset with all fields.
    """
    try:
        url = f"{api_url}/projects"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_all_projects: {str(e)}"}]

@mcp.resource("pmo://docs/all_projects")
def all_projects_doc() -> str:
    return load_resource_txt("docs_all_projects.txt")

@mcp.prompt("all_projects_summary")
def all_projects_prompt() -> str:
    return load_prompt_txt("all_projects_summary.txt")

# ================================================================================
# FILTERED PROJECTS SECTION
# ================================================================================

@mcp.tool()
def get_filtered_projects(
    strategic_portfolio: Optional[str] = None,
    product_line: Optional[str] = None,
    technology_project: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch projects filtered by strategic portfolio, product line, or technology flag.
    Use get_business_lines() first to ensure correct case-sensitive parameter values.
    """
    try:
        params = {}
        if strategic_portfolio:
            params["strategic_portfolio"] = strategic_portfolio
        if product_line:
            params["product_line"] = product_line
        if technology_project:
            params["technology_project"] = technology_project

        url = f"{api_url}/projects_filter"
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_filtered_projects: {str(e)}"}]

@mcp.resource("pmo://docs/filtered_projects")
def filtered_projects_doc() -> str:
    return load_resource_txt("docs_filtered_projects.txt")

@mcp.prompt("filtered_projects_workflow")
def filtered_projects_prompt() -> str:
    return load_prompt_txt("filtered_projects_workflow.txt")

# ================================================================================
# ALL RESOURCES SECTION
# ================================================================================

@mcp.tool()
def get_all_resources() -> List[Dict[str, Any]]:
    """
    Fetch all resources (people, employees, contractors, etc.) in the system.
    Use for resource directory, capacity planning, or role lookup.
    """
    try:
        url = f"{api_url}/resources"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_all_resources: {str(e)}"}]

@mcp.resource("pmo://docs/all_resources")
def all_resources_doc() -> str:
    return load_resource_txt("docs_all_resources.txt")

@mcp.prompt("all_resources_summary")
def all_resources_prompt() -> str:
    return load_prompt_txt("all_resources_summary.txt")

# ================================================================================
# RESOURCE ALLOCATION PLANNED/ACTUAL SECTION
# ================================================================================

@mcp.tool()
def get_resource_allocation_planned_actual(
    resource_id: int,
    start_date: str,
    end_date: str,
    interval: str = "Weekly"
) -> List[Dict[str, Any]]:
    """
    Fetch planned and actual allocation/capacity for a resource over a time interval.
    Use resource_id from get_all_resources. Interval can be 'Weekly' or 'Monthly'.
    """
    try:
        params = {
            "resource_id": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval
        }
        url = f"{api_url}/resource_capacity_allocation"
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_resource_allocation_planned_actual: {str(e)}"}]

@mcp.resource("pmo://docs/resource_capacity_allocation_planned_actual")
def resource_capacity_allocation_planned_actual_doc() -> str:
    return load_resource_txt("docs_resource_capacity_allocation_planned_actual.txt")

@mcp.prompt("resource_capacity_allocation_planned_actual")
def resource_capacity_allocation_planned_actual_prompt() -> str:
    return load_prompt_txt("resource_capacity_allocation_planned_actual.txt")

if __name__ == "__main__":
    mcp.run()