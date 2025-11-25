"""
Metadata management utility for PMO MCP Server.

This module handles loading, caching, and accessing metadata from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from core.exceptions import MetadataError


logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata loading, caching, and access.
    """

    def __init__(self):
        """Initialize metadata manager with settings."""
        self.settings = get_settings()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_enabled = self.settings.metadata.cache_enabled

    def _get_metadata_path(self, filename: str) -> Path:
        """
        Get full path to metadata file.

        Args:
            filename: Metadata filename

        Returns:
            Path to metadata file
        """
        return self.settings.get_metadata_path(filename)

    def load_metadata(self, filename: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Load metadata from JSON file.

        Args:
            filename: Name of the metadata file
            use_cache: Whether to use cached data if available

        Returns:
            Metadata dictionary

        Raises:
            MetadataError: If unable to load or parse metadata
        """
        # Check cache first if enabled
        if use_cache and self._cache_enabled and filename in self._cache:
            logger.debug(f"Retrieved metadata from cache: {filename}")
            return self._cache[filename]

        filepath = self._get_metadata_path(filename)

        if not filepath.exists():
            error_msg = f"Metadata file not found: {filename}"
            logger.error(error_msg)
            raise MetadataError(filename, error_msg)

        try:
            with open(filepath, encoding="utf-8") as f:
                metadata = json.load(f)

            # Cache the metadata if caching is enabled
            if self._cache_enabled:
                self._cache[filename] = metadata
                logger.debug(f"Cached metadata: {filename}")

            logger.info(f"Successfully loaded metadata: {filename}")
            return metadata

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in metadata file: {str(e)}"
            logger.error(f"{error_msg} - {filename}")
            raise MetadataError(filename, error_msg)

        except Exception as e:
            error_msg = f"Error loading metadata: {str(e)}"
            logger.error(f"{error_msg} - {filename}")
            raise MetadataError(filename, error_msg)

    def load_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all metadata files.

        Returns:
            Dictionary mapping metadata file keys to their content
        """
        metadata_files = {
            "master_index": "api_master_index.metadata.json",
            "projects_api": "projects_api.metadata.json",
            "resources_api": "resources_api.metadata.json",
            "business_lines_api": "business_lines_api.metadata.json",
            "allocations_api": "allocations_api.metadata.json",
            "managers_timeoff_api": "managers_timeoff_api.metadata.json",
            "allocation_actual_import_api": "allocation_actual_import_api.metadata.json"
        }

        all_metadata = {}
        for key, filename in metadata_files.items():
            try:
                all_metadata[key] = self.load_metadata(filename)
            except MetadataError as e:
                logger.warning(f"Skipping metadata file {filename}: {e}")
                all_metadata[key] = {}

        return all_metadata

    def get_field_info(self, entity_type: str, field_name: str) -> Dict[str, Any]:
        """
        Get field information from metadata.

        Args:
            entity_type: Entity type (project, resource, etc.)
            field_name: Field name

        Returns:
            Dictionary with field information
        """
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
            return {}

        try:
            all_metadata = self.load_all_metadata()
            api_metadata = all_metadata.get(metadata_key, {})
            data_dict = api_metadata.get("data_dictionary", {})
            entity_data = data_dict.get(entity_type, {})
            field_data = entity_data.get(field_name, {})

            return field_data

        except Exception as e:
            logger.error(f"Error getting field info: {e}")
            return {}

    def get_field_description(self, entity_type: str, field_name: str) -> str:
        """
        Get formatted field description for documentation.

        Args:
            entity_type: Entity type (project, resource, etc.)
            field_name: Field name

        Returns:
            Formatted field description
        """
        field_data = self.get_field_info(entity_type, field_name)

        if not field_data:
            return f"Field: {field_name}"

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

    def get_field_constraints(self, entity_type: str, field_name: str) -> Dict[str, Any]:
        """
        Get field constraints from metadata.

        Args:
            entity_type: Entity type
            field_name: Field name

        Returns:
            Dictionary of constraints
        """
        field_data = self.get_field_info(entity_type, field_name)
        return field_data.get("constraints", {})

    def get_available_enum_values(self, entity_type: str, field_name: str) -> List[str]:
        """
        Get available enum values for a field.

        Args:
            entity_type: Entity type
            field_name: Field name

        Returns:
            List of allowed enum values
        """
        constraints = self.get_field_constraints(entity_type, field_name)
        return constraints.get("enum", [])

    def get_api_endpoints(self, api_name: str) -> Dict[str, Any]:
        """
        Get API endpoints from metadata.

        Args:
            api_name: API name (e.g., 'projects_api')

        Returns:
            Dictionary of endpoints
        """
        try:
            all_metadata = self.load_all_metadata()
            api_metadata = all_metadata.get(api_name, {})
            return api_metadata.get("api_endpoints", {})
        except Exception as e:
            logger.error(f"Error getting API endpoints: {e}")
            return {}

    def clear_cache(self):
        """Clear the metadata cache."""
        self._cache.clear()
        logger.info("Metadata cache cleared")

    def reload_metadata(self, filename: Optional[str] = None):
        """
        Reload metadata from files.

        Args:
            filename: Specific file to reload, or None to reload all
        """
        if filename:
            # Remove from cache and reload
            if filename in self._cache:
                del self._cache[filename]
            self.load_metadata(filename, use_cache=False)
            logger.info(f"Reloaded metadata: {filename}")
        else:
            # Clear cache and reload all
            self.clear_cache()
            self.load_all_metadata()
            logger.info("Reloaded all metadata")


# Global metadata manager instance
_metadata_manager = None


def get_metadata_manager() -> MetadataManager:
    """
    Get the global metadata manager instance.

    Returns:
        MetadataManager instance
    """
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataManager()
    return _metadata_manager
