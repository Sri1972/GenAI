# --- Hybrid tool selection: rule-based first, then prompt guidance ---
from typing import Dict
def select_mcp_tool_for_query(query: str) -> Dict[str, str]:
    """
    Hybrid tool selection: returns recommended MCP tool name and guidance.
    - First tries rule-based selection.
    - If no match, falls back to MCP prompt guidance.
    Returns a dict: {'tool': tool_name, 'guidance': prompt_string}
    """
    q = query.lower()
    # Rule-based selection
    if (
        ("hours" in q or "cost" in q) and
        ("resource" in q or "resources" in q) and
        ("portfolio" in q or "product line" in q)
    ):
        if any(t in q for t in ["date", "month", "year", "timeline", "period", "interval", "weekly", "monthly"]):
            return {"tool": "get_resources_by_portfolio_allocation", "guidance": TOOL_SELECTION_GUIDE}
        elif "project" in q:
            return {"tool": "get_project_resource_allocation", "guidance": TOOL_SELECTION_GUIDE}
        else:
            return {"tool": "get_projects_by_portfolio_and_product_line", "guidance": TOOL_SELECTION_GUIDE}
    if "project" in q and ("resource allocation" in q or "resource planning" in q) and any(t in q for t in ["date", "month", "year", "timeline", "period", "interval", "weekly", "monthly"]):
        return {"tool": "get_project_resource_allocation", "guidance": TOOL_SELECTION_GUIDE}
    if ("resource" in q or "resources" in q) and ("capacity" in q or "cost" in q) and any(t in q for t in ["date", "month", "year", "timeline", "period", "interval", "weekly", "monthly"]):
        return {"tool": "get_resource_capacity_allocation", "guidance": TOOL_SELECTION_GUIDE}
    if "project" in q and ("overview" in q or "list" in q or "summary" in q):
        return {"tool": "get_all_projects", "guidance": TOOL_SELECTION_GUIDE}
    if "resource" in q and ("overview" in q or "list" in q or "summary" in q):
        return {"tool": "get_all_resources", "guidance": TOOL_SELECTION_GUIDE}
    if "business structure" in q or "portfolio" in q or "product line" in q:
        return {"tool": "get_business_lines", "guidance": TOOL_SELECTION_GUIDE}
    if any(t in q for t in ["chart", "graph", "plot", "visualization"]):
        return {"tool": "forward_chart_json_to_d3_mcp", "guidance": TOOL_SELECTION_GUIDE}
    if ("resource" in q or "resources" in q) and any(t in q for t in ["utilization", "available capacity", "over-allocation", "under-allocation"]):
        if "portfolio" in q:
            return {"tool": "get_resources_by_portfolio_allocation", "guidance": TOOL_SELECTION_GUIDE}
        else:
            return {"tool": "get_resource_capacity_allocation", "guidance": TOOL_SELECTION_GUIDE}
    if "project" in q and any(t in q for t in ["resource planning", "gaps", "conflicts"]):
        return {"tool": "get_project_resource_allocation", "guidance": TOOL_SELECTION_GUIDE}
    if "filter" in q or any(t in q for t in ["status", "type", "date"]):
        return {"tool": "get_projects_dynamic_filter", "guidance": TOOL_SELECTION_GUIDE}
    # Fallback: return prompt guidance only
    return {"tool": "unknown", "guidance": TOOL_SELECTION_GUIDE}
import json
import os
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
import requests
from urllib.parse import quote
from datetime import datetime


api_url = "http://localhost:5000"

# Centralized tool selection guide string
TOOL_SELECTION_GUIDE = (
    "Tool Selection Guide:\n"
    "- If the user asks for hours and cost per resource for all projects in a portfolio (e.g., 'market & sell') without a time element, use get_projects_by_portfolio_and_product_line.\n"
    "- If the query includes a timeline (dates, months, etc.), use get_resources_by_portfolio_allocation.\n"
    "- For project-level resource allocation with a time element, use get_project_resource_allocation.\n"
    "- For resource-level capacity/cost over a period, use get_resource_capacity_allocation.\n"
    "- For general project overviews, use get_all_projects.\n"
    "- For business structure, use get_business_lines or get_strategic_portfolios.\n"
    "- If the user requests a chart, graph, plot, or visualization of resource/project data, use the chart rendering tools (e.g., forward_chart_json_to_d3_mcp, render_from_dataset).\n"
    "- For resource utilization, available capacity, or over/under-allocation analysis, use get_resource_capacity_allocation or get_resources_by_portfolio_allocation depending on whether the query is for a single resource or a portfolio.\n"
    "- For project resource planning, gaps, or conflicts, use get_project_resource_allocation.\n"
    "- For business structure, portfolio, or product line information, use get_business_lines or get_strategic_portfolios. For product lines under a portfolio, use get_product_lines_by_portfolio.\n"
    "- For a summary, overview, or list of all projects/resources, use get_all_projects or get_all_resources.\n"
    "- If the user specifies filters (e.g., by status, type, date), use get_projects_dynamic_filter or similar advanced filtering tools.\n"
)

