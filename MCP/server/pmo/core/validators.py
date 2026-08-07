"""
Input validation module for PMO MCP Server.

This module provides comprehensive validation functions for all input types,
including dates, intervals, field constraints, and more.
"""

import re
from datetime import datetime
from typing import Any, List, Optional

from config.settings import get_settings
from core.exceptions import (
    InvalidDateFormatError,
    InvalidIntervalError,
    MissingRequiredFieldError,
    ConstraintViolationError,
    ValidationError
)


class Validator:
    """Main validator class with all validation methods."""

    def __init__(self):
        """Initialize validator with settings."""
        self.settings = get_settings()

    def validate_date(self, date_string: str, field_name: str = "date") -> str:
        """
        Validate date format.

        Args:
            date_string: Date string to validate
            field_name: Name of the field (for error messages)

        Returns:
            Validated date string

        Raises:
            InvalidDateFormatError: If date format is invalid
        """
        if not date_string:
            raise MissingRequiredFieldError(field_name)

        date_format = self.settings.validation.date_format

        try:
            # Try to parse the date
            datetime.strptime(date_string, date_format)
            return date_string
        except ValueError:
            raise InvalidDateFormatError(date_string, "YYYY-MM-DD")

    def validate_optional_date(self, date_string: Optional[str], field_name: str = "date") -> Optional[str]:
        """
        Validate optional date format.

        Args:
            date_string: Date string to validate (can be None)
            field_name: Name of the field (for error messages)

        Returns:
            Validated date string or None

        Raises:
            InvalidDateFormatError: If date format is invalid
        """
        if date_string is None:
            return None
        return self.validate_date(date_string, field_name)

    def validate_interval(self, interval: str) -> str:
        """
        Validate interval value.

        Args:
            interval: Interval value to validate

        Returns:
            Validated interval value

        Raises:
            InvalidIntervalError: If interval is not in allowed list
        """
        allowed_intervals = self.settings.validation.allowed_intervals

        if interval not in allowed_intervals:
            raise InvalidIntervalError(interval, allowed_intervals)

        return interval

    def validate_optional_interval(self, interval: Optional[str]) -> Optional[str]:
        """
        Validate optional interval value.

        Args:
            interval: Interval value to validate (can be None)

        Returns:
            Validated interval value or None

        Raises:
            InvalidIntervalError: If interval is not in allowed list
        """
        if interval is None:
            return None
        return self.validate_interval(interval)

    def validate_required_field(self, value: Any, field_name: str) -> Any:
        """
        Validate that a required field is provided.

        Args:
            value: Field value
            field_name: Name of the field

        Returns:
            The value if valid

        Raises:
            MissingRequiredFieldError: If value is None or empty string
        """
        if value is None or value == "":
            raise MissingRequiredFieldError(field_name)
        return value

    def validate_string_length(
        self,
        value: str,
        field_name: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> str:
        """
        Validate string length constraints.

        Args:
            value: String value to validate
            field_name: Name of the field
            min_length: Minimum allowed length (optional)
            max_length: Maximum allowed length (optional)

        Returns:
            Validated string

        Raises:
            ConstraintViolationError: If length constraints are violated
        """
        if min_length is not None and len(value) < min_length:
            raise ConstraintViolationError(
                field_name=field_name,
                constraint_type="min_length",
                constraint_value=min_length,
                actual_value=len(value)
            )

        if max_length is not None and len(value) > max_length:
            raise ConstraintViolationError(
                field_name=field_name,
                constraint_type="max_length",
                constraint_value=max_length,
                actual_value=len(value)
            )

        return value

    def validate_numeric_range(
        self,
        value: float,
        field_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> float:
        """
        Validate numeric range constraints.

        Args:
            value: Numeric value to validate
            field_name: Name of the field
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)

        Returns:
            Validated numeric value

        Raises:
            ConstraintViolationError: If range constraints are violated
        """
        if min_value is not None and value < min_value:
            raise ConstraintViolationError(
                field_name=field_name,
                constraint_type="min_value",
                constraint_value=min_value,
                actual_value=value
            )

        if max_value is not None and value > max_value:
            raise ConstraintViolationError(
                field_name=field_name,
                constraint_type="max_value",
                constraint_value=max_value,
                actual_value=value
            )

        return value

    def validate_enum(self, value: str, field_name: str, allowed_values: List[str]) -> str:
        """
        Validate enum value.

        Args:
            value: Value to validate
            field_name: Name of the field
            allowed_values: List of allowed values

        Returns:
            Validated value

        Raises:
            ConstraintViolationError: If value is not in allowed list
        """
        if value not in allowed_values:
            raise ConstraintViolationError(
                field_name=field_name,
                constraint_type="enum",
                constraint_value=allowed_values,
                actual_value=value
            )

        return value

    def validate_email(self, email: str, field_name: str = "email") -> str:
        """
        Validate email format.

        Args:
            email: Email address to validate
            field_name: Name of the field

        Returns:
            Validated email

        Raises:
            ValidationError: If email format is invalid
        """
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, email):
            raise ValidationError(
                field_name=field_name,
                message="Invalid email format",
                value=email
            )

        return email

    def validate_positive_integer(self, value: int, field_name: str) -> int:
        """
        Validate that value is a positive integer.

        Args:
            value: Integer value to validate
            field_name: Name of the field

        Returns:
            Validated integer

        Raises:
            ValidationError: If value is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise ValidationError(
                field_name=field_name,
                message="Must be a positive integer",
                value=value
            )

        return value

    def validate_date_range(
        self,
        start_date: str,
        end_date: str,
        start_field_name: str = "start_date",
        end_field_name: str = "end_date"
    ) -> tuple:
        """
        Validate date range (start_date must be before or equal to end_date).

        Args:
            start_date: Start date string
            end_date: End date string
            start_field_name: Name of start date field
            end_field_name: Name of end date field

        Returns:
            Tuple of (validated_start_date, validated_end_date)

        Raises:
            ValidationError: If start_date is after end_date
        """
        # First validate individual dates
        validated_start = self.validate_date(start_date, start_field_name)
        validated_end = self.validate_date(end_date, end_field_name)

        # Parse dates for comparison
        date_format = self.settings.validation.date_format
        start_dt = datetime.strptime(validated_start, date_format)
        end_dt = datetime.strptime(validated_end, date_format)

        if start_dt > end_dt:
            raise ValidationError(
                field_name=start_field_name,
                message="Start date must be before or equal to end date",
                value=start_date
            )

        return validated_start, validated_end

    def validate_filter_operator(self, operator: str) -> str:
        """
        Validate filter operator.

        Args:
            operator: Filter operator to validate

        Returns:
            Validated operator

        Raises:
            ValidationError: If operator is invalid
        """
        valid_operators = ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "NOT IN"]

        if operator not in valid_operators:
            raise ValidationError(
                field_name="operator",
                message=f"Invalid operator. Must be one of: {', '.join(valid_operators)}",
                value=operator
            )

        return operator


# Global validator instance
_validator = None


def get_validator() -> Validator:
    """
    Get the global validator instance.

    Returns:
        Validator instance
    """
    global _validator
    if _validator is None:
        _validator = Validator()
    return _validator
