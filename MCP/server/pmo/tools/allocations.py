"""
Resource allocation and capacity tools for PMO MCP Server.

This module provides MCP tools for allocation and capacity-related operations.
"""

import logging
from typing import Any, Dict, List, Optional

from core import get_api_client, get_validator
from core.exceptions import PMOBaseException, ResourceNotFoundError
from tools.projects import get_project_by_name
from tools.resources import get_resource_by_name


logger = logging.getLogger(__name__)


def get_resource_capacity_allocation(
    resource_id: int,
    start_date: str,
    end_date: str,
    interval: Optional[str] = None,
    project_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get total hours and cost for a resource over a given period.

    Args:
        resource_id: Resource ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        interval: Optional interval ("Weekly", "Monthly", or None)
        project_id: Optional project ID to filter allocation details

    Returns:
        Resource allocation data
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        # Validate inputs
        validator.validate_positive_integer(resource_id, "resource_id")
        validator.validate_date_range(start_date, end_date)

        if interval:
            validator.validate_interval(interval)

        if project_id:
            validator.validate_positive_integer(project_id, "project_id")

        # Build parameters
        params = {
            "resource_id": str(resource_id),
            "start_date": start_date,
            "end_date": end_date
        }

        if interval:
            params["interval"] = interval
        if project_id:
            params["project_id"] = project_id

        return api_client.get(
            endpoint="/resource_capacity_allocation",
            params=params,
            operation_name="get_resource_capacity_allocation"
        )

    except PMOBaseException as e:
        logger.error(f"Error getting resource capacity allocation: {e}")
        return e.to_dict()
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_project_resource_allocation(
    project_id: Optional[int] = None,
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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

    Returns:
        List of resource allocation details
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        # Resolve project_id if project_name provided
        if project_name and not project_id:
            project = get_project_by_name(project_name)
            if "error" in project:
                return [project]
            project_id = project.get("project_id")

        if not project_id:
            return [{"error": "Either project_id or project_name must be provided"}]

        # Validate inputs
        validator.validate_positive_integer(project_id, "project_id")
        validator.validate_interval(interval)

        if start_date:
            validator.validate_date(start_date, "start_date")
        if end_date:
            validator.validate_date(end_date, "end_date")
        if start_date and end_date:
            validator.validate_date_range(start_date, end_date)

        # Build parameters
        params = {"interval": interval}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        result = api_client.get(
            endpoint=f"/project_capacity_allocation/{project_id}",
            params=params,
            operation_name="get_project_resource_allocation"
        )

        # Handle API response format
        if isinstance(result, dict):
            return [result]
        elif isinstance(result, list):
            return result
        else:
            return [{"error": "Unexpected response format from API"}]

    except PMOBaseException as e:
        logger.error(f"Error getting project resource allocation: {e}")
        return [e.to_dict()]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_resources_by_portfolio_allocation(
    strategic_portfolio: Optional[str] = None,
    product_line: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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

    Returns:
        List of resource allocation details
    """
    try:
        validator = get_validator()
        api_client = get_api_client()

        if not strategic_portfolio and not product_line:
            return [{"error": "At least one of strategic_portfolio or product_line must be provided"}]

        # Validate inputs
        validator.validate_interval(interval)

        if start_date:
            validator.validate_date(start_date, "start_date")
        if end_date:
            validator.validate_date(end_date, "end_date")
        if start_date and end_date:
            validator.validate_date_range(start_date, end_date)

        # Build parameters
        params = {"interval": interval}
        if strategic_portfolio:
            params["strategic_portfolio"] = strategic_portfolio
        if product_line:
            params["product_line"] = product_line
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        api_result = api_client.get(
            endpoint="/resource_capacity_allocation_per_portfolio",
            params=params,
            operation_name="get_resources_by_portfolio_allocation"
        )

        # Handle both list and dict responses
        if isinstance(api_result, list):
            return api_result
        elif isinstance(api_result, dict):
            return [api_result]
        else:
            return [{"error": f"Unexpected API response format: {type(api_result)}"}]

    except PMOBaseException as e:
        logger.error(f"Error getting resources by portfolio allocation: {e}")
        return [e.to_dict()]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]