def tool_selection_guide() -> str:
    """
    Guide for selecting the correct MCP tool based on user query context.
    This guide can be used by the client or LLM to select the right tool for the user's request.

    {TOOL_SELECTION_GUIDE}
    """
    return TOOL_SELECTION_GUIDE

mcp = FastMCP("PMO")
mcp.prompt("tool_selection_guide")

# Load metadata from JSON files
PMO_DIR = os.path.dirname(os.path.abspath(__file__))

def load_metadata(filename: str) -> Dict[str, Any]:
    """Load JSON metadata file from metadata directory"""
    metadata_dir = os.path.join(PMO_DIR, "metadata")
    filepath = os.path.join(metadata_dir, filename)
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Metadata file {filename} not found")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing metadata file {filename}: {e}")
        return {}

def get_api_metadata() -> Dict[str, Any]:
    """Load all API metadata for enhanced tool functionality"""
    metadata = {
        "master_index": load_metadata("api_master_index.metadata.json"),
        "projects_api": load_metadata("projects_api.metadata.json"),
        "resources_api": load_metadata("resources_api.metadata.json"),
        "business_lines_api": load_metadata("business_lines_api.metadata.json"),
        "allocations_api": load_metadata("allocations_api.metadata.json"),
        "managers_timeoff_api": load_metadata("managers_timeoff_api.metadata.json"),
        "allocation_actual_import_api": load_metadata("allocation_actual_import_api.metadata.json")
    }
    return metadata

def get_field_info(entity_type: str, field_name: str) -> str:
    """Get field description and constraints from metadata"""
    metadata = get_api_metadata()
    
    # Map entity types to metadata files
    entity_metadata_map = {
        "project": "projects_api",
        "resource": "resources_api", 
        "business_line": "business_lines_api",
        "allocation": "allocations_api",
        "manager": "managers_timeoff_api",
        "timeoff": "managers_timeoff_api"
    }
    
    metadata_key = entity_metadata_map.get(entity_type)
    if not metadata_key:
        return f"Field: {field_name}"
    
    api_metadata = metadata.get(metadata_key, {})
    data_dict = api_metadata.get("data_dictionary", {})
    entity_data = data_dict.get(entity_type, {})
    field_data = entity_data.get(field_name, {})
    
    if field_data:
        description = field_data.get("description", "")
        field_type = field_data.get("type", "")
        constraints = field_data.get("constraints", {})
        business_meaning = field_data.get("business_meaning", "")
        
        info_parts = [f"**{field_name}** ({field_type})"]
        if description:
            info_parts.append(f": {description}")
        if business_meaning:
            info_parts.append(f" | {business_meaning}")
        if constraints:
            constraint_info = []
            if constraints.get("required"):
                constraint_info.append("required")
            if "enum" in constraints:
                constraint_info.append(f"values: {', '.join(constraints['enum'])}")
            if constraint_info:
                info_parts.append(f" | Constraints: {', '.join(constraint_info)}")
        
        return "".join(info_parts)
    
    return f"Field: {field_name}"

# Cache metadata on startup
_METADATA_CACHE = None

def get_cached_metadata() -> Dict[str, Any]:
    """Get cached metadata, loading it if not already cached"""
    global _METADATA_CACHE
    if _METADATA_CACHE is None:
        _METADATA_CACHE = get_api_metadata()
    return _METADATA_CACHE

# ================================================================================
# UTILITY FUNCTIONS
# ================================================================================

def handle_api_error(response, operation_name: str):
    """Centralized error handling for API responses with metadata context"""
    if response.status_code != 200:
        print(f"API Error in {operation_name}: Status {response.status_code}, Response: {response.text}")
        
        # Add metadata context for common errors
        error_context = ""
        if response.status_code == 422:
            error_context = " | Check field constraints in metadata for validation requirements"
        elif response.status_code == 404:
            error_context = " | Resource not found - verify ID exists"
        
        return [{"error": f"API request failed: {response.status_code} - {response.text}{error_context}"}]
    return None

