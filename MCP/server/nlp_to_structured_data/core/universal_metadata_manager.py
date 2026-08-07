"""
Universal Metadata Management System

A generalized metadata management system that handles all file types through a unified schema
while providing format-specific optimizations and extensibility. Now supports both local 
metadata files and remote HTTP metadata service integration.

Key Features:
- Universal metadata schema that works for any data format
- Format-specific adapters for optimized handling
- Pluggable architecture for easy extension
- Advanced auto-discovery with intelligent format detection
- Schema validation and normalization
- Metadata inheritance and composition
- Version management and change tracking
- HTTP service integration for remote metadata retrieval
"""

import logging
import json
import yaml
import pandas as pd
import os
import re
from typing import Dict, Any, Optional, List, Union, Type, Protocol
from pathlib import Path
import aiofiles
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

# Import the HTTP client
try:
    # Try relative import first (when used as part of package)
    from ..services.metadata_http_client import MetadataHttpClient, MetadataServiceConfig, MetadataServiceResponse
except ImportError:
    # Fall back to absolute import (when used standalone)
    import sys
    from pathlib import Path
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from services.metadata_http_client import MetadataHttpClient, MetadataServiceConfig, MetadataServiceResponse

logger = logging.getLogger(__name__)

class DataFormat(Enum):
    """Supported data formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PARQUET = "parquet"
    XML = "xml"
    YAML = "yaml"
    TSV = "tsv"
    UNKNOWN = "unknown"

@dataclass
class MetadataConfig:
    """Configuration for metadata management."""
    auto_discovery: bool = True
    cache_enabled: bool = True
    validation_enabled: bool = True
    auto_generate_missing: bool = True
    inherit_from_parent: bool = True
    version_tracking: bool = True
    backup_on_save: bool = True
    
    # HTTP service configuration
    use_http_service: bool = False  # Whether to use HTTP metadata service
    http_service_config: Optional[MetadataServiceConfig] = None
    
    # Discovery patterns (for local files)
    discovery_patterns: List[str] = field(default_factory=lambda: [
        "{base_name}.metadata.json",
        "{base_name}.metadata.yaml", 
        "{base_name}_metadata.json",
        "{base_name}.meta.json",
        "metadata.json",
        ".metadata.json"
    ])
    
    # Discovery locations (relative to data file, for local files)
    discovery_paths: List[str] = field(default_factory=lambda: [
        ".",  # Same directory
        "metadata",  # metadata subfolder
        "../metadata",  # parent metadata folder
        "metadata/{format}",  # format-specific subfolder
        "../metadata/{format}",  # parent format-specific subfolder
    ])

class MetadataAdapter(Protocol):
    """Protocol for format-specific metadata adapters."""
    
    def get_format(self) -> DataFormat:
        """Return the data format this adapter handles."""
        ...
    
    async def detect_metadata(self, file_path: str) -> Dict[str, Any]:
        """Detect metadata from the data file itself."""
        ...
    
    def normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize format-specific metadata to universal schema."""
        ...
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """Validate metadata and return list of errors (empty if valid)."""
        ...

class BaseMetadataAdapter(ABC):
    """Base class for metadata adapters."""
    
    @abstractmethod
    def get_format(self) -> DataFormat:
        """Return the data format this adapter handles."""
        pass
    
    @abstractmethod
    async def detect_metadata(self, file_path: str) -> Dict[str, Any]:
        """Detect metadata from the data file itself."""
        pass
    
    def normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Default normalization - can be overridden."""
        return self._to_universal_schema(metadata)
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """Default validation - can be overridden."""
        errors = []
        
        # Basic structure validation
        if not isinstance(metadata, dict):
            errors.append("Metadata must be a dictionary")
            return errors
        
        # Check for required sections in universal schema
        required_sections = ["dataset_info", "data_dictionary"]
        for section in required_sections:
            if section not in metadata:
                errors.append(f"Missing required section: {section}")
        
        return errors
    
    def _to_universal_schema(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert to universal metadata schema."""
        universal = {
            "schema_version": "2.0",
            "created_at": datetime.now().isoformat(),
            "format": self.get_format().value,
            
            # Core sections
            "dataset_info": {
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "version": metadata.get("version", "1.0"),
                "author": metadata.get("author", ""),
                "created_date": metadata.get("created_date", ""),
                "updated_date": metadata.get("updated_date", "")
            },
            
            "source_info": metadata.get("source_info", {}),
            
            "data_dictionary": {
                "columns": metadata.get("data_dictionary", {}).get("columns", {}),
                "relationships": metadata.get("relationships", {}),
                "business_rules": metadata.get("business_rules", {})
            },
            
            "quality_profile": metadata.get("data_quality", {}),
            
            "format_specific": {
                self.get_format().value: metadata.get("format_specific", {}).get(self.get_format().value, {})
            },
            
            "analytics_context": metadata.get("analytics_context", {}),
            "security_classification": metadata.get("security_classification", {}),
            "governance": metadata.get("metadata_management", {}).get("governance", {}),
            
            # Preserve any custom fields
            "extensions": {
                key: value for key, value in metadata.items()
                if key not in [
                    "title", "description", "version", "author", "created_date", "updated_date",
                    "source_info", "data_dictionary", "business_rules", "data_quality",
                    "format_specific", "analytics_context", "security_classification",
                    "metadata_management", "relationships"
                ]
            }
        }
        
        return universal

