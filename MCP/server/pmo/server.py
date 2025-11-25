"""
PMO MCP Server - Refactored Version

This is the main entry point for the refactored PMO MCP Server.
It provides a clean, modular, and configurable architecture.
"""

import sys
import logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List

# Add current directory to path for imports
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

# Import configuration
from config import get_settings

# Import utilities
from utils import get_metadata_manager, get_prompt_manager

# Import tool modules
from tools import projects, resources, allocations


# Initialize settings
settings = get_settings()

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.server.log_level),
    format=settings.logging.format
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(settings.server.name)

# Initialize managers
metadata_mgr = get_metadata_manager()
prompt_mgr = get_prompt_manager()

logger.info(f"Initializing PMO MCP Server v{settings.server.version}")


# ================================================================================
# PROJECT TOOLS
# ================================================================================

@mcp.tool()
def get_all_projects() -> List[Dict[str, Any]]:
    """
    Get the full list of all projects with complete details including start/end dates,
    costs, effort hours, and resource details.

    Use this for comprehensive project overviews and when no specific filtering is needed.

    Returns:
        List of project objects with complete details from PMO API
    """
    return projects.get_all_projects()


@mcp.tool()
def get_project_by_id(project_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its ID.

    Args:
        project_id: The unique identifier for the project

    Returns:
        Detailed project information including timeline, costs, and resource assignments
    """
    return projects.get_project_by_id(project_id)


@mcp.tool()
def get_project_by_name(project_name: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its name.

    Args:
        project_name: The name of the project to find

    Returns:
        Project information or error
    """
    return projects.get_project_by_name(project_name)


@mcp.tool()
def get_projects_by_portfolio_and_product_line(
    strategic_portfolio: str = None,
    product_line: str = None,
    fields: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Get projects filtered by strategic portfolio and/or product line.

    Args:
        strategic_portfolio: Strategic portfolio to filter by (optional)
        product_line: Product line to filter by (optional)
        fields: Specific fields to return (optional, returns all if not specified)

    Note: Values are case-sensitive. Use get_business_lines() to get exact values.

    Returns:
        List of filtered projects
    """
    return projects.get_projects_by_portfolio_and_product_line(
        strategic_portfolio, product_line, fields
    )


@mcp.tool()
def get_projects_dynamic_filter(
    filters: List[Dict[str, Any]],
    fields: List[str] = None,
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

    Returns:
        List of filtered projects
    """
    return projects.get_projects_dynamic_filter(filters, fields, logical_operator)


# ================================================================================
# RESOURCE TOOLS
# ================================================================================

@mcp.tool()
def get_all_resources() -> List[Dict[str, Any]]:
    """
    Get complete list of all resources (colleagues/employees) with their details.

    Returns information including resource ID, name, email, role, portfolio alignment,
    manager information, and capacity details.

    Returns:
        List of all resources
    """
    return resources.get_all_resources()


@mcp.tool()
def get_resource_by_id(resource_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific resource by ID.

    Args:
        resource_id: The unique identifier for the resource

    Returns:
        Resource information
    """
    return resources.get_resource_by_id(resource_id)


@mcp.tool()
def get_resource_by_name(resource_name: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific resource by name.

    Args:
        resource_name: The name of the resource to find

    Returns:
        Resource information
    """
    return resources.get_resource_by_name(resource_name)


@mcp.tool()
def get_business_lines() -> List[Dict[str, str]]:
    """
    Get the organizational structure including strategic portfolios and product lines.

    Use this to get exact case-sensitive values for filtering projects and resources.
    Essential for any portfolio or product line filtering operations.

    Returns:
        List of business line mappings
    """
    return resources.get_business_lines()


@mcp.tool()
def get_strategic_portfolios() -> List[str]:
    """
    Get list of unique strategic portfolios in the system.

    Returns:
        List of strategic portfolio names
    """
    return resources.get_strategic_portfolios()


@mcp.tool()
def get_product_lines_by_portfolio(strategic_portfolio: str) -> List[str]:
    """
    Get product lines for a specific strategic portfolio.

    Args:
        strategic_portfolio: The strategic portfolio name (case-sensitive)

    Returns:
        List of product line names
    """
    return resources.get_product_lines_by_portfolio(strategic_portfolio)


# ================================================================================
# ALLOCATION TOOLS
# ================================================================================

@mcp.tool()
def get_resource_capacity_allocation(
    resource_id: int,
    start_date: str,
    end_date: str,
    interval: str = None,
    project_id: int = None
) -> Dict[str, Any]:
    """
    Get total hours and cost for a resource over a given period, with optional intervals.

    Args:
        resource_id: Resource ID (get from get_all_resources or get_resource_by_name)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        interval: Optional interval ("Weekly", "Monthly", or None for date blocks)
        project_id: Optional project ID to filter allocation details

    Returns:
        Resource allocation data with time-series information
    """
    return allocations.get_resource_capacity_allocation(
        resource_id, start_date, end_date, interval, project_id
    )


@mcp.tool()
def get_project_resource_allocation(
    project_id: int = None,
    project_name: str = None,
    start_date: str = None,
    end_date: str = None,
    interval: str = None
) -> List[Dict[str, Any]]:
    """
    Get resource allocation details for a specific project.

    Args:
        project_id: Project ID (optional if project_name provided)
        project_name: Project name (optional if project_id provided)
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        interval: Interval for data aggregation (optional)

    You must provide either project_id or project_name.

    Returns:
        List of resource allocation details for the project
    """
    return allocations.get_project_resource_allocation(
        project_id, project_name, start_date, end_date, interval
    )


@mcp.tool()
def get_resources_by_portfolio_allocation(
    strategic_portfolio: str = None,
    product_line: str = None,
    start_date: str = None,
    end_date: str = None,
    interval: str = None
) -> List[Dict[str, Any]]:
    """
    Get resource allocation details for a specific strategic portfolio and/or product line.

    Args:
        strategic_portfolio: Strategic portfolio to filter by (optional)
        product_line: Product line to filter by (optional)
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        interval: Interval for data aggregation (optional)

    At least one of strategic_portfolio or product_line should be provided.

    Returns:
        List of resource allocation details
    """
    return allocations.get_resources_by_portfolio_allocation(
        strategic_portfolio, product_line, start_date, end_date, interval
    )


# ================================================================================
# METADATA AND DOCUMENTATION TOOLS
# ================================================================================

@mcp.tool()
def get_api_field_definitions(entity_type: str) -> Dict[str, Any]:
    """
    Get comprehensive field definitions for an entity type from metadata.

    Args:
        entity_type: The entity type (project, resource, allocation, business_line, etc.)

    Returns:
        Detailed field information including constraints, business meaning, and validation rules
    """
    try:
        all_metadata = metadata_mgr.load_all_metadata()

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

        api_metadata = all_metadata.get(metadata_key, {})
        data_dict = api_metadata.get("data_dictionary", {})
        entity_data = data_dict.get(entity_type, {})

        if not entity_data:
            return {"error": f"No field definitions found for entity type '{entity_type}'"}

        # Format field definitions
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
        logger.error(f"Error retrieving field definitions: {e}")
        return {"error": f"Error retrieving field definitions: {str(e)}"}


@mcp.tool()
def get_api_endpoints_summary() -> Dict[str, Any]:
    """
    Get a comprehensive summary of all available PMO API endpoints from metadata.

    Returns:
        Organized information about all endpoints, their purposes, and relationships
    """
    try:
        all_metadata = metadata_mgr.load_all_metadata()
        master_index = all_metadata.get("master_index", {})

        # Extract endpoint information
        all_endpoints = {}
        metadata_files = master_index.get("metadata_files", {})

        for api_name, api_info in metadata_files.items():
            api_metadata = all_metadata.get(api_name, {})
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

        # Get API categories
        api_categories = master_index.get("api_categories", {})
        categories = {}
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
            "base_url": master_index.get("api_service_info", {}).get("base_url", settings.api.base_url)
        }

    except Exception as e:
        logger.error(f"Error retrieving endpoints summary: {e}")
        return {"error": f"Error retrieving endpoints summary: {str(e)}"}


# ================================================================================
# PROMPTS
# ================================================================================

@mcp.prompt("tool_selection_guide")
def tool_selection_guide_prompt() -> str:
    """Guide for selecting the correct MCP tool based on user query context."""
    return prompt_mgr.get_tool_selection_guide()


@mcp.prompt("project_overview")
def project_overview_prompt() -> str:
    """Generate a comprehensive project overview."""
    return prompt_mgr.get_prompt("project_overview")


@mcp.prompt("resource_utilization_analysis")
def resource_utilization_prompt() -> str:
    """Analyze resource utilization patterns."""
    return prompt_mgr.get_prompt("resource_utilization_analysis")


@mcp.prompt("portfolio_deep_dive")
def portfolio_analysis_prompt() -> str:
    """Provide detailed portfolio analysis."""
    return prompt_mgr.get_prompt("portfolio_deep_dive")


@mcp.prompt("project_resource_planning")
def project_resource_planning_prompt() -> str:
    """Create project resource planning analysis."""
    return prompt_mgr.get_prompt("project_resource_planning")


@mcp.prompt("chart_generation_guidelines")
def chart_generation_guidelines_prompt() -> str:
    """Best practices for generating charts with data labels and tooltips."""
    return prompt_mgr.get_prompt("chart_generation_guidelines")


# ================================================================================
# MAIN ENTRY POINT
# ================================================================================

if __name__ == "__main__":
    logger.info("Starting PMO MCP Server...")
    logger.info(f"API Base URL: {settings.api.base_url}")
    logger.info(f"Debug Mode: {settings.server.debug}")
    mcp.run()