def validate_field_constraints(entity_type: str, field_name: str, value: Any) -> List[str]:
    """Validate field value against metadata constraints"""
    metadata = get_cached_metadata()
    
    # Map entity types to metadata files
    entity_metadata_map = {
        "project": "projects_api",
        "resource": "resources_api", 
        "business_line": "business_lines_api",
        "allocation": "allocations_api"
    }
    
    errors = []
    metadata_key = entity_metadata_map.get(entity_type)
    if not metadata_key:
        return errors
    
    api_metadata = metadata.get(metadata_key, {})
    data_dict = api_metadata.get("data_dictionary", {})
    entity_data = data_dict.get(entity_type, {})
    field_data = entity_data.get(field_name, {})
    constraints = field_data.get("constraints", {})
    
    if constraints:
        # Check required constraint
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"{field_name} is required")
        
        # Check enum constraint
        if "enum" in constraints and value not in constraints["enum"]:
            errors.append(f"{field_name} must be one of: {', '.join(constraints['enum'])}")
        
        # Check string length constraints
        if isinstance(value, str):
            if "max_length" in constraints and len(value) > constraints["max_length"]:
                errors.append(f"{field_name} exceeds maximum length of {constraints['max_length']}")
            if "min_length" in constraints and len(value) < constraints["min_length"]:
                errors.append(f"{field_name} below minimum length of {constraints['min_length']}")
        
        # Check numeric constraints
        if isinstance(value, (int, float)):
            if "min_value" in constraints and value < constraints["min_value"]:
                errors.append(f"{field_name} below minimum value of {constraints['min_value']}")
            if "max_value" in constraints and value > constraints["max_value"]:
                errors.append(f"{field_name} exceeds maximum value of {constraints['max_value']}")
    
    return errors

def get_available_values(entity_type: str, field_name: str) -> List[str]:
    """Get available enum values for a field from metadata"""
    metadata = get_cached_metadata()
    
    entity_metadata_map = {
        "project": "projects_api",
        "resource": "resources_api", 
        "business_line": "business_lines_api",
        "allocation": "allocations_api"
    }
    
    metadata_key = entity_metadata_map.get(entity_type)
    if not metadata_key:
        return []
    
    api_metadata = metadata.get(metadata_key, {})
    data_dict = api_metadata.get("data_dictionary", {})
    entity_data = data_dict.get(entity_type, {})
    field_data = entity_data.get(field_name, {})
    constraints = field_data.get("constraints", {})
    
    return constraints.get("enum", [])

def find_project_by_name(project_name: str) -> Optional[Dict[str, Any]]:
    """Helper function to find a project by name"""
    try:
        projects = get_all_projects()
        if isinstance(projects, list) and len(projects) > 0 and "error" not in projects[0]:
            for project in projects:
                if project.get("project_name", "").lower() == project_name.lower():
                    return project
        return None
    except Exception as e:
        print(f"Error finding project by name: {str(e)}")
        return None

def find_resource_by_name(resource_name: str) -> Optional[Dict[str, Any]]:
    """Helper function to find a resource by name"""
    try:
        resources = get_all_resources()
        if isinstance(resources, list) and len(resources) > 0 and "error" not in resources[0]:
            for resource in resources:
                if resource.get("resource_name", "").lower() == resource_name.lower():
                    return resource
        return None
    except Exception as e:
        print(f"Error finding resource by name: {str(e)}")
        return None

# ================================================================================
# METADATA-DRIVEN DOCUMENTATION TOOLS  
# ================================================================================

