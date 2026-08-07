"""
API client for PMO MCP Server.

This module provides a robust HTTP client for communicating with the PMO API,
with retry logic, timeout handling, and comprehensive error handling.
"""

import requests
import time
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from config.settings import get_settings
from core.exceptions import (
    APIConnectionError,
    APIError,
    PMOBaseException
)


logger = logging.getLogger(__name__)


class PMOAPIClient:
    """
    HTTP client for PMO API with robust error handling and retry logic.
    """

    def __init__(self):
        """Initialize the API client with settings."""
        self.settings = get_settings()
        self.base_url = self.settings.api.base_url
        self.timeout = self.settings.api.timeout
        self.retry_attempts = self.settings.api.retry_attempts
        self.retry_delay = self.settings.api.retry_delay

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        # Remove leading slash if present to avoid double slashes
        endpoint = endpoint.lstrip('/')
        return urljoin(self.base_url, endpoint)

    def _handle_response(self, response: requests.Response, operation_name: str) -> Any:
        """
        Handle API response and raise appropriate exceptions.

        Args:
            response: HTTP response object
            operation_name: Name of the operation (for logging)

        Returns:
            Parsed JSON response

        Raises:
            APIError: If the API returns an error status code
        """
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise APIError(
                    status_code=response.status_code,
                    message="Invalid JSON response from API",
                    response_text=response.text
                )

        # Handle error responses
        error_message = self._get_error_message(response)
        logger.error(f"API Error in {operation_name}: Status {response.status_code}, Message: {error_message}")

        raise APIError(
            status_code=response.status_code,
            message=error_message,
            response_text=response.text
        )

    def _get_error_message(self, response: requests.Response) -> str:
        """
        Extract error message from response.

        Args:
            response: HTTP response object

        Returns:
            Error message string
        """
        if response.status_code == 404:
            return "Resource not found"
        elif response.status_code == 422:
            return f"Validation error: {response.text}"
        elif response.status_code == 500:
            return "Internal server error"
        elif response.status_code == 503:
            return "Service unavailable"
        else:
            return f"API request failed with status {response.status_code}"

    def _make_request_with_retry(
        self,
        method: str,
        url: str,
        operation_name: str,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            operation_name: Operation name for logging
            **kwargs: Additional arguments for requests

        Returns:
            HTTP response object

        Raises:
            APIConnectionError: If unable to connect after retries
        """
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"API Call (attempt {attempt + 1}/{self.retry_attempts}): {method} {url}")

                response = requests.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )

                return response

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error on attempt {attempt + 1}/{self.retry_attempts}: {e}")

                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise APIConnectionError(
                        url=url,
                        message="Failed to connect to PMO API after retries",
                        details={"attempts": self.retry_attempts, "error": str(e)}
                    )

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.retry_attempts}: {e}")

                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise APIConnectionError(
                        url=url,
                        message=f"API request timed out after {self.timeout}s",
                        details={"timeout": self.timeout, "error": str(e)}
                    )

            except requests.exceptions.RequestException as e:
                logger.error(f"Request exception: {e}")
                raise APIConnectionError(
                    url=url,
                    message="Network error occurred",
                    details={"error": str(e)}
                )

        # This should never be reached, but just in case
        if last_exception:
            raise APIConnectionError(
                url=url,
                message="Failed to complete request",
                details={"error": str(last_exception)}
            )

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "API GET"
    ) -> Any:
        """
        Make GET request to API.

        Args:
            endpoint: API endpoint
            params: Query parameters (optional)
            operation_name: Operation name for logging

        Returns:
            Parsed JSON response

        Raises:
            APIConnectionError: If unable to connect
            APIError: If the API returns an error
        """
        url = self._build_url(endpoint)
        logger.info(f"{operation_name}: GET {endpoint}")

        if params:
            logger.debug(f"Query params: {params}")

        response = self._make_request_with_retry(
            method="GET",
            url=url,
            operation_name=operation_name,
            params=params
        )

        return self._handle_response(response, operation_name)

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "API POST"
    ) -> Any:
        """
        Make POST request to API.

        Args:
            endpoint: API endpoint
            json_data: JSON body data (optional)
            params: Query parameters (optional)
            operation_name: Operation name for logging

        Returns:
            Parsed JSON response

        Raises:
            APIConnectionError: If unable to connect
            APIError: If the API returns an error
        """
        url = self._build_url(endpoint)
        logger.info(f"{operation_name}: POST {endpoint}")

        if json_data:
            logger.debug(f"Request body: {json_data}")
        if params:
            logger.debug(f"Query params: {params}")

        response = self._make_request_with_retry(
            method="POST",
            url=url,
            operation_name=operation_name,
            json=json_data,
            params=params
        )

        return self._handle_response(response, operation_name)

    def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "API PUT"
    ) -> Any:
        """
        Make PUT request to API.

        Args:
            endpoint: API endpoint
            json_data: JSON body data (optional)
            params: Query parameters (optional)
            operation_name: Operation name for logging

        Returns:
            Parsed JSON response

        Raises:
            APIConnectionError: If unable to connect
            APIError: If the API returns an error
        """
        url = self._build_url(endpoint)
        logger.info(f"{operation_name}: PUT {endpoint}")

        if json_data:
            logger.debug(f"Request body: {json_data}")

        response = self._make_request_with_retry(
            method="PUT",
            url=url,
            operation_name=operation_name,
            json=json_data,
            params=params
        )

        return self._handle_response(response, operation_name)

    def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "API DELETE"
    ) -> Any:
        """
        Make DELETE request to API.

        Args:
            endpoint: API endpoint
            params: Query parameters (optional)
            operation_name: Operation name for logging

        Returns:
            Parsed JSON response

        Raises:
            APIConnectionError: If unable to connect
            APIError: If the API returns an error
        """
        url = self._build_url(endpoint)
        logger.info(f"{operation_name}: DELETE {endpoint}")

        response = self._make_request_with_retry(
            method="DELETE",
            url=url,
            operation_name=operation_name,
            params=params
        )

        return self._handle_response(response, operation_name)


# Global API client instance
_api_client = None


def get_api_client() -> PMOAPIClient:
    """
    Get the global API client instance.

    Returns:
        PMOAPIClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = PMOAPIClient()
    return _api_client
