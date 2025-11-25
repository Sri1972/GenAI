"""
Custom exceptions for PMO MCP Server.

This module defines all custom exception classes used throughout the application,
providing consistent error handling and meaningful error messages.
"""

from typing import Any, Dict, Optional


class PMOBaseException(Exception):
    """Base exception for all PMO MCP Server errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            details: Additional error details (optional)
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {"error": self.message}
        if self.details:
            result["details"] = self.details
        return result


class ConfigurationError(PMOBaseException):
    """Raised when there's a configuration error."""
    pass


class APIConnectionError(PMOBaseException):
    """Raised when unable to connect to the PMO API."""

    def __init__(self, url: str, message: str = "Failed to connect to PMO API", details: Optional[Dict[str, Any]] = None):
        """
        Initialize API connection error.

        Args:
            url: The API URL that failed
            message: Error message
            details: Additional details
        """
        full_message = f"{message}: {url}"
        super().__init__(full_message, details)
        self.url = url


class APIError(PMOBaseException):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str, response_text: Optional[str] = None):
        """
        Initialize API error.

        Args:
            status_code: HTTP status code
            message: Error message
            response_text: Raw response text from API
        """
        details = {
            "status_code": status_code,
            "response": response_text
        }
        super().__init__(message, details)
        self.status_code = status_code
        self.response_text = response_text


class ValidationError(PMOBaseException):
    """Raised when input validation fails."""

    def __init__(self, field_name: str, message: str, value: Any = None):
        """
        Initialize validation error.

        Args:
            field_name: Name of the field that failed validation
            message: Validation error message
            value: The invalid value (optional)
        """
        full_message = f"Validation failed for '{field_name}': {message}"
        details = {"field": field_name}
        if value is not None:
            details["value"] = value
        super().__init__(full_message, details)
        self.field_name = field_name
        self.value = value


class ResourceNotFoundError(PMOBaseException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, identifier: Any):
        """
        Initialize resource not found error.

        Args:
            resource_type: Type of resource (e.g., 'project', 'resource')
            identifier: The identifier used to search (name, ID, etc.)
        """
        message = f"{resource_type.capitalize()} '{identifier}' not found"
        details = {
            "resource_type": resource_type,
            "identifier": identifier
        }
        super().__init__(message, details)
        self.resource_type = resource_type
        self.identifier = identifier


class MetadataError(PMOBaseException):
    """Raised when there's an error loading or processing metadata."""

    def __init__(self, filename: str, message: str = "Failed to load metadata"):
        """
        Initialize metadata error.

        Args:
            filename: Name of the metadata file
            message: Error message
        """
        full_message = f"{message}: {filename}"
        details = {"filename": filename}
        super().__init__(full_message, details)
        self.filename = filename


class PromptError(PMOBaseException):
    """Raised when there's an error loading or processing prompts."""

    def __init__(self, prompt_name: str, message: str = "Failed to load prompt"):
        """
        Initialize prompt error.

        Args:
            prompt_name: Name of the prompt
            message: Error message
        """
        full_message = f"{message}: {prompt_name}"
        details = {"prompt_name": prompt_name}
        super().__init__(full_message, details)
        self.prompt_name = prompt_name


class InvalidDateFormatError(ValidationError):
    """Raised when a date string has an invalid format."""

    def __init__(self, date_string: str, expected_format: str = "YYYY-MM-DD"):
        """
        Initialize invalid date format error.

        Args:
            date_string: The invalid date string
            expected_format: The expected date format
        """
        message = f"Invalid date format. Expected: {expected_format}"
        super().__init__("date", message, date_string)
        self.expected_format = expected_format


class InvalidIntervalError(ValidationError):
    """Raised when an interval value is invalid."""

    def __init__(self, interval: str, allowed_intervals: list):
        """
        Initialize invalid interval error.

        Args:
            interval: The invalid interval value
            allowed_intervals: List of allowed interval values
        """
        message = f"Must be one of: {', '.join(allowed_intervals)}"
        super().__init__("interval", message, interval)
        self.allowed_intervals = allowed_intervals


class MissingRequiredFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(self, field_name: str):
        """
        Initialize missing required field error.

        Args:
            field_name: Name of the missing field
        """
        message = "This field is required"
        super().__init__(field_name, message)


class ConstraintViolationError(ValidationError):
    """Raised when a field value violates constraints."""

    def __init__(self, field_name: str, constraint_type: str, constraint_value: Any, actual_value: Any):
        """
        Initialize constraint violation error.

        Args:
            field_name: Name of the field
            constraint_type: Type of constraint (e.g., 'max_length', 'min_value')
            constraint_value: The constraint value
            actual_value: The actual value that violated the constraint
        """
        message = f"Violates {constraint_type} constraint: {constraint_value}"
        super().__init__(field_name, message, actual_value)
        self.constraint_type = constraint_type
        self.constraint_value = constraint_value
