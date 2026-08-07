"""
HTTP Client for Metadata Service

Provides HTTP client functionality to interact with the remote metadata service
running at http://localhost:8080. This client handles:
- Fetching metadata by project and object name
- Listing available projects and objects
- Error handling and response validation
"""

import logging
import json
import requests
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MetadataServiceConfig:
    """Configuration for the metadata HTTP service."""
    base_url: str = "http://localhost:8080"
    timeout: int = 30
    retries: int = 3
    verify_ssl: bool = True

@dataclass
class MetadataServiceResponse:
    """Standardized response from metadata service."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    
class MetadataHttpClient:
    """
    HTTP client for interacting with the metadata service API.
    
    This client provides methods to:
    - Get metadata for specific projects and objects
    - List available projects and objects
    - Handle authentication and error responses
    """
    
    def __init__(self, config: Optional[MetadataServiceConfig] = None):
        """Initialize the metadata HTTP client."""
        self.config = config or MetadataServiceConfig()
        self.session = requests.Session()
        self.session.timeout = self.config.timeout
        
        # Configure session headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'nlp-structured-data-client/1.0'
        })
        
        logger.info(f"MetadataHttpClient initialized with base URL: {self.config.base_url}")
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> MetadataServiceResponse:
        """
        Make HTTP request to the metadata service with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: URL parameters
            data: Request body data
            
        Returns:
            MetadataServiceResponse with results or error information
        """
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            # Make the request with retries
            for attempt in range(self.config.retries):
                try:
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data,
                        verify=self.config.verify_ssl
                    )
                    
                    # Log the request for debugging
                    logger.debug(f"HTTP {method} {url} - Status: {response.status_code}")
                    
                    # Handle response
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            
                            # Check for different success indicators
                            is_success = False
                            
                            # Check for explicit 'status': 'success' field
                            if isinstance(response_data, dict) and response_data.get('status') == 'success':
                                is_success = True
                            
                            # Check for health endpoint format
                            elif isinstance(response_data, dict) and response_data.get('status') == 'healthy':
                                is_success = True
                                # Normalize health response to standard format
                                response_data = {
                                    'status': 'success',
                                    'health': response_data
                                }
                            
                            # Check if response looks like valid data (has expected fields)
                            elif isinstance(response_data, dict) and len(response_data) > 0:
                                # If it's not an error response, assume success
                                if 'error' not in response_data and 'message' not in response_data:
                                    is_success = True
                                    # Wrap in standard format
                                    response_data = {
                                        'status': 'success',
                                        'data': response_data
                                    }
                            
                            if is_success:
                                return MetadataServiceResponse(
                                    success=True,
                                    data=response_data,
                                    status_code=response.status_code
                                )
                            else:
                                # Service returned error status
                                error_msg = response_data.get('message', response_data.get('error', 'Unknown service error'))
                                return MetadataServiceResponse(
                                    success=False,
                                    error_message=error_msg,
                                    status_code=response.status_code
                                )
                        except json.JSONDecodeError as e:
                            return MetadataServiceResponse(
                                success=False,
                                error_message=f"Invalid JSON response: {e}",
                                status_code=response.status_code
                            )
                    else:
                        # HTTP error status
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                        return MetadataServiceResponse(
                            success=False,
                            error_message=error_msg,
                            status_code=response.status_code
                        )
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"Request timeout on attempt {attempt + 1}")
                    if attempt == self.config.retries - 1:
                        return MetadataServiceResponse(
                            success=False,
                            error_message="Request timeout after retries"
                        )
                except requests.exceptions.ConnectionError:
                    logger.warning(f"Connection error on attempt {attempt + 1}")
                    if attempt == self.config.retries - 1:
                        return MetadataServiceResponse(
                            success=False,
                            error_message="Failed to connect to metadata service"
                        )
                
        except Exception as e:
            logger.error(f"Unexpected error in HTTP request: {e}")
            return MetadataServiceResponse(
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def get_metadata(self, project_name: str, object_name: str) -> MetadataServiceResponse:
        """
        Get metadata for a specific project and object.
        
        Args:
            project_name: Name of the project (e.g., "Sales")
            object_name: Name of the object (e.g., "sales_data")
            
        Returns:
            MetadataServiceResponse containing the metadata or error information
        """
        params = {
            'project_name': project_name,
            'object_name': object_name
        }
        
        logger.info(f"Fetching metadata for project: {project_name}, object: {object_name}")
        
        response = self._make_request('GET', '/get', params=params)
        
        if response.success:
            logger.info(f"Successfully retrieved metadata for {project_name}/{object_name}")
        else:
            logger.error(f"Failed to retrieve metadata: {response.error_message}")
            
        return response
    
    def list_projects(self) -> MetadataServiceResponse:
        """
        List all available projects in the metadata service.
        
        Returns:
            MetadataServiceResponse containing project list or error information
        """
        logger.info("Fetching list of available projects")
        
        response = self._make_request('GET', '/projects')
        
        if response.success:
            projects = response.data.get('projects', [])
            logger.info(f"Found {len(projects)} projects")
        else:
            logger.error(f"Failed to retrieve projects: {response.error_message}")
            
        return response
    
    def list_objects(self, project_name: Optional[str] = None) -> MetadataServiceResponse:
        """
        List all available objects, optionally filtered by project.
        
        Args:
            project_name: Optional project name to filter objects
            
        Returns:
            MetadataServiceResponse containing object list or error information
        """
        params = {}
        if project_name:
            params['project_name'] = project_name
            
        logger.info(f"Fetching list of objects{' for project: ' + project_name if project_name else ''}")
        
        response = self._make_request('GET', '/objects', params=params)
        
        if response.success:
            objects = response.data.get('objects', [])
            logger.info(f"Found {len(objects)} objects")
        else:
            logger.error(f"Failed to retrieve objects: {response.error_message}")
            
        return response
    
    def check_health(self) -> MetadataServiceResponse:
        """
        Check if the metadata service is healthy and reachable.
        
        Returns:
            MetadataServiceResponse indicating service health
        """
        logger.info("Checking metadata service health")
        
        response = self._make_request('GET', '/health')
        
        if response.success:
            logger.info("Metadata service is healthy")
        else:
            logger.warning(f"Metadata service health check failed: {response.error_message}")
            
        return response
    
    def get_supported_formats(self) -> MetadataServiceResponse:
        """
        Get list of supported file formats from the metadata service.
        
        Returns:
            MetadataServiceResponse containing supported formats
        """
        logger.info("Fetching supported file formats")
        
        response = self._make_request('GET', '/formats')
        
        if response.success:
            formats = response.data.get('formats', [])
            logger.info(f"Service supports {len(formats)} formats")
        else:
            logger.error(f"Failed to retrieve supported formats: {response.error_message}")
            
        return response
    
    def get_metadata_template(self) -> MetadataServiceResponse:
        """
        Get the complete metadata template from the service.
        
        Returns:
            MetadataServiceResponse containing the metadata template
        """
        logger.info("Fetching metadata template")
        
        response = self._make_request('GET', '/template')
        
        if response.success:
            logger.info("Successfully retrieved metadata template")
        else:
            logger.error(f"Failed to retrieve metadata template: {response.error_message}")
            
        return response
    
    def get_format_documentation(self) -> MetadataServiceResponse:
        """
        Get detailed format documentation from the service.
        
        Returns:
            MetadataServiceResponse containing format documentation
        """
        logger.info("Fetching format documentation")
        
        response = self._make_request('GET', '/describe')
        
        if response.success:
            logger.info("Successfully retrieved format documentation")
        else:
            logger.error(f"Failed to retrieve format documentation: {response.error_message}")
            
        return response
    
    def get_format_specific_documentation(self, format_type: str) -> MetadataServiceResponse:
        """
        Get format-specific documentation from the service.
        
        Args:
            format_type: The format type (csv, excel, json, parquet)
            
        Returns:
            MetadataServiceResponse containing format-specific documentation
        """
        logger.info(f"Fetching {format_type} format documentation")
        
        response = self._make_request('GET', f'/describe/{format_type}')
        
        if response.success:
            logger.info(f"Successfully retrieved {format_type} format documentation")
        else:
            logger.error(f"Failed to retrieve {format_type} format documentation: {response.error_message}")
            
        return response
    
    def extract_metadata_content(self, response: MetadataServiceResponse) -> Optional[Dict[str, Any]]:
        """
        Extract the actual metadata content from a successful service response.
        
        Args:
            response: MetadataServiceResponse from get_metadata call
            
        Returns:
            The metadata dictionary or None if extraction failed
        """
        if not response.success or not response.data:
            return None
            
        # Handle different response structures
        response_data = response.data
        
        # If response has a 'data' field, use that
        if 'data' in response_data:
            data_content = response_data['data']
            if isinstance(data_content, dict):
                return data_content
        
        # If response has a 'metadata' field, use that
        if 'metadata' in response_data:
            metadata_content = response_data['metadata']
            if isinstance(metadata_content, dict):
                return metadata_content
        
        # For the actual service response structure we observed,
        # the metadata is directly in the response excluding status and retrieval_info
        filtered_data = {
            k: v for k, v in response_data.items() 
            if k not in ['status', 'retrieval_info', 'health']
        }
        
        # If we have substantial content, return it
        if filtered_data and len(filtered_data) > 0:
            # Check if it looks like metadata (has expected fields)
            expected_fields = ['dataset_info', 'data_dictionary', 'format_specific', 'quality_profile']
            if any(field in filtered_data for field in expected_fields):
                return filtered_data
            
            # If not standard metadata structure, but has content, wrap it
            if len(filtered_data) > 2:  # More than just basic status fields
                return filtered_data
        
        # If all else fails, try to return the full response data
        # (excluding known status fields)
        if isinstance(response_data, dict) and len(response_data) > 1:
            return {k: v for k, v in response_data.items() if k != 'status'}
            
        return None
    
    def parse_project_object_from_path(self, metadata_path: str) -> Optional[Tuple[str, str]]:
        """
        Parse project and object names from a metadata file path.
        
        This method attempts to extract project and object names from paths like:
        - "D:/path/to/metadata_store/Sales/sales_data.metadata.json"
        - "metadata_store/Sales/sales_data.metadata.json"
        - "Sales/sales_data"
        
        Args:
            metadata_path: Path to metadata file or identifier
            
        Returns:
            Tuple of (project_name, object_name) or None if parsing failed
        """
        try:
            # Normalize path separators
            normalized_path = metadata_path.replace('\\', '/').replace('//', '/')
            
            # Remove file extension if present
            if normalized_path.endswith('.metadata.json'):
                normalized_path = normalized_path[:-14]  # Remove .metadata.json
            elif normalized_path.endswith('.json'):
                normalized_path = normalized_path[:-5]   # Remove .json
            
            # Split path into parts
            parts = [part for part in normalized_path.split('/') if part]
            
            if len(parts) >= 2:
                # Look for metadata_store pattern: .../metadata_store/Project/object
                if 'metadata_store' in parts:
                    store_index = parts.index('metadata_store')
                    if len(parts) > store_index + 2:
                        project_name = parts[store_index + 1]
                        object_name = parts[store_index + 2]
                        return (project_name, object_name)
                
                # Simple pattern: Project/object
                project_name = parts[-2]
                object_name = parts[-1]
                return (project_name, object_name)
            
            logger.warning(f"Could not parse project/object from path: {metadata_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing metadata path {metadata_path}: {e}")
            return None
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("HTTP session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()