@mcp.tool()
def get_api_field_definitions(entity_type: str) -> Dict[str, Any]:
    """
    Get comprehensive field definitions for an entity type from metadata.
    
    Args:
        entity_type: The entity type (project, resource, allocation, business_line, etc.)
        
    Returns detailed field information including constraints, business meaning, and validation rules.
    """
    try:
        metadata = get_cached_metadata()
        
        # Map entity types to metadata files
        entity_metadata_map = {
            "project": "projects_api",
            "resource": "resources_api", 
            "business_line": "business_lines_api",
            "allocation": "allocations_api",
            "manager": "managers_timeoff_api",
            "timeoff": "managers_timeoff_api"
        }
        
        metadata_key = entity_metadata_map.get(entity_type)
        if not metadata_key:
            available_types = list(entity_metadata_map.keys())
            return {
                "error": f"Invalid entity type '{entity_type}'",
                "available_types": available_types
            }
        
        api_metadata = metadata.get(metadata_key, {})
        data_dict = api_metadata.get("data_dictionary", {})
        entity_data = data_dict.get(entity_type, {})
        
        if not entity_data:
            return {"error": f"No field definitions found for entity type '{entity_type}'"}
        
        # Format field definitions for easy consumption
        field_definitions = {}
        for field_name, field_info in entity_data.items():
            field_definitions[field_name] = {
                "description": field_info.get("description", ""),
                "type": field_info.get("type", ""),
                "business_meaning": field_info.get("business_meaning", ""),
                "constraints": field_info.get("constraints", {}),
                "required": field_info.get("constraints", {}).get("required", False),
                "enum_values": field_info.get("constraints", {}).get("enum", [])
            }
        
        return {
            "entity_type": entity_type,
            "metadata_source": metadata_key,
            "total_fields": len(field_definitions),
            "field_definitions": field_definitions
        }
        
    except Exception as e:
        return {"error": f"Error retrieving field definitions: {str(e)}"}

@mcp.tool()
def get_api_endpoints_summary() -> Dict[str, Any]:
    """
    Get a comprehensive summary of all available PMO API endpoints from metadata.
    
    Returns organized information about all endpoints, their purposes, and relationships.
    """
    try:
        metadata = get_cached_metadata()
        master_index = metadata.get("master_index", {})
        
        # Extract endpoint information from all metadata files
        all_endpoints = {}
        categories = {}
        
        metadata_files = master_index.get("metadata_files", {})
        for api_name, api_info in metadata_files.items():
            api_metadata = metadata.get(api_name, {})
            endpoints = api_metadata.get("api_endpoints", {})
            
            for endpoint_path, endpoint_details in endpoints.items():
                all_endpoints[endpoint_path] = {
                    "method": endpoint_details.get("method", "GET"),
                    "summary": endpoint_details.get("summary", ""),
                    "description": endpoint_details.get("description", ""),
                    "business_meaning": endpoint_details.get("business_meaning", ""),
                    "api_category": api_name,
                    "tags": endpoint_details.get("tags", [])
                }
        
        # Get API categories from master index
        api_categories = master_index.get("api_categories", {})
        for category_name, category_info in api_categories.items():
            categories[category_name] = {
                "description": category_info.get("description", ""),
                "business_purpose": category_info.get("business_purpose", ""),
                "key_endpoints": category_info.get("key_endpoints", [])
            }
        
        return {
            "total_endpoints": len(all_endpoints),
            "api_categories": categories,
            "all_endpoints": all_endpoints,
            "base_url": master_index.get("api_service_info", {}).get("base_url", "http://localhost:5000")
        }
        
    except Exception as e:
        return {"error": f"Error retrieving endpoints summary: {str(e)}"}

# ================================================================================
# PROJECT MANAGEMENT TOOLS
# ================================================================================