class CSVMetadataAdapter(BaseMetadataAdapter):
    """Adapter for CSV files."""
    
    def get_format(self) -> DataFormat:
        return DataFormat.CSV
    
    async def detect_metadata(self, file_path: str) -> Dict[str, Any]:
        """Detect metadata from CSV file."""
        try:
            # Sample the CSV to detect structure
            df = pd.read_csv(file_path, nrows=100)  # Sample first 100 rows
            
            detected = {
                "title": f"CSV Data: {Path(file_path).stem}",
                "description": f"Auto-detected CSV file with {len(df.columns)} columns",
                "format_specific": {
                    "csv": {
                        "delimiter": ",",  # Could detect this
                        "header_row": 1,
                        "encoding": "utf-8",
                        "estimated_rows": len(df)
                    }
                },
                "data_dictionary": {
                    "columns": {}
                }
            }
            
            # Detect column metadata
            for col in df.columns:
                col_data = df[col]
                detected["data_dictionary"]["columns"][col] = {
                    "description": f"Column: {col}",
                    "type": self._pandas_to_universal_type(col_data.dtype),
                    "nullable": col_data.isnull().any(),
                    "unique_count": col_data.nunique(),
                    "missing_count": int(col_data.isnull().sum()),
                    "sample_values": col_data.dropna().head(3).tolist(),
                    "aliases": [col.lower(), col.replace("_", " "), col.replace(" ", "_")]
                }
                
                # Add type-specific metadata
                if pd.api.types.is_numeric_dtype(col_data):
                    detected["data_dictionary"]["columns"][col].update({
                        "constraints": {
                            "min_value": float(col_data.min()) if not col_data.empty else None,
                            "max_value": float(col_data.max()) if not col_data.empty else None
                        },
                        "statistics": {
                            "mean": float(col_data.mean()) if not col_data.empty else None,
                            "std": float(col_data.std()) if not col_data.empty else None
                        }
                    })
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting CSV metadata: {e}")
            return {}
    
    def _pandas_to_universal_type(self, dtype) -> str:
        """Convert pandas dtype to universal type."""
        if pd.api.types.is_integer_dtype(dtype):
            return "integer"
        elif pd.api.types.is_float_dtype(dtype):
            return "float"
        elif pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "datetime"
        else:
            return "string"

class ExcelMetadataAdapter(BaseMetadataAdapter):
    """Adapter for Excel files."""
    
    def get_format(self) -> DataFormat:
        return DataFormat.EXCEL
    
    async def detect_metadata(self, file_path: str) -> Dict[str, Any]:
        """Detect metadata from Excel file."""
        try:
            # Get Excel file info
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            # Sample the first sheet
            df = pd.read_excel(file_path, nrows=100)
            
            detected = {
                "title": f"Excel Workbook: {Path(file_path).stem}",
                "description": f"Auto-detected Excel file with {len(sheet_names)} sheets",
                "format_specific": {
                    "excel": {
                        "sheet_names": sheet_names,
                        "default_sheet": sheet_names[0] if sheet_names else None,
                        "estimated_rows": len(df)
                    }
                },
                "data_dictionary": {
                    "columns": {}
                }
            }
            
            # Detect column metadata (similar to CSV)
            for col in df.columns:
                col_data = df[col]
                detected["data_dictionary"]["columns"][col] = {
                    "description": f"Column: {col}",
                    "type": self._pandas_to_universal_type(col_data.dtype),
                    "nullable": col_data.isnull().any(),
                    "unique_count": col_data.nunique(),
                    "missing_count": int(col_data.isnull().sum()),
                    "sample_values": col_data.dropna().head(3).tolist(),
                    "aliases": [col.lower(), col.replace("_", " "), col.replace(" ", "_")]
                }
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting Excel metadata: {e}")
            return {}
    
    def _pandas_to_universal_type(self, dtype) -> str:
        """Convert pandas dtype to universal type."""
        if pd.api.types.is_integer_dtype(dtype):
            return "integer"
        elif pd.api.types.is_float_dtype(dtype):
            return "float"
        elif pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "datetime"
        else:
            return "string"

