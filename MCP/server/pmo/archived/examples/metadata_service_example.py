"""
PMO API Metadata Service
========================

This service provides centralized access to API metadata for documentation,
validation, and governance purposes. It serves as the foundation for a
comprehensive metadata management system.

Usage:
    from utils.metadata_service import MetadataService
    
    # Initialize service
    metadata_service = MetadataService()
    
    # Get metadata for specific API
    project_metadata = metadata_service.get_api_metadata("projects_api")
    
    # Get endpoint documentation
    endpoint_info = metadata_service.get_endpoint_info("/projects")
    
    # Validate data against schema
    is_valid = metadata_service.validate_response_data("/projects", response_data)
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class MetadataService:
    """Centralized metadata management service for PMO API"""
    
    def __init__(self, metadata_dir: Optional[str] = None):
        """
        Initialize metadata service
        
        Args:
            metadata_dir: Path to metadata directory. If None, uses default location.
        """
        if metadata_dir is None:
            # Default to metadata directory relative to this file
            current_dir = Path(__file__).parent.parent
            self.metadata_dir = current_dir / "metadata"
        else:
            self.metadata_dir = Path(metadata_dir)
            
        self._metadata_cache = {}
        self._master_index = None
        self._load_master_index()
    
    def _load_master_index(self) -> None:
        """Load the master metadata index"""
        try:
            index_path = self.metadata_dir / "api_master_index.metadata.json"
            if index_path.exists():
                with open(index_path, 'r', encoding='utf-8') as f:
                    self._master_index = json.load(f)
            else:
                print(f"Warning: Master index not found at {index_path}")
                self._master_index = {}
        except Exception as e:
            print(f"Error loading master index: {e}")
            self._master_index = {}
    
    def get_api_metadata(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a specific API
        
        Args:
            api_name: Name of the API (e.g., 'projects_api', 'resources_api')
            
        Returns:
            Complete metadata dictionary or None if not found
        """
        if api_name in self._metadata_cache:
            return self._metadata_cache[api_name]
            
        # Check if API exists in master index
        if (self._master_index and 
            "metadata_files" in self._master_index and 
            api_name in self._master_index["metadata_files"]):
            
            file_info = self._master_index["metadata_files"][api_name]
            file_path = self.metadata_dir / file_info["file_path"]
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    self._metadata_cache[api_name] = metadata
                    return metadata
            except Exception as e:
                print(f"Error loading metadata for {api_name}: {e}")
                return None
        
        return None
    
    def get_endpoint_info(self, endpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific endpoint
        
        Args:
            endpoint_path: The endpoint path (e.g., '/projects', '/resources/{resource_id}')
            
        Returns:
            Endpoint information or None if not found
        """
        # Search through all APIs to find the endpoint
        if not self._master_index or "metadata_files" not in self._master_index:
            return None
            
        for api_name, api_info in self._master_index["metadata_files"].items():
            if endpoint_path in api_info.get("endpoints_covered", []):
                metadata = self.get_api_metadata(api_name)
                if metadata and "api_endpoints" in metadata:
                    for endpoint in metadata["api_endpoints"]:
                        if endpoint.get("path") == endpoint_path:
                            return {
                                "api_name": api_name,
                                "endpoint": endpoint,
                                "api_metadata": metadata
                            }
        
        return None
    
    def get_data_dictionary(self, api_name: str, entity_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get data dictionary for an API or specific entity
        
        Args:
            api_name: Name of the API
            entity_name: Optional specific entity name
            
        Returns:
            Data dictionary or None if not found
        """
        metadata = self.get_api_metadata(api_name)
        if not metadata or "data_dictionary" not in metadata:
            return None
            
        data_dict = metadata["data_dictionary"]
        
        if entity_name and entity_name in data_dict:
            return data_dict[entity_name]
        
        return data_dict
    
    def validate_response_data(self, endpoint_path: str, data: Any) -> Dict[str, Any]:
        """
        Validate response data against metadata schema
        
        Args:
            endpoint_path: The endpoint path
            data: Response data to validate
            
        Returns:
            Validation result with status and details
        """
        endpoint_info = self.get_endpoint_info(endpoint_path)
        if not endpoint_info:
            return {
                "valid": False,
                "error": f"No metadata found for endpoint {endpoint_path}"
            }
        
        # Basic validation - can be extended with more sophisticated schema validation
        endpoint = endpoint_info["endpoint"]
        
        try:
            # Check if data structure matches expected format
            if isinstance(data, list):
                if not endpoint.get("returns_array", False):
                    return {
                        "valid": False,
                        "error": "Expected single object but received array"
                    }
            elif isinstance(data, dict):
                if endpoint.get("returns_array", False):
                    return {
                        "valid": False,
                        "error": "Expected array but received single object"
                    }
            
            return {
                "valid": True,
                "message": "Basic validation passed"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }
    
    def get_business_rules(self, api_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get business rules for an API
        
        Args:
            api_name: Name of the API
            
        Returns:
            List of business rules or None if not found
        """
        metadata = self.get_api_metadata(api_name)
        if metadata and "business_rules" in metadata:
            return metadata["business_rules"]
        return None
    
    def get_usage_patterns(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Get usage patterns for an API
        
        Args:
            api_name: Name of the API
            
        Returns:
            Usage patterns or None if not found
        """
        metadata = self.get_api_metadata(api_name)
        if metadata and "usage_patterns" in metadata:
            return metadata["usage_patterns"]
        return None
    
    def list_available_apis(self) -> List[str]:
        """
        Get list of all available APIs
        
        Returns:
            List of API names
        """
        if self._master_index and "metadata_files" in self._master_index:
            return list(self._master_index["metadata_files"].keys())
        return []
    
    def get_api_status(self, api_name: str) -> Optional[str]:
        """
        Get status of an API (active, deprecated, etc.)
        
        Args:
            api_name: Name of the API
            
        Returns:
            Status string or None if not found
        """
        if (self._master_index and 
            "metadata_files" in self._master_index and 
            api_name in self._master_index["metadata_files"]):
            return self._master_index["metadata_files"][api_name].get("status")
        return None
    
    def get_cross_references(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        Find all APIs that reference a specific entity
        
        Args:
            entity_name: Name of the entity to search for
            
        Returns:
            List of API references
        """
        references = []
        
        for api_name in self.list_available_apis():
            metadata = self.get_api_metadata(api_name)
            if metadata:
                # Check in primary entities
                primary_entities = metadata.get("primary_entities", [])
                if entity_name in primary_entities:
                    references.append({
                        "api_name": api_name,
                        "reference_type": "primary_entity",
                        "api_title": metadata.get("title", api_name)
                    })
                
                # Check in data dictionary
                data_dict = metadata.get("data_dictionary", {})
                if entity_name in data_dict:
                    references.append({
                        "api_name": api_name,
                        "reference_type": "data_dictionary",
                        "api_title": metadata.get("title", api_name)
                    })
        
        return references
    
    def get_metadata_health_check(self) -> Dict[str, Any]:
        """
        Perform health check on metadata system
        
        Returns:
            Health check results
        """
        results = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": []
        }
        
        # Check master index
        if not self._master_index:
            results["status"] = "warning"
            results["checks"].append({
                "check": "master_index",
                "status": "failed",
                "message": "Master index not loaded"
            })
        else:
            results["checks"].append({
                "check": "master_index",
                "status": "passed",
                "message": "Master index loaded successfully"
            })
        
        # Check metadata files
        missing_files = []
        if self._master_index and "metadata_files" in self._master_index:
            for api_name, file_info in self._master_index["metadata_files"].items():
                file_path = self.metadata_dir / file_info["file_path"]
                if not file_path.exists():
                    missing_files.append(file_info["file_path"])
        
        if missing_files:
            results["status"] = "error"
            results["checks"].append({
                "check": "metadata_files",
                "status": "failed",
                "message": f"Missing files: {', '.join(missing_files)}"
            })
        else:
            results["checks"].append({
                "check": "metadata_files",
                "status": "passed",
                "message": "All metadata files found"
            })
        
        return results


# Singleton instance for easy import
metadata_service = MetadataService()


# Convenience functions for common operations
def get_api_docs(api_name: str) -> Optional[Dict[str, Any]]:
    """Get API documentation - convenience function"""
    return metadata_service.get_api_metadata(api_name)


def get_endpoint_docs(endpoint_path: str) -> Optional[Dict[str, Any]]:
    """Get endpoint documentation - convenience function"""
    return metadata_service.get_endpoint_info(endpoint_path)


def validate_api_response(endpoint_path: str, data: Any) -> Dict[str, Any]:
    """Validate API response - convenience function"""
    return metadata_service.validate_response_data(endpoint_path, data)


def list_apis() -> List[str]:
    """List all available APIs - convenience function"""
    return metadata_service.list_available_apis()


def health_check() -> Dict[str, Any]:
    """Perform metadata health check - convenience function"""
    return metadata_service.get_metadata_health_check()


if __name__ == "__main__":
    # Example usage and testing
    print("PMO Metadata Service Test")
    print("========================")
    
    # Health check
    health = health_check()
    print(f"Health Status: {health['status']}")
    
    # List APIs
    apis = list_apis()
    print(f"Available APIs: {apis}")
    
    # Get specific API info
    if "projects_api" in apis:
        project_docs = get_api_docs("projects_api")
        if project_docs:
            print(f"Projects API Title: {project_docs.get('title')}")
    
    # Get endpoint info
    endpoint_info = get_endpoint_docs("/projects")
    if endpoint_info:
        print(f"Found endpoint info for /projects in API: {endpoint_info['api_name']}")