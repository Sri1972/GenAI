"""
Project management tools for PMO MCP Server.

This module provides MCP tools for project-related operations.
"""

import logging
from typing import Any, Dict, List, Optional

from core import get_api_client, get_validator
from core.exceptions import PMOBaseException, ResourceNotFoundError
from utils import get_metadata_manager


logger = logging.getLogger(__name__)


def get_all_projects() -> List[Dict[str, Any]]:
    """
    Get the full list of all projects with complete details.

    Returns:
        List of project objects with complete details from PMO API
    """
    try:
        api_client = get_api_client()
        metadata_mgr = get_metadata_manager()

        projects = api_client.get(
            endpoint="/projects",
            operation_name="get_all_projects"
        )

        # Add metadata context to response
        if isinstance(projects, list) and len(projects) > 0:
            all_metadata = metadata_mgr.load_all_metadata()
            projects_meta = all_metadata.get("projects_api", {})

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

    except PMOBaseException as e:
        logger.error(f"Error getting all projects: {e}")
        return [e.to_dict()]
    except Exception as e:
        logger.error(f"Unexpected error in get_all_projects: {e}")
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_project_by_id(project_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its ID.

    Args:
        project_id: The unique identifier for the project

    Returns:
        Detailed project information
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        # Validate project_id
        validator.validate_positive_integer(project_id, "project_id")

        result = api_client.get(
            endpoint=f"/projects/{project_id}",
            operation_name="get_project_by_id"
        )

        # Handle API response format: ensure we return a dict
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result
        else:
            return {"error": "Unexpected response format from API"}

    except PMOBaseException as e:
        logger.error(f"Error getting project by ID: {e}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in get_project_by_id: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


def get_project_by_name(project_name: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific project by its name.

    Args:
        project_name: The name of the project to find

    Returns:
        Project information or error
    """
    try:
        validator = get_validator()

        # Validate project_name
        validator.validate_required_field(project_name, "project_name")

        # Get all projects and search
        projects = get_all_projects()

        if isinstance(projects, list) and len(projects) > 0 and "error" not in projects[0]:
            # Skip metadata info if present
            start_index = 1 if "_metadata_info" in projects[0] else 0

            for project in projects[start_index:]:
                if project.get("project_name", "").lower() == project_name.lower():
                    return project

            raise ResourceNotFoundError("project", project_name)
        else:
            return {"error": "Could not retrieve projects list"}

    except PMOBaseException as e:
        logger.error(f"Error finding project by name: {e}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in get_project_by_name: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


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
        fields: Specific fields to return (optional)

    Returns:
        List of filtered projects
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        filters = []
        if strategic_portfolio:
            validator.validate_required_field(strategic_portfolio, "strategic_portfolio")
            filters.append({"column": "strategic_portfolio", "operator": "=", "value": strategic_portfolio})

        if product_line:
            validator.validate_required_field(product_line, "product_line")
            filters.append({"column": "product_line", "operator": "=", "value": product_line})

        if not filters:
            return [{"error": "At least one of strategic_portfolio or product_line must be provided"}]

        body = {
            "fields": fields or [],
            "filters": filters,
            "logical_operator": "AND"
        }

        result = api_client.post(
            endpoint="/projects/dynamic_filter",
            json_data=body,
            operation_name="get_projects_by_portfolio_and_product_line"
        )

        return result if isinstance(result, list) else [result]

    except PMOBaseException as e:
        logger.error(f"Error filtering projects by portfolio/product line: {e}")
        return [e.to_dict()]
    except Exception as e:
        logger.error(f"Unexpected error in get_projects_by_portfolio_and_product_line: {e}")
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_projects_dynamic_filter(
    filters: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
    logical_operator: str = "AND"
) -> List[Dict[str, Any]]:
    """
    Advanced project filtering with custom conditions and field selection.

    Args:
        filters: List of filter conditions
        fields: Specific fields to return (optional)
        logical_operator: "AND" or "OR" for combining filters

    Returns:
        List of filtered projects
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        # Validate filters structure
        if not filters or not isinstance(filters, list):
            return [{"error": "filters must be a non-empty list"}]

        # Validate each filter has required fields
        for f in filters:
            if not all(k in f for k in ["column", "operator", "value"]):
                return [{"error": "Each filter must have 'column', 'operator', and 'value'"}]
            validator.validate_filter_operator(f["operator"])

        # Validate logical operator
        if logical_operator not in ["AND", "OR"]:
            return [{"error": "logical_operator must be 'AND' or 'OR'"}]

        body = {
            "fields": fields or [],
            "filters": filters,
            "logical_operator": logical_operator
        }

        result = api_client.post(
            endpoint="/projects/dynamic_filter",
            json_data=body,
            operation_name="get_projects_dynamic_filter"
        )

        return result if isinstance(result, list) else [result]

    except PMOBaseException as e:
        logger.error(f"Error with dynamic filter: {e}")
        return [e.to_dict()]
    except Exception as e:
        logger.error(f"Unexpected error in get_projects_dynamic_filter: {e}")
        return [{"error": f"Unexpected error: {str(e)}"}]