class JSONMetadataAdapter(BaseMetadataAdapter):
    """Adapter for JSON files."""
    
    def get_format(self) -> DataFormat:
        return DataFormat.JSON
    
    async def detect_metadata(self, file_path: str) -> Dict[str, Any]:
        """Detect metadata from JSON file."""
        try:
            # Sample the JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            detected = {
                "title": f"JSON Data: {Path(file_path).stem}",
                "description": f"Auto-detected JSON file",
                "format_specific": {
                    "json": {
                        "structure": self._detect_json_structure(data),
                        "encoding": "utf-8"
                    }
                },
                "data_dictionary": {
                    "columns": {}
                }
            }
            
            # If it's a list of objects, analyze the structure
            if isinstance(data, list) and data and isinstance(data[0], dict):
                # Analyze first few records
                sample_records = data[:100]
                all_keys = set()
                for record in sample_records:
                    all_keys.update(record.keys())
                
                for key in all_keys:
                    values = [record.get(key) for record in sample_records if key in record]
                    non_null_values = [v for v in values if v is not None]
                    
                    detected["data_dictionary"]["columns"][key] = {
                        "description": f"JSON field: {key}",
                        "type": self._detect_json_type(non_null_values),
                        "nullable": len(non_null_values) < len(values),
                        "sample_values": non_null_values[:3],
                        "aliases": [key.lower(), key.replace("_", " ")]
                    }
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting JSON metadata: {e}")
            return {}
    
    def _detect_json_structure(self, data) -> str:
        """Detect JSON data structure."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return "array_of_objects"
            else:
                return "array"
        elif isinstance(data, dict):
            return "object"
        else:
            return "primitive"
    
    def _detect_json_type(self, values) -> str:
        """Detect type from JSON values."""
        if not values:
            return "unknown"
        
        sample_value = values[0]
        if isinstance(sample_value, bool):
            return "boolean"
        elif isinstance(sample_value, int):
            return "integer"
        elif isinstance(sample_value, float):
            return "float"
        elif isinstance(sample_value, str):
            return "string"
        elif isinstance(sample_value, list):
            return "array"
        elif isinstance(sample_value, dict):
            return "object"
        else:
            return "unknown"

class UniversalMetadataManager:
    """
    Universal metadata management system that handles all data formats
    through a unified schema and pluggable adapter architecture.
    
    Now supports both local metadata files and remote HTTP metadata service.
    """
    
    def __init__(self, config: Optional[MetadataConfig] = None):
        """Initialize the universal metadata manager."""
        self.config = config or MetadataConfig()
        self.adapters: Dict[DataFormat, MetadataAdapter] = {}
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize HTTP client if enabled
        self.http_client: Optional[MetadataHttpClient] = None
        if self.config.use_http_service:
            http_config = self.config.http_service_config or MetadataServiceConfig()
            self.http_client = MetadataHttpClient(http_config)
            logger.info("HTTP metadata service integration enabled")
        
        # Register default adapters
        self._register_default_adapters()
        
        logger.info("UniversalMetadataManager initialized")
    
    def __del__(self):
        """Cleanup resources."""
        if self.http_client:
            self.http_client.close()
    
    def enable_http_service(self, http_config: Optional[MetadataServiceConfig] = None):
        """
        Enable HTTP metadata service integration.
        
        Args:
            http_config: Optional HTTP service configuration
        """
        if self.http_client:
            self.http_client.close()
            
        self.config.use_http_service = True
        self.config.http_service_config = http_config or MetadataServiceConfig()
        self.http_client = MetadataHttpClient(self.config.http_service_config)
        logger.info("HTTP metadata service integration enabled")
    
    def disable_http_service(self):
        """Disable HTTP metadata service integration."""
        if self.http_client:
            self.http_client.close()
            self.http_client = None
            
        self.config.use_http_service = False
        logger.info("HTTP metadata service integration disabled")
    
    def _register_default_adapters(self):
        """Register built-in format adapters."""
        self.register_adapter(CSVMetadataAdapter())
        self.register_adapter(ExcelMetadataAdapter())
        self.register_adapter(JSONMetadataAdapter())
    
    def register_adapter(self, adapter: MetadataAdapter):
        """Register a format-specific adapter."""
        format_type = adapter.get_format()
        self.adapters[format_type] = adapter
        logger.debug(f"Registered adapter for {format_type.value}")
    
    def detect_format(self, file_path: str) -> DataFormat:
        """Detect data format from file extension and content."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        # Map extensions to formats
        extension_map = {
            '.csv': DataFormat.CSV,
            '.tsv': DataFormat.TSV,
            '.xlsx': DataFormat.EXCEL,
            '.xls': DataFormat.EXCEL,
            '.json': DataFormat.JSON,
            '.parquet': DataFormat.PARQUET,
            '.xml': DataFormat.XML,
            '.yaml': DataFormat.YAML,
            '.yml': DataFormat.YAML
        }
        
        return extension_map.get(extension, DataFormat.UNKNOWN)
    
    async def load_metadata(
        self, 
        data_file: Optional[str] = None,
        metadata_file: Optional[str] = None,
        project_name: Optional[str] = None,
        object_name: Optional[str] = None,
        format_hint: Optional[DataFormat] = None,
        force_mode: Optional[str] = None  # 'local', 'http', or None for auto-detect
    ) -> Dict[str, Any]:
        """
        Flexible metadata loading that intelligently determines the source.
        
        This method can load metadata from multiple sources based on the parameters provided:
        1. HTTP Service: When project_name and object_name are provided
        2. HTTP Service: When metadata_file contains a parseable project/object path
        3. Local Files: When data_file and/or metadata_file point to local files
        4. Auto-detection: Tries HTTP service first, then falls back to local files
        
        Args:
            data_file: Path to the data file (for local metadata discovery)
            metadata_file: Can be either:
                          - Local file path (e.g., "/path/to/metadata.json")
                          - Service identifier (e.g., "Sales/sales_data" or "metadata_store/Sales/sales_data.metadata.json")
            project_name: Project name (for HTTP service mode)
            object_name: Object name (for HTTP service mode)
            format_hint: Optional format hint to override detection
            force_mode: Force a specific mode ('local', 'http', or None for auto-detect)
            
        Returns:
            Universal metadata dictionary
        """
        try:
            # Determine the loading strategy based on available parameters and configuration
            loading_strategy = self._determine_loading_strategy(
                data_file, metadata_file, project_name, object_name, force_mode
            )
            
            logger.debug(f"Using loading strategy: {loading_strategy}")
            
            if loading_strategy == "http_direct":
                # Direct HTTP service with explicit project/object
                return await self._load_metadata_from_service(
                    project_name, object_name, format_hint
                )
                
            elif loading_strategy == "http_parsed":
                # HTTP service with parsed project/object from metadata_file
                parsed_project, parsed_object = self._parse_metadata_identifier(metadata_file)
                if parsed_project and parsed_object:
                    return await self._load_metadata_from_service(
                        parsed_project, parsed_object, format_hint
                    )
                else:
                    raise ValueError(f"Could not parse project/object from: {metadata_file}")
                    
            elif loading_strategy == "local":
                # Local file mode
                return await self._load_metadata_from_file(
                    data_file, metadata_file, format_hint
                )
                
            elif loading_strategy == "hybrid":
                # Try HTTP service first, then fall back to local
                return await self._load_metadata_hybrid(
                    data_file, metadata_file, project_name, object_name, format_hint
                )
                
            else:
                raise ValueError(f"Unknown loading strategy: {loading_strategy}")
                
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            # Return minimal metadata as fallback
            return await self._create_fallback_metadata(
                data_file, metadata_file, project_name, object_name, format_hint, str(e)
            )
    
    def _determine_loading_strategy(
        self,
        data_file: Optional[str],
        metadata_file: Optional[str], 
        project_name: Optional[str],
        object_name: Optional[str],
        force_mode: Optional[str]
    ) -> str:
        """
        Intelligently determine the best loading strategy based on available parameters.
        
        Returns:
            Strategy name: 'http_direct', 'http_parsed', 'local', or 'hybrid'
        """
        # Handle forced modes
        if force_mode == "local":
            return "local"
        elif force_mode == "http":
            if project_name and object_name:
                return "http_direct"
            elif metadata_file:
                return "http_parsed"
            else:
                raise ValueError("HTTP mode forced but no project/object or parseable metadata_file provided")
        
        # Auto-detection logic
        
        # 1. If we have explicit project and object names, prefer HTTP service
        if project_name and object_name:
            if self.config.use_http_service and self.http_client:
                return "http_direct"
            else:
                logger.warning("project_name/object_name provided but HTTP service not enabled")
                return "local"  # Fall back to local if HTTP not configured
        
        # 2. If metadata_file looks like a service identifier, try HTTP
        if metadata_file and self.config.use_http_service and self.http_client:
            # Check if metadata_file can be parsed as project/object
            if self._can_parse_as_service_identifier(metadata_file):
                return "http_parsed"
        
        # 3. If metadata_file is a local file path, use local mode
        if metadata_file and self._is_local_file_path(metadata_file):
            return "local"
        
        # 4. If we have data_file, prefer local mode
        if data_file:
            return "local"
        
        # 5. If HTTP service is available and metadata_file could be a service identifier
        if metadata_file and self.config.use_http_service and self.http_client:
            return "hybrid"  # Try HTTP first, fall back to local
        
        # 6. Default to local mode
        return "local"
    
    def _can_parse_as_service_identifier(self, metadata_file: str) -> bool:
        """Check if a metadata_file string can be parsed as a service identifier."""
        try:
            # Try parsing with the HTTP client
            if self.http_client:
                parsed = self.http_client.parse_project_object_from_path(metadata_file)
                return parsed is not None
            
            # Simple heuristics if no HTTP client
            # Service identifiers typically have patterns like:
            # - "project/object"
            # - "metadata_store/project/object.metadata.json"
            # - "project.object"
            
            if '/' in metadata_file:
                parts = metadata_file.split('/')
                # Could be "project/object" or longer path
                return len(parts) >= 2
            elif '.' in metadata_file and not metadata_file.endswith('.json'):
                # Could be "project.object" format
                parts = metadata_file.split('.')
                return len(parts) == 2
            
            return False
        except Exception:
            return False
    
    def _is_local_file_path(self, metadata_file: str) -> bool:
        """Check if metadata_file is a local file path."""
        try:
            path = Path(metadata_file)
            
            # Check if it's an absolute path
            if path.is_absolute():
                return True
            
            # Check if it has file extensions typically used for metadata
            if metadata_file.endswith(('.json', '.yaml', '.yml', '.metadata')):
                return True
            
            # Check if it looks like a relative file path (has directory separators)
            if '\\' in metadata_file or (os.name != 'nt' and '/' in metadata_file):
                return True
            
            # Check if the file actually exists locally
            if path.exists():
                return True
                
            return False
        except Exception:
            return False
    
    def _parse_metadata_identifier(self, identifier: str) -> tuple:
        """Parse metadata identifier into project and object names."""
        if self.http_client:
            parsed = self.http_client.parse_project_object_from_path(identifier)
            if parsed:
                return parsed
        
        # Manual parsing fallback
        if '/' in identifier:
            parts = [p for p in identifier.split('/') if p]
            if len(parts) >= 2:
                return (parts[-2], parts[-1].replace('.metadata.json', '').replace('.json', ''))
        
        if '.' in identifier and not identifier.endswith('.json'):
            parts = identifier.split('.')
            if len(parts) == 2:
                return (parts[0], parts[1])
        
        return (None, None)
    
    async def _load_metadata_hybrid(
        self,
        data_file: Optional[str],
        metadata_file: Optional[str],
        project_name: Optional[str],
        object_name: Optional[str],
        format_hint: Optional[DataFormat]
    ) -> Dict[str, Any]:
        """
        Hybrid loading: Try HTTP service first, fall back to local files.
        """
        try:
            # First, try to use HTTP service
            if self.config.use_http_service and self.http_client:
                # Check service health first
                if self.check_service_health():
                    # Try parsing metadata_file for project/object
                    if metadata_file:
                        parsed_project, parsed_object = self._parse_metadata_identifier(metadata_file)
                        if parsed_project and parsed_object:
                            logger.info(f"Attempting HTTP service: {parsed_project}/{parsed_object}")
                            return await self._load_metadata_from_service(
                                parsed_project, parsed_object, format_hint
                            )
                    
                    # Try explicit project/object if provided
                    if project_name and object_name:
                        logger.info(f"Attempting HTTP service: {project_name}/{object_name}")
                        return await self._load_metadata_from_service(
                            project_name, object_name, format_hint
                        )
                else:
                    logger.warning("HTTP service not healthy, falling back to local files")
        except Exception as e:
            logger.warning(f"HTTP service failed: {e}, falling back to local files")
        
        # Fall back to local file loading
        logger.info("Falling back to local file loading")
        return await self._load_metadata_from_file(data_file, metadata_file, format_hint)
    
    async def _create_fallback_metadata(
        self,
        data_file: Optional[str],
        metadata_file: Optional[str],
        project_name: Optional[str],
        object_name: Optional[str],
        format_hint: Optional[DataFormat],
        error_message: str
    ) -> Dict[str, Any]:
        """Create fallback metadata when all loading methods fail."""
        if data_file:
            detected_format = format_hint or self.detect_format(data_file)
            metadata = self._create_minimal_metadata(data_file, detected_format)
        elif project_name and object_name:
            metadata = self._create_minimal_metadata_for_service(
                project_name, object_name, format_hint or DataFormat.UNKNOWN
            )
        elif metadata_file:
            # Try to extract information from metadata_file
            parsed_project, parsed_object = self._parse_metadata_identifier(metadata_file)
            if parsed_project and parsed_object:
                metadata = self._create_minimal_metadata_for_service(
                    parsed_project, parsed_object, format_hint or DataFormat.UNKNOWN
                )
            else:
                # Treat as a local file reference
                metadata = {
                    "schema_version": "2.0",
                    "created_at": datetime.now().isoformat(),
                    "format": (format_hint or DataFormat.UNKNOWN).value,
                    "dataset_info": {
                        "title": Path(metadata_file).stem if metadata_file else "Unknown",
                        "description": "Fallback metadata - original loading failed"
                    },
                    "data_dictionary": {"columns": {}},
                    "management": {
                        "source": "fallback",
                        "auto_generated": True,
                        "minimal": True,
                        "error": error_message
                    }
                }
        else:
            # No useful information available
            metadata = {
                "schema_version": "2.0",
                "created_at": datetime.now().isoformat(),
                "format": (format_hint or DataFormat.UNKNOWN).value,
                "dataset_info": {
                    "title": "Unknown Dataset",
                    "description": "Fallback metadata - no source information available"
                },
                "data_dictionary": {"columns": {}},
                "management": {
                    "source": "fallback",
                    "auto_generated": True,
                    "minimal": True,
                    "error": error_message
                }
            }
        
        return metadata
    
    async def _load_metadata_from_service(
        self,
        project_name: str,
        object_name: str,
        format_hint: Optional[DataFormat] = None
    ) -> Dict[str, Any]:
        """Load metadata from HTTP service."""
        # Check cache first
        cache_key = f"service:{project_name}:{object_name}"
        if self.config.cache_enabled and cache_key in self.metadata_cache:
            logger.debug(f"Using cached metadata for {project_name}/{object_name}")
            return self.metadata_cache[cache_key]
        
        # Fetch from HTTP service
        logger.info(f"Fetching metadata from service: {project_name}/{object_name}")
        response = self.http_client.get_metadata(project_name, object_name)
        
        if not response.success:
            raise Exception(f"Failed to fetch metadata: {response.error_message}")
        
        # Extract metadata content
        metadata = self.http_client.extract_metadata_content(response)
        if not metadata:
            raise Exception("No metadata content found in service response")
        
        # Enhance metadata with missing aliases for better query matching
        metadata = self._enhance_metadata_aliases(metadata)
        
        # The service returns already structured metadata, but we may need to normalize it
        # to our universal schema if it's in a different format
        
        # Add management metadata
        metadata["management"] = metadata.get("management", {})
        metadata["management"].update({
            "loaded_at": datetime.now().isoformat(),
            "source": "http_service",
            "project_name": project_name,
            "object_name": object_name,
            "service_url": self.http_client.config.base_url,
            "schema_version": "2.0"
        })
        
        # Validate if enabled
        if self.config.validation_enabled:
            errors = self._validate_universal_metadata(metadata)
            if errors:
                logger.warning(f"Metadata validation errors: {errors}")
        
        # Cache the result
        if self.config.cache_enabled:
            self.metadata_cache[cache_key] = metadata
        
        logger.info(f"Successfully loaded metadata from service: {project_name}/{object_name}")
        return metadata
    
    async def _load_metadata_from_file(
        self, 
        data_file: Optional[str] = None, 
        metadata_file: Optional[str] = None,
        format_hint: Optional[DataFormat] = None
    ) -> Dict[str, Any]:
        """Load metadata from local files (original implementation)."""
        # If no data_file provided, try to infer from metadata_file or create minimal
        if not data_file:
            if metadata_file:
                # Try to use metadata_file as a local file reference
                logger.debug(f"No data_file provided, using metadata_file as reference: {metadata_file}")
                # Create minimal metadata based on metadata_file
                return self._create_minimal_metadata_from_metadata_file(metadata_file, format_hint)
            else:
                raise ValueError("Either data_file or metadata_file must be provided for local file loading")
        
        # Check cache first
        cache_key = f"{data_file}:{metadata_file or 'auto'}"
        if self.config.cache_enabled and cache_key in self.metadata_cache:
            logger.debug(f"Using cached metadata for {data_file}")
            return self.metadata_cache[cache_key]
        
        # Detect format
        detected_format = format_hint or self.detect_format(data_file)
        logger.debug(f"Detected format: {detected_format.value}")
        
        # Initialize metadata with auto-detection
        metadata = await self._auto_detect_metadata(data_file, detected_format)
        
        # Load external metadata if available
        external_metadata = {}
        if metadata_file:
            external_metadata = await self._load_external_metadata(metadata_file)
        elif self.config.auto_discovery:
            external_metadata = await self._discover_external_metadata(data_file, detected_format)
        
        # Merge metadata (external takes priority)
        if external_metadata:
            metadata = self._merge_metadata(metadata, external_metadata)
            logger.debug("Merged auto-detected and external metadata")
        
        # Normalize to universal schema
        if detected_format in self.adapters:
            adapter = self.adapters[detected_format]
            metadata = adapter.normalize_metadata(metadata)
        
        # Validate if enabled
        if self.config.validation_enabled:
            errors = self._validate_universal_metadata(metadata)
            if errors:
                logger.warning(f"Metadata validation errors: {errors}")
        
        # Add management metadata
        metadata["management"] = {
            "loaded_at": datetime.now().isoformat(),
            "source": "local_file",
            "source_file": data_file,
            "metadata_file": metadata_file,
            "auto_detected": bool(metadata_file is None),
            "format": detected_format.value,
            "schema_version": "2.0"
        }
        
        # Cache the result
        if self.config.cache_enabled:
            self.metadata_cache[cache_key] = metadata
        
        return metadata
    
    def _create_minimal_metadata_from_metadata_file(
        self,
        metadata_file: str,
        format_hint: Optional[DataFormat]
    ) -> Dict[str, Any]:
        """Create minimal metadata when only metadata_file is available for local mode."""
        from pathlib import Path
        
        # Try to extract meaningful info from metadata_file path
        path = Path(metadata_file)
        title = path.stem
        
        # Remove common metadata file suffixes
        if title.endswith('.metadata'):
            title = title[:-9]
        
        detected_format = format_hint or DataFormat.UNKNOWN
        
        return {
            "schema_version": "2.0",
            "created_at": datetime.now().isoformat(),
            "format": detected_format.value,
            "dataset_info": {
                "title": title,
                "description": f"Minimal metadata from metadata file reference: {metadata_file}",
                "metadata_file": metadata_file
            },
            "data_dictionary": {
                "columns": {}
            },
            "management": {
                "source": "local_file",
                "auto_generated": True,
                "minimal": True,
                "note": "Created from metadata_file reference only (no data_file provided)"
            }
        }
    
    async def _auto_detect_metadata(self, data_file: str, format_type: DataFormat) -> Dict[str, Any]:
        """Auto-detect metadata from the data file itself."""
        if format_type in self.adapters:
            adapter = self.adapters[format_type]
            return await adapter.detect_metadata(data_file)
        else:
            logger.warning(f"No adapter for format {format_type.value}")
            return {}
    
    async def _discover_external_metadata(self, data_file: str, format_type: DataFormat) -> Dict[str, Any]:
        """Discover external metadata files using configured patterns."""
        data_path = Path(data_file)
        base_name = data_path.stem
        data_dir = data_path.parent
        
        # Try each discovery path
        for path_pattern in self.config.discovery_paths:
            # Resolve path pattern
            search_dir = data_dir
            if path_pattern != ".":
                # Replace format placeholder
                resolved_pattern = path_pattern.replace("{format}", format_type.value)
                search_dir = data_dir / resolved_pattern
            
            if not search_dir.exists():
                continue
            
            # Try each filename pattern
            for filename_pattern in self.config.discovery_patterns:
                # Replace placeholders
                filename = filename_pattern.replace("{base_name}", base_name)
                metadata_path = search_dir / filename
                
                if metadata_path.exists():
                    logger.debug(f"Found metadata file: {metadata_path}")
                    return await self._load_external_metadata(str(metadata_path))
        
        logger.debug("No external metadata file found during discovery")
        return {}
    
    async def _load_external_metadata(self, metadata_file: str) -> Dict[str, Any]:
        """Load metadata from external file."""
        metadata_path = Path(metadata_file)
        
        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            return {}
        
        try:
            async with aiofiles.open(metadata_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Determine format and parse
            extension = metadata_path.suffix.lower()
            
            if extension in ['.json', '.metadata']:
                return json.loads(content)
            elif extension in ['.yaml', '.yml']:
                return yaml.safe_load(content)
            else:
                logger.warning(f"Unsupported metadata format: {extension}")
                return {}
                
        except (json.JSONDecodeError, yaml.YAMLError, Exception) as e:
            logger.error(f"Error parsing metadata file {metadata_file}: {e}")
            return {}
    
    def _merge_metadata(self, auto_detected: Dict[str, Any], external: Dict[str, Any]) -> Dict[str, Any]:
        """Merge auto-detected and external metadata (external takes priority)."""
        merged = auto_detected.copy()
        
        # Deep merge with external taking priority
        for key, value in external.items():
            if key == "data_dictionary" and key in merged:
                # Special handling for data dictionary
                merged_dict = merged[key].copy()
                
                if "columns" in value and "columns" in merged_dict:
                    merged_columns = merged_dict["columns"].copy()
                    for col_name, col_meta in value["columns"].items():
                        if col_name in merged_columns:
                            # Merge column metadata
                            merged_columns[col_name].update(col_meta)
                        else:
                            merged_columns[col_name] = col_meta
                    merged_dict["columns"] = merged_columns
                
                # Merge other data_dictionary sections
                for subkey, subvalue in value.items():
                    if subkey != "columns":
                        merged_dict[subkey] = subvalue
                
                merged[key] = merged_dict
            else:
                # For other keys, external takes full priority
                merged[key] = value
        
        return merged
    
    def _enhance_metadata_aliases(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance metadata by adding default aliases when they're missing.
        
        This is particularly useful for HTTP service responses that may not
        include comprehensive aliases for natural language query matching.
        
        Args:
            metadata: The metadata dictionary to enhance
            
        Returns:
            Enhanced metadata with aliases added to columns
        """
        if "data_dictionary" not in metadata or "columns" not in metadata["data_dictionary"]:
            return metadata
        
        columns = metadata["data_dictionary"]["columns"]
        
        for column_name, column_meta in columns.items():
            # Skip if aliases already exist and are not empty
            if column_meta.get("aliases") and len(column_meta["aliases"]) > 0:
                continue
            
            # Generate aliases based on column name and business meaning
            aliases = self._generate_column_aliases(column_name, column_meta)
            
            if aliases:
                column_meta["aliases"] = aliases
                logger.debug(f"Added aliases for column '{column_name}': {aliases}")
        
        return metadata
    
    def _generate_column_aliases(self, column_name: str, column_meta: Dict[str, Any]) -> List[str]:
        """
        Generate aliases for a column based on its name and metadata.
        
        Args:
            column_name: The actual column name
            column_meta: The column metadata dictionary
            
        Returns:
            List of alias strings for the column
        """
        aliases = []
        
        # Start with variations of the column name
        col_lower = column_name.lower()
        
        # Add the column name itself (in lowercase)
        aliases.append(col_lower)
        
        # Add variations based on common naming patterns
        if "_" in col_lower:
            # For snake_case: add space-separated version
            space_version = col_lower.replace("_", " ")
            aliases.append(space_version)
            
            # Add individual words
            words = col_lower.split("_")
            aliases.extend(words)
            
            # Add combinations
            if len(words) > 1:
                aliases.append(" ".join(words))
        
        # Add camelCase variations
        if any(c.isupper() for c in column_name):
            # Split camelCase
            import re
            words = re.findall(r'[A-Z][a-z]*|[a-z]+', column_name)
            if len(words) > 1:
                aliases.append(" ".join(word.lower() for word in words))
                aliases.extend([word.lower() for word in words])
        
        # Add business meaning if available
        business_meaning = column_meta.get("business_meaning", "")
        if business_meaning:
            business_lower = business_meaning.lower()
            aliases.append(business_lower)
            
            # Extract keywords from business meaning
            business_words = re.findall(r'\b\w+\b', business_lower)
            aliases.extend([word for word in business_words if len(word) > 2])
        
        # Add business_name if available (alternative to business_meaning)
        business_name = column_meta.get("business_name", "")
        if business_name:
            aliases.append(business_name.lower())
        
        # Add description words if available
        description = column_meta.get("description", "")
        if description:
            # Extract key words from description
            desc_words = re.findall(r'\b\w+\b', description.lower())
            key_words = [word for word in desc_words if len(word) > 3 and 
                        word not in ['this', 'that', 'with', 'from', 'data', 'field', 'column']]
            aliases.extend(key_words[:3])  # Limit to 3 key words
        
        # Add common aliases based on column type and common patterns
        type_aliases = self._get_type_based_aliases(column_name, column_meta)
        aliases.extend(type_aliases)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_aliases = []
        for alias in aliases:
            if alias and alias not in seen and alias != column_name:
                seen.add(alias)
                unique_aliases.append(alias)
        
        return unique_aliases[:10]  # Limit to 10 aliases max
    
    def _get_type_based_aliases(self, column_name: str, column_meta: Dict[str, Any]) -> List[str]:
        """Get common aliases based on column name patterns and data types."""
        aliases = []
        col_lower = column_name.lower()
        
        # Common patterns for different types of columns
        if any(term in col_lower for term in ['id', 'key', 'code']):
            aliases.extend(['id', 'identifier', 'key', 'code'])
        
        if any(term in col_lower for term in ['name', 'title']):
            aliases.extend(['name', 'title', 'label'])
        
        if any(term in col_lower for term in ['amount', 'total', 'price', 'cost', 'value']):
            aliases.extend(['amount', 'total', 'value', 'price', 'cost', 'revenue', 'money'])
        
        if any(term in col_lower for term in ['date', 'time', 'created', 'updated']):
            aliases.extend(['date', 'time', 'timestamp', 'when'])
        
        if any(term in col_lower for term in ['customer', 'client']):
            aliases.extend(['customer', 'client', 'account'])
        
        if any(term in col_lower for term in ['product', 'item']):
            aliases.extend(['product', 'item', 'merchandise'])
        
        if any(term in col_lower for term in ['sales', 'rep', 'representative']):
            aliases.extend(['sales rep', 'representative', 'salesperson', 'rep'])
        
        if any(term in col_lower for term in ['quantity', 'qty', 'count']):
            aliases.extend(['quantity', 'qty', 'count', 'number'])
        
        return aliases
    
    def _validate_universal_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """Validate metadata against universal schema."""
        errors = []
        
        # Check required top-level sections
        required_sections = ["dataset_info", "data_dictionary"]
        for section in required_sections:
            if section not in metadata:
                errors.append(f"Missing required section: {section}")
        
        # Validate data_dictionary.columns if present
        if "data_dictionary" in metadata and "columns" in metadata["data_dictionary"]:
            columns = metadata["data_dictionary"]["columns"]
            if not isinstance(columns, dict):
                errors.append("data_dictionary.columns must be a dictionary")
            else:
                for col_name, col_meta in columns.items():
                    if not isinstance(col_meta, dict):
                        errors.append(f"Column '{col_name}' metadata must be a dictionary")
        
        return errors
    
    def _create_minimal_metadata(self, data_file: str, format_type: DataFormat) -> Dict[str, Any]:
        """Create minimal metadata when loading fails."""
        return {
            "schema_version": "2.0",
            "created_at": datetime.now().isoformat(),
            "format": format_type.value,
            "dataset_info": {
                "title": Path(data_file).stem,
                "description": f"Minimal metadata for {format_type.value} file",
                "source_file": data_file
            },
            "data_dictionary": {
                "columns": {}
            },
            "management": {
                "source": "local_file",
                "auto_generated": True,
                "minimal": True,
                "error": "Failed to load comprehensive metadata"
            }
        }
    
    def _create_minimal_metadata_for_service(
        self, 
        project_name: str, 
        object_name: str, 
        format_type: DataFormat
    ) -> Dict[str, Any]:
        """Create minimal metadata for service objects when loading fails."""
        return {
            "schema_version": "2.0",
            "created_at": datetime.now().isoformat(),
            "format": format_type.value,
            "dataset_info": {
                "title": object_name,
                "description": f"Minimal metadata for {format_type.value} object",
                "project_name": project_name,
                "object_name": object_name
            },
            "data_dictionary": {
                "columns": {}
            },
            "management": {
                "source": "http_service",
                "auto_generated": True,
                "minimal": True,
                "error": "Failed to load comprehensive metadata"
            }
        }
    
    async def save_metadata(
        self, 
        data_file: str, 
        metadata: Dict[str, Any], 
        metadata_file: Optional[str] = None,
        format_type: DataFormat = DataFormat.JSON
    ) -> bool:
        """Save metadata to file with versioning and backup."""
        try:
            if not metadata_file:
                # Generate default metadata file name
                data_path = Path(data_file)
                metadata_file = str(data_path.parent / f"{data_path.stem}.metadata.json")
            
            metadata_path = Path(metadata_file)
            
            # Backup existing file if enabled
            if self.config.backup_on_save and metadata_path.exists():
                backup_path = metadata_path.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup")
                metadata_path.rename(backup_path)
                logger.debug(f"Backed up existing metadata to {backup_path}")
            
            # Ensure directory exists
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add save metadata
            metadata_to_save = metadata.copy()
            metadata_to_save["management"] = metadata_to_save.get("management", {})
            metadata_to_save["management"].update({
                "saved_at": datetime.now().isoformat(),
                "schema_version": "2.0"
            })
            
            # Add version tracking if enabled
            if self.config.version_tracking:
                version_history = metadata_to_save.get("version_history", [])
                version_history.append({
                    "version": f"1.{len(version_history)}",
                    "timestamp": datetime.now().isoformat(),
                    "action": "save"
                })
                metadata_to_save["version_history"] = version_history
            
            # Save based on format
            if format_type == DataFormat.JSON:
                async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(metadata_to_save, indent=2, ensure_ascii=False))
            elif format_type == DataFormat.YAML:
                async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
                    await f.write(yaml.dump(metadata_to_save, default_flow_style=False))
            
            logger.info(f"Metadata saved to {metadata_file}")
            
            # Update cache
            if self.config.cache_enabled:
                cache_key = f"{data_file}:{metadata_file}"
                self.metadata_cache[cache_key] = metadata_to_save
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving metadata for {data_file}: {e}")
            return False
    
    def get_column_aliases(self, metadata: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract all column aliases from metadata."""
        aliases = {}
        
        columns = metadata.get("data_dictionary", {}).get("columns", {})
        for col_name, col_meta in columns.items():
            if "aliases" in col_meta and isinstance(col_meta["aliases"], list):
                aliases[col_name] = col_meta["aliases"]
        
        return aliases
    
    def find_column_by_alias(self, alias: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Find actual column name by alias."""
        columns = metadata.get("data_dictionary", {}).get("columns", {})
        
        for col_name, col_meta in columns.items():
            # Check exact match first
            if col_name.lower() == alias.lower():
                return col_name
            
            # Check aliases
            if "aliases" in col_meta:
                for col_alias in col_meta["aliases"]:
                    if col_alias.lower() == alias.lower():
                        return col_name
                    # Partial matching
                    if alias.lower() in col_alias.lower():
                        return col_name
        
        return None
    
    def clear_cache(self):
        """Clear the metadata cache."""
        self.metadata_cache.clear()
        logger.debug("Metadata cache cleared")
    
    def get_supported_formats(self) -> List[DataFormat]:
        """Get list of supported data formats."""
        return list(self.adapters.keys())
    
    def get_adapter(self, format_type: DataFormat) -> Optional[MetadataAdapter]:
        """Get adapter for specific format."""
        return self.adapters.get(format_type)
    
    # HTTP Service specific methods
    
    def list_projects(self) -> Optional[List[Dict[str, Any]]]:
        """
        List all available projects from the HTTP metadata service.
        
        Returns:
            List of project dictionaries or None if service not available
        """
        if not self.http_client:
            logger.warning("HTTP service not enabled")
            return None
            
        response = self.http_client.list_projects()
        if response.success:
            return response.data.get('projects', [])
        else:
            logger.error(f"Failed to list projects: {response.error_message}")
            return None
    
    def list_objects(self, project_name: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        List all available objects from the HTTP metadata service.
        
        Args:
            project_name: Optional project name to filter objects
            
        Returns:
            List of object dictionaries or None if service not available
        """
        if not self.http_client:
            logger.warning("HTTP service not enabled")
            return None
            
        response = self.http_client.list_objects(project_name)
        if response.success:
            return response.data.get('objects', [])
        else:
            logger.error(f"Failed to list objects: {response.error_message}")
            return None
    
    def check_service_health(self) -> bool:
        """
        Check if the HTTP metadata service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.http_client:
            logger.warning("HTTP service not enabled")
            return False
            
        response = self.http_client.check_health()
        return response.success
    
    def get_service_supported_formats(self) -> Optional[List[str]]:
        """
        Get supported formats from the HTTP metadata service.
        
        Returns:
            List of supported format strings or None if service not available
        """
        if not self.http_client:
            logger.warning("HTTP service not enabled")
            return None
            
        response = self.http_client.get_supported_formats()
        if response.success:
            return response.data.get('formats', [])
        else:
            logger.error(f"Failed to get supported formats: {response.error_message}")
            return None
    
    async def load_metadata_by_project_object(
        self,
        project_name: str,
        object_name: str,
        format_hint: Optional[DataFormat] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to load metadata by project and object name.
        
        Args:
            project_name: Name of the project
            object_name: Name of the object
            format_hint: Optional format hint
            
        Returns:
            Metadata dictionary
        """
        return await self.load_metadata(
            project_name=project_name,
            object_name=object_name,
            format_hint=format_hint
        )
    
    def parse_metadata_identifier(self, identifier: str) -> Optional[tuple]:
        """
        Parse a metadata identifier into project and object names.
        
        Supports formats like:
        - "project_name/object_name"
        - "project_name.object_name"
        - "/path/to/metadata_store/project_name/object_name.metadata.json"
        
        Args:
            identifier: Metadata identifier string
            
        Returns:
            Tuple of (project_name, object_name) or None if parsing failed
        """
        if not self.http_client:
            return None
            
        # Try parsing as file path first
        parsed = self.http_client.parse_project_object_from_path(identifier)
        if parsed:
            return parsed
        
        # Try simple project/object or project.object formats
        if '/' in identifier:
            parts = identifier.split('/')
            if len(parts) == 2:
                return (parts[0], parts[1])
        elif '.' in identifier:
            parts = identifier.split('.')
            if len(parts) == 2:
                return (parts[0], parts[1])
        
        logger.warning(f"Could not parse metadata identifier: {identifier}")
        return None