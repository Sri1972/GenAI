"""
Enhanced PMO Tool with Metadata Integration
==========================================

This is an example of how to integrate the metadata service with PMO MCP tools
to provide enriched responses with business context and governance information.
"""

import json
import os
from typing import Any, Dict, List, Optional
import requests
from urllib.parse import quote

# Import our metadata service
try:
    from utils.metadata_service import metadata_service, get_api_docs, validate_api_response
    METADATA_AVAILABLE = True
except ImportError:
    print("Warning: Metadata service not available - falling back to basic mode")
    METADATA_AVAILABLE = False

api_url = "http://localhost:5000"

class EnhancedPMOTool:
    """Enhanced PMO tool with metadata integration"""
    
    def __init__(self):
        self.api_url = api_url
        self.metadata_service = metadata_service if METADATA_AVAILABLE else None
    
    def _enrich_response_with_metadata(self, endpoint: str, data: Any, api_name: str = None) -> Dict[str, Any]:
        """
        Enrich API response with metadata information
        
        Args:
            endpoint: The API endpoint that was called
            data: The response data
            api_name: Optional API name for metadata lookup
            
        Returns:
            Enriched response with metadata context
        """
        enriched = {
            "data": data,
            "metadata_info": {
                "endpoint": endpoint,
                "timestamp": "2025-10-27",
                "has_metadata": False
            }
        }
        
        if not self.metadata_service:
            return enriched
        
        try:
            # Get endpoint information
            endpoint_info = self.metadata_service.get_endpoint_info(endpoint)
            if endpoint_info:
                enriched["metadata_info"]["has_metadata"] = True
                enriched["metadata_info"]["api_name"] = endpoint_info["api_name"]
                enriched["metadata_info"]["documentation"] = f"See metadata: {endpoint_info['api_name']}.metadata.json"
                
                # Add business context
                api_metadata = endpoint_info["api_metadata"]
                if "business_purpose" in api_metadata:
                    enriched["metadata_info"]["business_purpose"] = api_metadata["business_purpose"]
                
                # Add usage notes
                if "usage_patterns" in api_metadata:
                    enriched["metadata_info"]["usage_patterns"] = api_metadata["usage_patterns"]
                
                # Validate response if possible
                validation_result = self.metadata_service.validate_response_data(endpoint, data)
                enriched["metadata_info"]["validation"] = validation_result
            
            # Get business rules if available
            if api_name:
                business_rules = self.metadata_service.get_business_rules(api_name)
                if business_rules:
                    enriched["metadata_info"]["business_rules"] = business_rules
        
        except Exception as e:
            enriched["metadata_info"]["error"] = f"Metadata enrichment failed: {str(e)}"
        
        return enriched
    
    def get_all_projects_enhanced(self) -> Dict[str, Any]:
        """
        Get all projects with metadata enrichment
        
        Returns:
            Enhanced response with project data and metadata context
        """
        try:
            url = f"{self.api_url}/projects"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Enrich with metadata
            enriched = self._enrich_response_with_metadata("/projects", data, "projects_api")
            
            # Add specific project insights from metadata
            if METADATA_AVAILABLE:
                try:
                    project_metadata = get_api_docs("projects_api")
                    if project_metadata:
                        enriched["metadata_info"]["data_governance"] = {
                            "primary_entities": project_metadata.get("primary_entities", []),
                            "data_classification": project_metadata.get("data_classification", {}),
                            "retention_policy": project_metadata.get("retention_policy", {})
                        }
                        
                        # Add field descriptions for user guidance
                        data_dict = project_metadata.get("data_dictionary", {})
                        if "project" in data_dict:
                            enriched["metadata_info"]["field_guide"] = data_dict["project"]
                
                except Exception as e:
                    enriched["metadata_info"]["metadata_warning"] = f"Could not load project metadata: {str(e)}"
            
            return enriched
            
        except requests.exceptions.RequestException as e:
            return {
                "error": f"API request failed: {str(e)}",
                "metadata_info": {
                    "endpoint": "/projects",
                    "error_context": "Network or API error"
                }
            }
    
    def get_resource_capacity_enhanced(self, resource_id: int, start_date: str, end_date: str, 
                                     interval: Optional[str] = None) -> Dict[str, Any]:
        """
        Get resource capacity allocation with metadata enrichment
        
        Args:
            resource_id: ID of the resource
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Optional interval (None for default, "Weekly", "Monthly")
            
        Returns:
            Enhanced response with capacity data and metadata context
        """
        try:
            params = {
                "resource_id": resource_id,
                "start_date": start_date,
                "end_date": end_date
            }
            if interval is not None:
                params["interval"] = interval
                
            url = f"{self.api_url}/resource_capacity_allocation"
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Enrich with metadata
            enriched = self._enrich_response_with_metadata("/resource_capacity_allocation", data, "resources_api")
            
            # Add specific capacity planning insights
            if METADATA_AVAILABLE:
                try:
                    resource_metadata = get_api_docs("resources_api")
                    if resource_metadata:
                        # Add response format information
                        enriched["metadata_info"]["response_format"] = {
                            "structure": "resource_details + data array",
                            "updated_format": True,
                            "description": "New format provides complete resource context with time-series data"
                        }
                        
                        # Add capacity planning guidance
                        usage_patterns = resource_metadata.get("usage_patterns", {})
                        if "capacity_planning" in usage_patterns:
                            enriched["metadata_info"]["planning_guidance"] = usage_patterns["capacity_planning"]
                        
                        # Add business rules for capacity management
                        business_rules = resource_metadata.get("business_rules", [])
                        capacity_rules = [rule for rule in business_rules if "capacity" in rule.get("description", "").lower()]
                        if capacity_rules:
                            enriched["metadata_info"]["capacity_rules"] = capacity_rules
                
                except Exception as e:
                    enriched["metadata_info"]["metadata_warning"] = f"Could not load resource metadata: {str(e)}"
            
            return enriched
            
        except requests.exceptions.RequestException as e:
            return {
                "error": f"API request failed: {str(e)}",
                "metadata_info": {
                    "endpoint": "/resource_capacity_allocation",
                    "error_context": "Network or API error"
                }
            }
    
    def get_business_lines_enhanced(self) -> Dict[str, Any]:
        """
        Get business lines with metadata enrichment
        
        Returns:
            Enhanced response with business lines data and organizational context
        """
        try:
            url = f"{self.api_url}/business_lines"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Enrich with metadata
            enriched = self._enrich_response_with_metadata("/business_lines", data, "business_lines_api")
            
            # Add organizational structure insights
            if METADATA_AVAILABLE:
                try:
                    business_metadata = get_api_docs("business_lines_api")
                    if business_metadata:
                        enriched["metadata_info"]["organizational_context"] = {
                            "hierarchy": "Business Line → Strategic Portfolio → Product Line",
                            "purpose": "Defines organizational structure for resource and project alignment",
                            "case_sensitivity": "All values are case-sensitive for filtering"
                        }
                        
                        # Add related endpoints
                        api_endpoints = business_metadata.get("api_endpoints", [])
                        related_endpoints = [ep.get("path") for ep in api_endpoints if ep.get("path") != "/business_lines"]
                        if related_endpoints:
                            enriched["metadata_info"]["related_endpoints"] = related_endpoints
                
                except Exception as e:
                    enriched["metadata_info"]["metadata_warning"] = f"Could not load business lines metadata: {str(e)}"
            
            return enriched
            
        except requests.exceptions.RequestException as e:
            return {
                "error": f"API request failed: {str(e)}",
                "metadata_info": {
                    "endpoint": "/business_lines",
                    "error_context": "Network or API error"
                }
            }
    
    def get_metadata_health_report(self) -> Dict[str, Any]:
        """
        Get health report of the metadata system
        
        Returns:
            Metadata system health status and information
        """
        if not METADATA_AVAILABLE:
            return {
                "status": "unavailable",
                "message": "Metadata service not imported or available",
                "recommendation": "Check metadata service installation and configuration"
            }
        
        try:
            health_check = self.metadata_service.get_metadata_health_check()
            
            # Add additional PMO-specific checks
            pmo_checks = []
            
            # Check if all PMO APIs have metadata
            expected_apis = ["projects_api", "resources_api", "business_lines_api", "allocations_api"]
            available_apis = self.metadata_service.list_available_apis()
            
            for api in expected_apis:
                if api in available_apis:
                    pmo_checks.append({
                        "check": f"{api}_metadata",
                        "status": "passed",
                        "message": f"{api} metadata available"
                    })
                else:
                    pmo_checks.append({
                        "check": f"{api}_metadata",
                        "status": "failed", 
                        "message": f"{api} metadata missing"
                    })
            
            health_check["pmo_specific_checks"] = pmo_checks
            return health_check
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "recommendation": "Check metadata service configuration and file availability"
            }
    
    def get_cross_reference_report(self, entity_name: str) -> Dict[str, Any]:
        """
        Get cross-reference report for an entity across all APIs
        
        Args:
            entity_name: Name of entity to search for (e.g., "project", "resource")
            
        Returns:
            Cross-reference information across all APIs
        """
        if not METADATA_AVAILABLE:
            return {
                "error": "Metadata service not available",
                "entity": entity_name
            }
        
        try:
            references = self.metadata_service.get_cross_references(entity_name)
            
            return {
                "entity": entity_name,
                "total_references": len(references),
                "references": references,
                "metadata_info": {
                    "purpose": "Shows which APIs use this entity",
                    "usage": "Helpful for understanding data relationships and dependencies"
                }
            }
            
        except Exception as e:
            return {
                "error": f"Cross-reference lookup failed: {str(e)}",
                "entity": entity_name
            }


# Example usage and testing functions
def demo_enhanced_tools():
    """Demonstrate the enhanced PMO tools with metadata integration"""
    print("PMO Enhanced Tools Demo")
    print("======================")
    
    tool = EnhancedPMOTool()
    
    # Test metadata health
    print("\\n1. Metadata Health Check:")
    health = tool.get_metadata_health_report()
    print(f"Status: {health.get('status')}")
    
    # Test business lines with metadata
    print("\\n2. Business Lines (Enhanced):")
    business_lines = tool.get_business_lines_enhanced()
    if "metadata_info" in business_lines:
        print(f"Has Metadata: {business_lines['metadata_info'].get('has_metadata')}")
        if business_lines['metadata_info'].get('has_metadata'):
            print(f"API Name: {business_lines['metadata_info'].get('api_name')}")
    
    # Test cross-references
    print("\\n3. Cross-Reference Report for 'project':")
    cross_ref = tool.get_cross_reference_report("project")
    print(f"Total References: {cross_ref.get('total_references', 0)}")


if __name__ == "__main__":
    demo_enhanced_tools()