@mcp.tool()
def get_all_projects() -> List[Dict[str, Any]]:
    """
    Get the full list of all projects with complete details including start/end dates, 
    costs, effort hours, and resource details.
    
    Use this for comprehensive project overviews and when no specific filtering is needed.
    
    Key project fields available (from metadata):
    - project_id: Unique identifier (integer, required)
    - project_name: Display name (string, required) 
    - strategic_portfolio: Business alignment (string, required)
    - product_line: Operational alignment (string, required)
    - project_status: Lifecycle state (Active, Completed, On Hold, Cancelled)
    - start_date/end_date: Project timeline (YYYY-MM-DD format)
    - technology_project: Technology investment flag (Yes/No)
    
    Returns: List of project objects with complete details from PMO API
    """
    try:
        url = f"{api_url}/projects"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_all_projects")
        if error:
            return error
        
        projects = response.json()
        
        # Add metadata context to response
        metadata = get_cached_metadata()
        projects_meta = metadata.get("projects_api", {})
        
        # If it's a successful response, add helpful metadata context
        if isinstance(projects, list) and len(projects) > 0:
            # Add metadata summary as first item for LLM context
            summary = {
                "_metadata_info": {
                    "endpoint": "/projects",
                    "total_projects": len(projects),
                    "available_filters": ["strategic_portfolio", "product_line", "technology_project"],
                    "common_fields": ["project_id", "project_name", "strategic_portfolio", "product_line", "project_status"],
                    "description": projects_meta.get("description", "Project management data")
                }
            }
            return [summary] + projects
        
        return projects
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_project_by_id(project_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its ID.
    
    Args:
        project_id: The unique identifier for the project
        
    Returns detailed project information including timeline, costs, and resource assignments.
    """
    try:
        url = f"{api_url}/projects/{project_id}"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_project_by_id")
        if error:
            return error[0]  # Return single error object, not list
        
        result = response.json()
        # Handle API response format: ensure we return a dict
        if isinstance(result, list) and len(result) > 0:
            return result[0]  # Extract first item from list for Pydantic validation
        elif isinstance(result, dict):
            return result
        else:
            return {"error": "Unexpected response format from API"}
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@mcp.tool()
def get_project_by_name(project_name: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its name.
    
    Args:
        project_name: The name of the project to find
        
    This will search through all projects to find the one with matching name.
    """
    try:
        project = find_project_by_name(project_name)
        if project:
            return project
        else:
            return {"error": f"Project '{project_name}' not found"}
            
    except Exception as e:
        return {"error": f"Error searching for project: {str(e)}"}

@mcp.tool()
def get_projects_by_portfolio_and_product_line(
    strategic_portfolio: Optional[str] = None,
    product_line: Optional[str] = None,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Get projects filtered by strategic portfolio and/or product line.
    
    Args:
        strategic_portfolio: Strategic portfolio to filter by (optional)
        product_line: Product line to filter by (optional)
        fields: Specific fields to return (optional, returns all if not specified)
        
    Note: Values are case-sensitive. Use get_business_lines() to get exact values.
    """
    try:
        filters = []
        if strategic_portfolio:
            filters.append({"column": "strategic_portfolio", "operator": "=", "value": strategic_portfolio})
        if product_line:
            filters.append({"column": "product_line", "operator": "=", "value": product_line})
        
        if not filters:
            return [{"error": "At least one of strategic_portfolio or product_line must be provided"}]
        
        body = {
            "fields": fields or [],
            "filters": filters,
            "logical_operator": "AND"
        }
        
        url = f"{api_url}/projects/dynamic_filter"
        print(f"API Call: POST {url}")
        print(f"Request Body: {json.dumps(body, indent=2)}")
        
        response = requests.post(url, json=body)
        error = handle_api_error(response, "get_projects_by_portfolio_and_product_line")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_projects_dynamic_filter(
    filters: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
    logical_operator: str = "AND"
) -> List[Dict[str, Any]]:
    """
    Advanced project filtering with custom conditions and field selection.
    
    Args:
        filters: List of filter conditions, each with {"column", "operator", "value"}
        fields: Specific fields to return (optional)
        logical_operator: "AND" or "OR" for combining filters
        
    Example filters:
    [{"column": "strategic_portfolio", "operator": "=", "value": "Market & Sell"},
     {"column": "technology_project", "operator": "=", "value": "YES"}]
    """
    try:
        body = {
            "fields": fields or [],
            "filters": filters,
            "logical_operator": logical_operator
        }
        
        url = f"{api_url}/projects/dynamic_filter"
        print(f"API Call: POST {url}")
        print(f"Request Body: {json.dumps(body, indent=2)}")
        
        response = requests.post(url, json=body)
        error = handle_api_error(response, "get_projects_dynamic_filter")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

# ================================================================================
# RESOURCE MANAGEMENT TOOLS
# ================================================================================

@mcp.tool()
def get_all_resources() -> List[Dict[str, Any]]:
    """
    Get complete list of all resources (colleagues/employees) with their details.
    
    Returns information including resource ID, name, email, role, portfolio alignment,
    manager information, and capacity details.
    """
    try:
        url = f"{api_url}/resources"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_all_resources")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_resource_by_id(resource_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific resource by ID.
    
    Args:
        resource_id: The unique identifier for the resource
    """
    try:
        resources = get_all_resources()
        if isinstance(resources, list) and len(resources) > 0 and "error" not in resources[0]:
            for resource in resources:
                if resource.get("resource_id") == resource_id:
                    return resource
            return {"error": f"Resource with ID {resource_id} not found"}
        else:
            return {"error": "Could not retrieve resources list"}
            
    except Exception as e:
        return {"error": f"Error finding resource: {str(e)}"}

@mcp.tool()
def get_resource_by_name(resource_name: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific resource by name.
    
    Args:
        resource_name: The name of the resource to find
    """
    try:
        resource = find_resource_by_name(resource_name)
        if resource:
            return resource
        else:
            return {"error": f"Resource '{resource_name}' not found"}
            
    except Exception as e:
        return {"error": f"Error searching for resource: {str(e)}"}

# ================================================================================
# RESOURCE CAPACITY AND ALLOCATION TOOLS
# ================================================================================

@mcp.tool()
def get_resource_capacity_allocation(
    resource_id: int,
    start_date: str,
    end_date: str,
    interval: Optional[str] = None,
    project_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get total hours and cost for a resource over a given period, with optional intervals.
    
    Args:
        resource_id: Resource ID (get from get_all_resources or get_resource_by_name)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        interval: Optional interval ("Weekly", "Monthly", or None for date blocks)
        project_id: Optional project ID to filter allocation details
        
    Returns structured data with resource_details and time-series allocation data.
    """
    try:
        params = {
            "resource_id": str(resource_id),
            "start_date": start_date,
            "end_date": end_date
        }
        
        if interval:
            params["interval"] = interval
        if project_id:
            params["project_id"] = project_id
            
        url = f"{api_url}/resource_capacity_allocation"
        print(f"API Call: GET {url}")
        print(f"Params: {params}")
        
        response = requests.get(url, params=params)
        error = handle_api_error(response, "get_resource_capacity_allocation")
        if error:
            return error[0]
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@mcp.tool()
def get_project_resource_allocation(
    project_id: Optional[int] = None,
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interval: str = "Monthly"
) -> List[Dict[str, Any]]:
    """
    Get resource allocation details for a specific project.
    
    Args:
        project_id: Project ID (optional if project_name provided)
        project_name: Project name (optional if project_id provided)
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        interval: Interval for data aggregation (default: "Monthly")
        
    You must provide either project_id or project_name.
    """
    try:
        # Resolve project_id if project_name provided
        if project_name and not project_id:
            project = find_project_by_name(project_name)
            if project:
                project_id = project.get("project_id")
            else:
                return [{"error": f"Project '{project_name}' not found"}]
        
        if not project_id:
            return [{"error": "Either project_id or project_name must be provided"}]
        
        params = {"interval": interval}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        url = f"{api_url}/project_capacity_allocation/{project_id}"
        print(f"API Call: GET {url}")
        print(f"Params: {params}")
        
        response = requests.get(url, params=params)
        error = handle_api_error(response, "get_project_resource_allocation")
        if error:
            return error
        
        result = response.json()
        # Handle API response format: ensure we return a list
        if isinstance(result, dict):
            return [result]  # Wrap dict in list for Pydantic validation
        elif isinstance(result, list):
            return result
        else:
            return [{"error": "Unexpected response format from API"}]
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_resources_by_portfolio_allocation(
    strategic_portfolio: Optional[str] = None,
    product_line: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interval: str = "Monthly"
) -> List[Dict[str, Any]]:
    """
    Get resource allocation details for a specific strategic portfolio and/or product line.
    
    Args:
        strategic_portfolio: Strategic portfolio to filter by (optional)
        product_line: Product line to filter by (optional)  
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        interval: Interval for data aggregation (default: "Monthly")
        
    At least one of strategic_portfolio or product_line should be provided.
    """
    try:
        params = {"interval": interval}
        
        if strategic_portfolio:
            params["strategic_portfolio"] = strategic_portfolio
        if product_line:
            params["product_line"] = product_line
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        if not strategic_portfolio and not product_line:
            return [{"error": "At least one of strategic_portfolio or product_line must be provided"}]
            
        url = f"{api_url}/resource_capacity_allocation_per_portfolio"
        print(f"API Call: GET {url}")
        print(f"Params: {params}")
        
        response = requests.get(url, params=params)
        error = handle_api_error(response, "get_resources_by_portfolio_allocation")
        if error:
            return error
        
        api_result = response.json()
        print(f"API Response type: {type(api_result)}")
        print(f"API Response preview: {str(api_result)[:500]}...")
        
        # Handle both list and dict responses from the API
        if isinstance(api_result, list):
            return api_result
        elif isinstance(api_result, dict):
            # If API returns a single dict, wrap it in a list
            return [api_result]
        else:
            return [{"error": f"Unexpected API response format: {type(api_result)}", "debug_value": str(api_result)}]
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

# ================================================================================
# BUSINESS STRUCTURE TOOLS
# ================================================================================

@mcp.tool()
def get_business_lines() -> List[Dict[str, str]]:
    """
    Get the organizational structure including strategic portfolios and product lines.
    
    Use this to get exact case-sensitive values for filtering projects and resources.
    Essential for any portfolio or product line filtering operations.
    """
    try:
        url = f"{api_url}/business_lines"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_business_lines")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_strategic_portfolios() -> List[str]:
    """
    Get list of unique strategic portfolios in the system.
    """
    try:
        url = f"{api_url}/strategic_portfolios"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_strategic_portfolios")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

@mcp.tool()
def get_product_lines_by_portfolio(strategic_portfolio: str) -> List[str]:
    """
    Get product lines for a specific strategic portfolio.
    
    Args:
        strategic_portfolio: The strategic portfolio name (case-sensitive)
    """
    try:
        url = f"{api_url}/product_lines/{quote(strategic_portfolio)}"
        print(f"API Call: GET {url}")
        
        response = requests.get(url)
        error = handle_api_error(response, "get_product_lines_by_portfolio")
        if error:
            return error
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"Network error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]

# ================================================================================
# RESOURCES AND DOCUMENTATION
# ================================================================================

@mcp.resource("pmo://docs/projects_overview")
def projects_overview_doc() -> str:
    """Project API documentation from metadata"""
    metadata = get_cached_metadata()
    projects_meta = metadata.get("projects_api", {})
    
    doc_parts = []
    doc_parts.append("# PMO Projects API Documentation")
    doc_parts.append(f"**Description:** {projects_meta.get('description', 'Project management API endpoints')}")
    
    # Add endpoints info
    endpoints = projects_meta.get("api_endpoints", {})
    if endpoints:
        doc_parts.append("\n## Available Endpoints:")
        for endpoint, details in endpoints.items():
            doc_parts.append(f"- **{details.get('method', 'GET')} {endpoint}**: {details.get('summary', '')}")
    
    # Add key fields from data dictionary
    data_dict = projects_meta.get("data_dictionary", {}).get("project", {})
    if data_dict:
        doc_parts.append("\n## Key Project Fields:")
        for field_name, field_info in list(data_dict.items())[:10]:  # Show first 10 fields
            doc_parts.append(f"- {get_field_info('project', field_name)}")
    
    # Add usage notes
    usage_notes = projects_meta.get("usage_notes", {})
    if usage_notes.get("common_use_cases"):
        doc_parts.append("\n## Common Use Cases:")
        for use_case in usage_notes["common_use_cases"][:3]:  # Show first 3
            doc_parts.append(f"- {use_case}")
    
    return "\n".join(doc_parts)

@mcp.resource("pmo://docs/projects_filtering") 
def projects_filtering_doc() -> str:
    """Project filtering documentation from metadata"""
    metadata = get_cached_metadata()
    projects_meta = metadata.get("projects_api", {})
    
    doc_parts = []
    doc_parts.append("# PMO Projects Filtering Guide")
    
    # Filter endpoints
    endpoints = projects_meta.get("api_endpoints", {})
    filter_endpoints = {k: v for k, v in endpoints.items() if "filter" in k.lower()}
    
    if filter_endpoints:
        doc_parts.append("\n## Filtering Endpoints:")
        for endpoint, details in filter_endpoints.items():
            doc_parts.append(f"### {details.get('method', 'GET')} {endpoint}")
            doc_parts.append(f"{details.get('description', '')}")
            
            # Add parameters if available
            params = details.get("parameters", [])
            if params:
                doc_parts.append("**Parameters:**")
                for param in params:
                    doc_parts.append(f"- {param.get('name', '')}: {param.get('description', '')}")
    
    # Add filtering best practices
    usage_notes = projects_meta.get("usage_notes", {})
    if usage_notes.get("filtering_best_practices"):
        doc_parts.append("\n## Best Practices:")
        for practice in usage_notes["filtering_best_practices"]:
            doc_parts.append(f"- {practice}")
    
    return "\n".join(doc_parts)

@mcp.resource("pmo://docs/resources_overview")
def resources_overview_doc() -> str:
    """Resource API documentation from metadata"""
    metadata = get_cached_metadata()
    resources_meta = metadata.get("resources_api", {})
    
    doc_parts = []
    doc_parts.append("# PMO Resources API Documentation")
    doc_parts.append(f"**Description:** {resources_meta.get('description', 'Resource management API endpoints')}")
    
    # Add endpoints info
    endpoints = resources_meta.get("api_endpoints", {})
    if endpoints:
        doc_parts.append("\n## Available Endpoints:")
        for endpoint, details in endpoints.items():
            doc_parts.append(f"- **{details.get('method', 'GET')} {endpoint}**: {details.get('summary', '')}")
    
    # Add key fields from data dictionary
    data_dict = resources_meta.get("data_dictionary", {}).get("resource", {})
    if data_dict:
        doc_parts.append("\n## Key Resource Fields:")
        for field_name, field_info in list(data_dict.items())[:8]:  # Show first 8 fields
            doc_parts.append(f"- {get_field_info('resource', field_name)}")
    
    return "\n".join(doc_parts)

@mcp.resource("pmo://docs/resource_capacity_allocation")
def resource_capacity_doc() -> str:
    """Resource capacity allocation documentation from metadata"""
    metadata = get_cached_metadata()
    resources_meta = metadata.get("resources_api", {})
    
    doc_parts = []
    doc_parts.append("# PMO Resource Capacity & Allocation Guide")
    
    # Capacity-related endpoints
    endpoints = resources_meta.get("api_endpoints", {})
    capacity_endpoints = {k: v for k, v in endpoints.items() if "capacity" in k.lower() or "allocation" in k.lower()}
    
    if capacity_endpoints:
        doc_parts.append("\n## Capacity & Allocation Endpoints:")
        for endpoint, details in capacity_endpoints.items():
            doc_parts.append(f"### {details.get('method', 'GET')} {endpoint}")
            doc_parts.append(f"{details.get('description', '')}")
    
    # Add capacity-related fields
    data_dict = resources_meta.get("data_dictionary", {})
    capacity_entity = data_dict.get("capacity_allocation", {})
    if capacity_entity:
        doc_parts.append("\n## Capacity Allocation Fields:")
        for field_name, field_info in list(capacity_entity.items())[:6]:
            doc_parts.append(f"- {get_field_info('allocation', field_name)}")
    
    return "\n".join(doc_parts)

@mcp.resource("pmo://docs/organizational_structure")
def organizational_structure_doc() -> str:
    """Organizational structure documentation from metadata"""
    metadata = get_cached_metadata()
    business_meta = metadata.get("business_lines_api", {})
    
    doc_parts = []
    doc_parts.append("# PMO Organizational Structure Guide")
    doc_parts.append(f"**Description:** {business_meta.get('description', 'Organizational hierarchy API endpoints')}")
    
    # Add endpoints info
    endpoints = business_meta.get("api_endpoints", {})
    if endpoints:
        doc_parts.append("\n## Available Endpoints:")
        for endpoint, details in endpoints.items():
            doc_parts.append(f"- **{details.get('method', 'GET')} {endpoint}**: {details.get('summary', '')}")
    
    # Add business rules about hierarchy
    business_rules = business_meta.get("business_rules", {})
    if business_rules.get("relationship_rules"):
        doc_parts.append("\n## Organizational Hierarchy Rules:")
        for rule in business_rules["relationship_rules"]:
            doc_parts.append(f"- {rule}")
    
    return "\n".join(doc_parts)

# ================================================================================
# PROMPTS FOR COMMON USE CASES
# ================================================================================

@mcp.prompt("project_overview")
def project_overview_prompt() -> str:
    return """Generate a comprehensive project overview including:
- Total number of projects
- Projects by strategic portfolio
- Technology vs non-technology projects
- Project status distribution
- Resource allocation summary
Use get_all_projects() and get_business_lines() for this analysis."""

@mcp.prompt("resource_utilization_analysis")
def resource_utilization_prompt() -> str:
    return """Analyze resource utilization by:
- Getting resource list with get_all_resources()
- Analyzing capacity allocation for key resources
- Identifying over/under-allocated resources  
- Providing recommendations for resource optimization
Include specific date ranges for capacity analysis."""

@mcp.prompt("portfolio_deep_dive")
def portfolio_analysis_prompt() -> str:
    return """Provide detailed portfolio analysis:
- Get business lines structure
- Analyze projects by strategic portfolio
- Review resource allocation per portfolio
- Identify portfolio resource constraints
- Suggest portfolio balancing opportunities"""

@mcp.prompt("project_resource_planning")
def project_resource_planning_prompt() -> str:
    return """Create project resource planning analysis:
- Get project details and timelines
- Analyze current resource allocations
- Identify resource gaps or conflicts
- Suggest resource reallocation opportunities
- Provide capacity planning recommendations"""

if __name__ == "__main__":
    mcp.run()