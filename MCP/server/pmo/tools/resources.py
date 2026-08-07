"""
Resource management tools for PMO MCP Server.

This module provides MCP tools for resource-related operations.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from core import get_api_client, get_validator
from core.exceptions import PMOBaseException, ResourceNotFoundError
from utils import get_metadata_manager


logger = logging.getLogger(__name__)


def get_all_resources() -> List[Dict[str, Any]]:
    """Get complete list of all resources with their details."""
    try:
        api_client = get_api_client()
        return api_client.get(endpoint="/resources", operation_name="get_all_resources")
    except PMOBaseException as e:
        logger.error(f"Error getting all resources: {e}")
        return [e.to_dict()]
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_resource_by_id(resource_id: int) -> Dict[str, Any]:
    """Get detailed information for a specific resource by ID."""
    try:
        validator = get_validator()
        validator.validate_positive_integer(resource_id, "resource_id")

        resources = get_all_resources()
        if isinstance(resources, list) and len(resources) > 0 and "error" not in resources[0]:
            for resource in resources:
                if resource.get("resource_id") == resource_id:
                    return resource
            raise ResourceNotFoundError("resource", resource_id)
        else:
            return {"error": "Could not retrieve resources list"}

    except PMOBaseException as e:
        logger.error(f"Error getting resource by ID: {e}")
        return e.to_dict()
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_resource_by_name(resource_name: str) -> Dict[str, Any]:
    """Get detailed information for a specific resource by name."""
    try:
        validator = get_validator()
        validator.validate_required_field(resource_name, "resource_name")

        resources = get_all_resources()
        if isinstance(resources, list) and len(resources) > 0 and "error" not in resources[0]:
            for resource in resources:
                if resource.get("resource_name", "").lower() == resource_name.lower():
                    return resource
            raise ResourceNotFoundError("resource", resource_name)
        else:
            return {"error": "Could not retrieve resources list"}

    except PMOBaseException as e:
        logger.error(f"Error getting resource by name: {e}")
        return e.to_dict()
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_business_lines() -> List[Dict[str, str]]:
    """Get the organizational structure including strategic portfolios and product lines."""
    try:
        api_client = get_api_client()
        return api_client.get(endpoint="/business_lines", operation_name="get_business_lines")
    except PMOBaseException as e:
        logger.error(f"Error getting business lines: {e}")
        return [e.to_dict()]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_strategic_portfolios() -> List[str]:
    """Get list of unique strategic portfolios in the system."""
    try:
        api_client = get_api_client()
        return api_client.get(endpoint="/strategic_portfolios", operation_name="get_strategic_portfolios")
    except PMOBaseException as e:
        logger.error(f"Error getting strategic portfolios: {e}")
        return [e.to_dict()]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_product_lines_by_portfolio(strategic_portfolio: str) -> List[str]:
    """Get product lines for a specific strategic portfolio."""
    try:
        validator = get_validator()
        api_client = get_api_client()

        validator.validate_required_field(strategic_portfolio, "strategic_portfolio")

        return api_client.get(
            endpoint=f"/product_lines/{quote(strategic_portfolio)}",
            operation_name="get_product_lines_by_portfolio"
        )

    except PMOBaseException as e:
        logger.error(f"Error getting product lines: {e}")
        return [e.to_dict()]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]
