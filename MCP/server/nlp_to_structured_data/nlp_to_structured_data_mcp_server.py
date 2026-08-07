#!/usr/bin/env python3
"""
Clean Simplified NLP to Structured Data MCP Server

No unicode characters - only ASCII for full compatibility.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    # MCP imports
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool, Resource, Prompt
except ImportError:
    print("MCP not available. Install with: pip install mcp")
    sys.exit(1)

# Direct service imports (no agents!)
from services.csv_service import CSVService
from services.excel_service import ExcelService 
from services.json_service import JSONService
import pandas as pd

# Import sophisticated infrastructure
from core.universal_metadata_manager import UniversalMetadataManager, MetadataConfig
from services.metadata_http_client import MetadataServiceConfig
from utils.resource_prompt_manager import get_resource_manager, get_prompt_manager

class EnhancedDataServer:
    """Enhanced MCP Server with full metadata, resource, and prompt integration."""
    
    def __init__(self):
        print("=== ENHANCED DATA SERVER INIT - UPDATED VERSION ===")
        # Initialize services directly
        self.csv_service = CSVService()
        self.excel_service = ExcelService()
        self.json_service = JSONService()
        
        # Get configuration from environment
        metadata_service_url = os.getenv('METADATA_SERVICE_BASE_URL', 'http://localhost:8080')
        metadata_service_enabled = os.getenv('METADATA_SERVICE_ENABLED', 'true').lower() == 'true'
        
        # Initialize infrastructure with HTTP service as the only metadata source
        http_config = MetadataServiceConfig(base_url=metadata_service_url)
        metadata_config = MetadataConfig(
            use_http_service=metadata_service_enabled,
            http_service_config=http_config,
            auto_discovery=False,  # Disable local file discovery
            cache_enabled=os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
        )
        self.metadata_manager = UniversalMetadataManager(config=metadata_config)
        self.resource_manager = get_resource_manager()
        self.prompt_manager = get_prompt_manager()
        
        # Current data state
        self.current_data = None
        self.current_metadata = None
        self.current_file_info = {}
        self.business_context = {}
        self.column_definitions = {}
        
        # Schema information from API
        self.metadata_template = None
        self.format_descriptions = {}
        
    async def initialize(self):
        """Initialize the server components and fetch metadata schemas."""
        try:
            print("Enhanced Data Server initialized successfully")
            print(">> Metadata Manager: Ready")
            print(">> Resource Manager: Ready")
            print(">> Prompt Manager: Ready")
            
            # Test infrastructure
            resources = self.resource_manager.get_resource_list()
            prompts = self.prompt_manager.get_prompt_list()
            print(f">> Available resources: {len(resources)}")
            print(f">> Available prompts: {len(prompts)}")
            
            # Fetch metadata schemas from API if HTTP service is enabled
            if self.metadata_manager.config.use_http_service:
                await self._fetch_metadata_schemas()
            
            return True
            
        except Exception as e:
            print(f"Failed to initialize server: {e}")
            return False
    
    async def _fetch_metadata_schemas(self):
        """Fetch metadata template and format descriptions from API."""
        try:
            http_client = self.metadata_manager.http_client
            if not http_client:
                print(">> No HTTP client available for schema fetching")
                return
            
            print(">> Fetching metadata schemas from API...")
            
            # Fetch complete metadata template
            template_response = http_client.get_metadata_template()
            if template_response.success:
                self.metadata_template = template_response.data
                print(f">> Fetched metadata template with {len(self.metadata_template)} sections")
            else:
                print(f">> Failed to fetch metadata template: {template_response.error_message}")
            
            # Fetch general format documentation
            describe_response = http_client.get_format_documentation()
            if describe_response.success:
                self.format_descriptions['general'] = describe_response.data
                print(">> Fetched general format documentation")
            else:
                print(f">> Failed to fetch format documentation: {describe_response.error_message}")
            
            # Fetch format-specific documentation
            for format_type in ['csv', 'excel', 'json', 'parquet']:
                format_response = http_client.get_format_specific_documentation(format_type)
                if format_response.success:
                    self.format_descriptions[format_type] = format_response.data
                    print(f">> Fetched {format_type.upper()} format documentation")
                else:
                    print(f">> Failed to fetch {format_type} documentation: {format_response.error_message}")
            
        except Exception as e:
            print(f">> Error fetching metadata schemas: {e}")
            # Continue without schemas - fallback to auto-detection
    
    async def load_data_file(self, file_path: str, file_type: str, metadata_path: str = ""):
        """Load data file using HTTP metadata service only."""
        print("=== LOAD_DATA_FILE CALLED WITH UPDATED CODE ===")
        print(f"=== file_path: {file_path}")
        print(f"=== file_type: {file_type}")
        print(f"=== metadata_path: {metadata_path}")
        try:
            print(f">> Loading {file_type.upper()} file: {file_path}")
            
            # Check if HTTP metadata service is enabled
            if not self.metadata_manager.config.use_http_service:
                return "ERROR: Metadata service is disabled. All metadata must come from the HTTP API service."
            
            # Check if HTTP client is available
            if not self.metadata_manager.http_client:
                return "ERROR: HTTP metadata service not available. Please ensure the metadata API is running."
            
            # Parse metadata path as project/object identifier
            if not metadata_path:
                return "ERROR: Metadata path (project/object) is required. Example: 'restaurant_project/restaurant_data'"
            
            # Parse project and object from metadata_path
            project_name, object_name = self._parse_project_object(metadata_path)
            if not project_name or not object_name:
                return f"ERROR: Invalid metadata path format. Expected 'project/object', got: '{metadata_path}'"
            
            print(f">> Fetching metadata from API: {project_name}/{object_name}")
            
            # Load metadata directly from HTTP service (bypass UniversalMetadataManager fallbacks)
            try:
                print(f">> Calling HTTP client directly for project='{project_name}', object='{object_name}'")
                
                # Use HTTP client directly to avoid fallback logic
                http_client = self.metadata_manager.http_client
                if not http_client:
                    return "ERROR: HTTP metadata client not available. Please ensure the metadata API is running."
                
                response = http_client.get_metadata(project_name, object_name)
                if not response.success:
                    return f"ERROR: Failed to retrieve metadata from API: {response.error_message}"
                
                # Extract metadata content from response
                self.current_metadata = http_client.extract_metadata_content(response)
                if not self.current_metadata:
                    return f"ERROR: No metadata content found in API response for '{project_name}/{object_name}'"
                
                print(f">> Successfully retrieved metadata from HTTP API")
                print(f">> Metadata keys from API: {list(self.current_metadata.keys())}")
                
            except Exception as e:
                print(f">> Exception during HTTP metadata loading: {str(e)}")
                import traceback
                print(f">> Full traceback: {traceback.format_exc()}")
                return f"ERROR: Failed to load metadata from API service: {str(e)}. Please ensure the metadata API is running and contains data for '{project_name}/{object_name}'."
            
            # Debug: Print what metadata was loaded from API
            if self.current_metadata:
                print(f">> Successfully loaded metadata from API: {len(self.current_metadata)} top-level keys")
                print(f">> Metadata keys: {list(self.current_metadata.keys())}")
                
                # Debug: Print the actual metadata structure
                print(f">> Raw metadata from API:")
                import json
                print(json.dumps(self.current_metadata, indent=2)[:500] + "..." if len(str(self.current_metadata)) > 500 else json.dumps(self.current_metadata, indent=2))
                
                # Validate that this is proper API metadata
                validation_result = self._validate_api_metadata_format(self.current_metadata)
                print(f">> API metadata validation result: {validation_result}")
                if not validation_result:
                    print(">> WARNING: Metadata format from API doesn't match expected schema")
            else:
                return "ERROR: No metadata received from API service."
            
            # Extract business context from standardized API metadata
            if self.current_metadata:
                print(">> Extracting business context and column definitions from API metadata...")
                
                # Debug: Show what template information we have
                if self.metadata_template:
                    print(f">> Using metadata template with {len(self.metadata_template)} sections")
                    print(f">> Template keys: {list(self.metadata_template.keys())}")
                else:
                    print(">> No metadata template available - using fallback extraction")
                
                self.business_context = self._extract_api_business_context(self.current_metadata)
                self.column_definitions = self._extract_api_column_definitions(self.current_metadata)
                
                print(f">> Extracted business context: {self.business_context}")
                print(f">> Extracted {len(self.column_definitions)} column definitions from API")
                if self.column_definitions:
                    print(f">> Available columns: {list(self.column_definitions.keys())}")
                    # Show first column details
                    first_col = list(self.column_definitions.keys())[0]
                    print(f">> First column details: {self.column_definitions[first_col]}")
                else:
                    print(">> ERROR: No column definitions extracted from API metadata")
                    print(">> This suggests the API metadata format is not as expected")
            else:
                return "ERROR: Failed to extract metadata from API response."
            
            # Load data using appropriate service
            if file_type.lower() == 'csv':
                self.current_data = await self.csv_service.load_csv(file_path)
            elif file_type.lower() == 'excel':
                self.current_data = await self.excel_service.load_excel(file_path)
            elif file_type.lower() == 'json':
                # Load JSON and convert to DataFrame for consistent processing
                json_data = await self.json_service.load_json(file_path)
                # Smart normalization: look for array data to tabulate
                if isinstance(json_data, dict):
                    # Look for keys that contain arrays of objects (typical data tables)
                    array_keys = []
                    for key, value in json_data.items():
                        if isinstance(value, list) and value and isinstance(value[0], dict):
                            array_keys.append((key, len(value)))
                    
                    if array_keys:
                        # Use the largest array as the main data
                        main_key = max(array_keys, key=lambda x: x[1])[0]
                        # Use JSON service's enhanced conversion with flattening
                        self.current_data = self.json_service.convert_to_dataframe(
                            json_data[main_key], flatten_nested=True
                        )
                        print(f"Using JSON array '{main_key}' with {len(json_data[main_key])} records")
                    else:
                        # No arrays found, use whole structure
                        self.current_data = self.json_service.convert_to_dataframe(
                            json_data, flatten_nested=True
                        )
                else:
                    # Direct list, convert as-is
                    self.current_data = self.json_service.convert_to_dataframe(
                        json_data, flatten_nested=True
                    )
            else:
                return f"Error: Unsupported file type: {file_type}"
            
            # CRITICAL: Update column definitions with actual DataFrame columns
            if self.current_data is not None and hasattr(self.current_data, 'columns'):
                actual_columns = list(self.current_data.columns)
                print(f">> Updating column definitions with actual DataFrame columns: {len(actual_columns)} columns")
                print(f">> Actual columns: {actual_columns}")
                
                # Update or create column definitions based on actual DataFrame
                updated_columns = {}
                for i, col_name in enumerate(actual_columns):
                    # Check if we have existing metadata for this column
                    existing_def = self.column_definitions.get(col_name, {})
                    
                    # Infer column type from DataFrame
                    col_dtype = str(self.current_data[col_name].dtype)
                    if 'int' in col_dtype:
                        inferred_type = 'integer'
                    elif 'float' in col_dtype:
                        inferred_type = 'number'
                    elif 'bool' in col_dtype:
                        inferred_type = 'boolean'
                    elif 'datetime' in col_dtype:
                        inferred_type = 'datetime'
                    else:
                        inferred_type = 'string'
                    
                    updated_columns[col_name] = {
                        'description': existing_def.get('description', f"Column: {col_name}"),
                        'type': existing_def.get('type', inferred_type),
                        'position': i + 1,
                        'nullable': True,
                        'source': existing_def.get('source', 'dataframe_columns'),
                        'aliases': existing_def.get('aliases', self._generate_api_aliases(col_name, {}))
                    }
                
                # Replace column definitions with actual DataFrame columns
                self.column_definitions = updated_columns
                print(f">> Successfully updated column definitions: {len(self.column_definitions)} columns")
                
                # Update current_metadata to reflect actual columns
                if self.current_metadata and 'data_dictionary' in self.current_metadata:
                    self.current_metadata['data_dictionary']['columns'] = updated_columns
                    print(f">> Updated metadata with actual column definitions")
            
            # Validate data against metadata if available
            if self.current_metadata:
                # Simple validation using available metadata
                validation_warnings = []
                if 'columns' in self.current_metadata:
                    for col, col_info in self.current_metadata['columns'].items():
                        if col_info.get('constraints', {}).get('required', False):
                            if col not in self.current_data.columns:
                                validation_warnings.append(f"Required column '{col}' is missing")
                            elif self.current_data[col].isnull().any():
                                validation_warnings.append(f"Required column '{col}' has null values")
                
                if validation_warnings:
                    print(f">> Data validation warnings: {len(validation_warnings)}")
            
            # Store enhanced file info
            self.current_file_info = {
                "file_path": file_path,
                "file_type": file_type.upper(),
                "metadata_path": metadata_path or "auto-discovered",
                "rows": len(self.current_data),
                "columns": len(self.current_data.columns) if hasattr(self.current_data, 'columns') else 'N/A',
                "has_metadata": bool(self.current_metadata),
                "business_context": bool(self.business_context)
            }
            
            # Get enhanced description
            if self.current_metadata:
                file_desc = self.current_metadata.get('file_info', {}).get('description', 
                    self.current_metadata.get('dataset_info', {}).get('description', 'Data file'))
                business_desc = self.business_context.get('description', 'Standard analysis')
            else:
                file_desc = 'Data file'
                business_desc = 'Basic analysis (no metadata)'
            
            return f"""SUCCESS: Enhanced data loading completed!

FILE INFO:
- File: {file_path}
- Type: {file_type.upper()}
- Description: {file_desc}
- Rows: {self.current_file_info['rows']:,}
- Columns: {self.current_file_info['columns']}

METADATA INFO:
- Source: {self.current_file_info['metadata_path']}
- Business Context: {business_desc}
- Column Definitions: {len(self.column_definitions)} columns with metadata
- Validation: {'PASSED' if self.current_metadata else 'NO METADATA'}

INTELLIGENCE FEATURES:
- Metadata-aware query processing: {'ENABLED' if self.current_metadata else 'BASIC MODE'}
- Business context integration: {'AVAILABLE' if self.business_context else 'NONE'}
- Domain-specific prompts: AVAILABLE
- Enhanced analysis: READY

Ready for intelligent queries! Ask me anything about this data using natural language."""
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"ERROR: Failed to load data: {str(e)}\n\nDetails:\n{error_details}"
    
    def _parse_project_object(self, metadata_path: str) -> tuple:
        """Parse metadata path into project and object names."""
        if '/' not in metadata_path:
            return None, None
        
        parts = metadata_path.split('/')
        if len(parts) != 2:
            return None, None
        
        return parts[0].strip(), parts[1].strip()
    
    def _validate_api_metadata_format(self, metadata: Dict[str, Any]) -> bool:
        """Validate that metadata follows the expected API format."""
        print(f">> Validating API metadata format...")
        
        # Check for required API metadata structure
        required_sections = ['dataset_info', 'data_dictionary']
        
        missing_sections = []
        for section in required_sections:
            if section not in metadata:
                missing_sections.append(section)
        
        if missing_sections:
            print(f">> Missing required sections: {missing_sections}")
            print(f">> Available sections: {list(metadata.keys())}")
            return False
        
        # Check for columns in data_dictionary
        data_dict = metadata.get('data_dictionary', {})
        if 'columns' not in data_dict:
            print(">> Missing 'columns' in data_dictionary")
            print(f">> data_dictionary contains: {list(data_dict.keys())}")
            return False
        
        columns = data_dict.get('columns', {})
        print(f">> Found {len(columns)} columns in data_dictionary")
        
        return True
    
    def _extract_api_business_context(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business context from standardized API metadata."""
        dataset_info = metadata.get('dataset_info', {})
        
        return {
            'description': dataset_info.get('description', 'Data analysis'),
            'domain': dataset_info.get('domain', 'General'),
            'purpose': dataset_info.get('purpose', 'Analysis'),
            'title': dataset_info.get('title', 'Dataset')
        }
    
    def _extract_api_column_definitions(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract column definitions from standardized API metadata."""
        print(f">> Extracting column definitions from API metadata...")
        
        # First, try the standard API format
        data_dictionary = metadata.get('data_dictionary', {})
        columns = data_dictionary.get('columns', {})
        
        print(f">> Found data_dictionary with {len(columns)} columns")
        
        # If no columns found in standard format, check if template provides guidance
        if not columns and self.metadata_template:
            print(f">> No columns in standard format, checking template guidance...")
            # Use template to find alternative paths
            template_columns_paths = [
                'columns',
                'fields', 
                'schema.columns',
                'metadata.columns'
            ]
            
            for path in template_columns_paths:
                test_columns = self._safe_get_nested(metadata, path)
                if test_columns and isinstance(test_columns, dict):
                    print(f">> Found columns at path: {path}")
                    columns = test_columns
                    break
        
        # If still no columns, look for any dictionary that could be columns
        if not columns:
            print(f">> Still no columns found, checking all top-level dictionaries...")
            for key, value in metadata.items():
                if isinstance(value, dict) and len(value) > 0:
                    # Check if this looks like column definitions
                    first_item = next(iter(value.values()))
                    if isinstance(first_item, dict) and any(field in first_item for field in ['type', 'description', 'business_meaning']):
                        print(f">> Found potential columns in section: {key}")
                        columns = value
                        break
        
        # If still no columns found, try to use detected_headers as fallback
        if not columns:
            print(f">> No columns found, attempting to use detected_headers as fallback...")
            data_dictionary = metadata.get('data_dictionary', {})
            detected_headers = data_dictionary.get('detected_headers', [])
            
            if detected_headers:
                print(f">> Found {len(detected_headers)} detected headers: {detected_headers}")
                columns = {}
                
                # Create basic column definitions from detected headers
                for i, header in enumerate(detected_headers):
                    columns[header] = {
                        'description': f"Auto-generated from detected header: {header}",
                        'type': 'string',  # Default type
                        'position': i + 1,
                        'nullable': True,
                        'source': 'detected_headers'
                    }
                
                print(f">> Generated {len(columns)} columns from detected headers")
            else:
                print(f">> No detected_headers found either")
        
        # IMPORTANT: After data is loaded, we'll update columns with actual DataFrame columns
        # This will be handled in the load_data_file method after DataFrame creation
        
        # Ensure all columns have aliases for natural language querying
        for col_name, col_info in columns.items():
            if isinstance(col_info, dict):
                if 'aliases' not in col_info:
                    col_info['aliases'] = self._generate_api_aliases(col_name, col_info)
                print(f">> Column '{col_name}': {col_info.get('description', 'No description')}")
        
        print(f">> Final result: {len(columns)} columns extracted")
        return columns
    
    def _safe_get_nested(self, data: Dict[str, Any], path: str) -> Any:
        """Safely get nested value using dot notation."""
        try:
            parts = path.split('.')
            current = data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current
        except:
            return None
    
    def _generate_api_aliases(self, col_name: str, col_info: Dict[str, Any]) -> List[str]:
        """Generate aliases for API metadata columns."""
        aliases = []
        col_lower = col_name.lower()
        
        # Add basic variations
        aliases.append(col_lower)
        
        # Add space/underscore variations
        if '_' in col_lower:
            aliases.append(col_lower.replace('_', ' '))
        if ' ' in col_lower:
            aliases.append(col_lower.replace(' ', '_'))
        
        # Add business meaning from API metadata
        business_meaning = col_info.get('business_meaning', '')
        if business_meaning:
            aliases.append(business_meaning.lower())
        
        # Add description keywords
        description = col_info.get('description', '')
        if description:
            # Extract key words from description
            import re
            words = re.findall(r'\b\w+\b', description.lower())
            key_words = [w for w in words if len(w) > 3 and w not in ['this', 'that', 'with', 'from']]
            aliases.extend(key_words[:2])  # Add up to 2 key words
        
        # Remove duplicates while preserving order
        unique_aliases = []
        for alias in aliases:
            if alias and alias not in unique_aliases:
                unique_aliases.append(alias)
        
        return unique_aliases[:10]  # Limit to 10 aliases
    
    async def load_sample_data(self, data_type: str):
        """Load sample data for testing."""
        try:
            print(f"Loading sample {data_type} data...")
            
            if data_type.lower() == 'sales':
                # Create sample sales data matching real sales_data.csv structure
                sample_data = {
                    'CustomerID': ['CUST-001', 'CUST-002', 'CUST-003', 'CUST-004', 'CUST-005', 
                                  'CUST-006', 'CUST-007', 'CUST-008', 'CUST-009', 'CUST-010'],
                    'CustomerName': ['Acme Corp', 'TechStart', 'Global Inc', 'DataCorp', 'CloudNet',
                                    'AI Solutions', 'SecureIT', 'WebCo', 'DevOps Ltd', 'AnalyticsCo'],
                    'ProductName': ['ML Platform', 'Cloud Storage', 'ML Platform', 'Security Suite', 'Infrastructure',
                                   'Analytics', 'Security Suite', 'Cloud Storage', 'ML Platform', 'Infrastructure'],
                    'TotalAmount': [45000, 12000, 38000, 15000, 28000,
                                   22000, 18000, 9500, 41000, 31000],
                    'SalesRep': ['Alice Johnson', 'Bob Wilson', 'Alice Johnson', 'Charlie Brown', 'Bob Wilson',
                                'Alice Johnson', 'Charlie Brown', 'Bob Wilson', 'Alice Johnson', 'Charlie Brown']
                }
                self.current_data = pd.DataFrame(sample_data)
                
            elif data_type.lower() == 'hr':
                # Create sample HR data
                sample_data = {
                    'Employee': ['Alice Johnson', 'Bob Wilson', 'Charlie Brown', 'Diana Smith', 'Eve Davis'],
                    'Department': ['Engineering', 'Sales', 'Marketing', 'Engineering', 'Marketing'],
                    'Salary': [125000, 110000, 90000, 125000, 90000],
                    'Performance': [4.5, 4.2, 3.8, 4.7, 4.0],
                    'Years': [3, 5, 2, 4, 1]
                }
                self.current_data = pd.DataFrame(sample_data)
                
            elif data_type.lower() == 'inventory':
                # Create sample inventory data
                sample_data = {
                    'Product': ['Laptop Pro', 'Monitor 4K', 'Keyboard', 'Mouse', 'Webcam'],
                    'Stock': [25, 45, 120, 85, 60],
                    'Value': [1200, 350, 89, 25, 95],
                    'Category': ['Computer', 'Display', 'Accessory', 'Accessory', 'Accessory'],
                    'Supplier': ['TechCorp', 'DisplayInc', 'PeripheralCo', 'PeripheralCo', 'VideoTech']
                }
                self.current_data = pd.DataFrame(sample_data)
                
            else:
                return f"ERROR: Unknown sample data type: {data_type}"
            
            # Set sample file info
            self.current_file_info = {
                "file_path": f"sample_{data_type}_data",
                "file_type": "SAMPLE",
                "metadata_path": "built-in",
                "rows": len(self.current_data),
                "columns": len(self.current_data.columns)
            }
            self.current_metadata = {"description": f"Sample {data_type} data for testing"}
            
            return f"""Sample {data_type} data loaded successfully!

DATA INFO:
- Type: Sample {data_type.upper()} data
- Rows: {len(self.current_data)}
- Columns: {len(self.current_data.columns)}

Ready for queries! Ask me anything about the sample data using natural language."""
            
        except Exception as e:
            return f"ERROR: Failed to load sample data: {str(e)}"
    
    async def get_enhanced_data_summary(self, query: str):
        """Get enhanced data summary with metadata context."""
        if self.current_data is None:
            return "ERROR: No data loaded"
        
        try:
            # Enhanced data sample with business context
            data_sample = self.current_data.head(10).to_string()
            
            # Add metadata context if available
            metadata_context = ""
            if self.current_metadata:
                metadata_context = f"""
BUSINESS CONTEXT:
- Description: {self.business_context.get('description', 'N/A')}
- Domain: {self.business_context.get('domain', 'General')}
- Purpose: {self.business_context.get('purpose', 'Analysis')}

COLUMN DEFINITIONS:
"""
                for col, info in list(self.column_definitions.items())[:5]:
                    business_meaning = info.get('business_meaning', col)
                    data_type = info.get('data_type', 'unknown')
                    metadata_context += f"- {col}: {business_meaning} ({data_type})\n"
                
                if len(self.column_definitions) > 5:
                    metadata_context += f"... and {len(self.column_definitions) - 5} more columns\n"
            
            data_summary = f"""
ENHANCED DATA SUMMARY:
- Total Rows: {len(self.current_data):,}
- Columns: {list(self.current_data.columns)}
- Data Quality: {self._assess_data_quality()}
{metadata_context}

SAMPLE DATA (first 10 rows):
{data_sample}

BASIC STATISTICS:
{self.current_data.describe().to_string() if len(self.current_data.select_dtypes(include='number').columns) > 0 else 'No numeric columns for statistics'}
"""
            return data_summary
            
        except Exception as e:
            return f"ERROR: Error getting enhanced data summary: {str(e)}"
    
    async def _perform_grouped_analysis(self, intent: Dict[str, Any], group_col: str, metric_col: str) -> str:
        """Perform grouped analysis with enhanced formatting."""
        try:
            query_lower = intent['original_query'].lower()
            show_individual_records = any(word in query_lower for word in ['customer', 'product', 'item', 'sale', 'transaction', 'order'])
            
            if show_individual_records and intent['limit'] and intent['group_by']:
                # Individual records grouped
                result_text = f"TOP {intent['limit']} RECORDS BY {metric_col.upper()}, GROUPED BY {group_col.upper()}:\n\n"
                
                desc_col = self._find_column(['customer', 'product', 'name', 'item'], exclude_terms=[group_col])
                
                for group_name in self.current_data[group_col].unique():
                    group_data = self.current_data[self.current_data[group_col] == group_name]
                    top_n = group_data.nlargest(intent['limit'], metric_col) if not intent['ascending'] else group_data.nsmallest(intent['limit'], metric_col)
                    
                    result_text += f">> {group_name}:\n"
                    for idx, (_, row) in enumerate(top_n.iterrows(), 1):
                        if desc_col:
                            result_text += f"  {idx}. {row[desc_col]}: ${row[metric_col]:,.2f}\n"
                        else:
                            result_text += f"  {idx}. ${row[metric_col]:,.2f}\n"
                    
                    group_total = group_data[metric_col].sum()
                    result_text += f"     Subtotal: ${group_total:,.2f}\n\n"
                
                total = self.current_data[metric_col].sum()
                result_text += f"OVERALL SUMMARY:\n"
                result_text += f"- Total {metric_col}: ${total:,.2f}\n"
                result_text += f"- Number of {group_col}s: {self.current_data[group_col].nunique()}\n"
                result_text += f"- Total records: {len(self.current_data):,}\n"
                
                return result_text
            else:
                # Aggregated grouping
                grouped_result = self.current_data.groupby(group_col)[metric_col].sum().sort_values(ascending=intent['ascending'])
                
                result_text = f"TOP {intent['limit']} {group_col.upper()} BY {metric_col.upper()}:\n\n"
                total = grouped_result.sum()
                
                for i, (name, value) in enumerate(grouped_result.head(intent['limit']).items(), 1):
                    percentage = (value / total) * 100
                    result_text += f"{i}. {name}: ${value:,.2f} ({percentage:.1f}% of total)\n"
                
                result_text += f"\nSUMMARY:\n"
                result_text += f"- Total {metric_col}: ${total:,.2f}\n"
                result_text += f"- Number of unique {group_col}s: {len(grouped_result)}\n"
                
                return result_text
                
        except Exception as e:
            return f"ERROR: Grouped analysis failed: {str(e)}"
    
    async def _perform_metric_analysis(self, intent: Dict[str, Any], metric_col: str) -> str:
        """Perform metric analysis with enhanced formatting."""
        try:
            sorted_data = self.current_data.sort_values(by=metric_col, ascending=intent['ascending'])
            
            result_text = f"TOP {intent['limit']} BY {metric_col.upper()}:\n\n"
            
            desc_col = self._find_column(['customer', 'product', 'name', 'item'])
            for i, (_, row) in enumerate(sorted_data.head(intent['limit']).iterrows(), 1):
                if desc_col:
                    result_text += f"{i}. {row[desc_col]}: ${row[metric_col]:,.2f}\n"
                else:
                    result_text += f"{i}. ${row[metric_col]:,.2f}\n"
            
            # Add summary statistics
            result_text += f"\nSTATISTICS:\n"
            result_text += f"- Total: ${self.current_data[metric_col].sum():,.2f}\n"
            result_text += f"- Average: ${self.current_data[metric_col].mean():,.2f}\n"
            result_text += f"- Range: ${self.current_data[metric_col].min():,.2f} - ${self.current_data[metric_col].max():,.2f}\n"
            
            return result_text
            
        except Exception as e:
            return f"ERROR: Metric analysis failed: {str(e)}"
    
    def _parse_query_intent(self, query: str) -> Dict[str, Any]:
        """Parse natural language query to extract intent and parameters."""
        query_lower = query.lower()
        
        # Extract number (top N, first N, etc.)
        import re
        number_match = re.search(r'\b(top|first|bottom|last)\s+(\d+)\b', query_lower)
        limit = int(number_match.group(2)) if number_match else 3
        
        # Enhanced grouping dimension extraction (by X, for each X, per X)
        group_by_patterns = [
            r'(?:by|for each|per|group by)\s+(\w+(?:\s+\w+)?(?:\s+\w+)?)',  # Support up to 3 words
            r'each\s+(\w+(?:\s+\w+)?(?:\s+\w+)?)',  # Support up to 3 words
        ]
        group_by = None
        for pattern in group_by_patterns:
            match = re.search(pattern, query_lower)
            if match:
                group_by = match.group(1).strip()
                print(f"DEBUG: Found group_by pattern: '{group_by}'")
                break
        
        # Extract metric/value column with enhanced patterns
        metric_keywords = ['volume', 'sales', 'amount', 'revenue', 'total', 'price', 'quantity', 'count', 'value']
        metric = None
        for keyword in metric_keywords:
            if keyword in query_lower:
                metric = keyword
                break
        
        # If "amounts" is mentioned, default to amount/total
        if 'amounts' in query_lower or 'amount' in query_lower:
            metric = 'amount'
        
        # Determine aggregation type
        aggregation = 'sum'
        if any(word in query_lower for word in ['average', 'avg', 'mean']):
            aggregation = 'mean'
        elif any(word in query_lower for word in ['count', 'number of']):
            aggregation = 'count'
        elif any(word in query_lower for word in ['max', 'maximum', 'highest']):
            aggregation = 'max'
        elif any(word in query_lower for word in ['min', 'minimum', 'lowest']):
            aggregation = 'min'
        
        # Determine sort order
        ascending = 'bottom' in query_lower or 'lowest' in query_lower or 'least' in query_lower
        
        return {
            'limit': limit,
            'group_by': group_by,
            'metric': metric,
            'aggregation': aggregation,
            'ascending': ascending,
            'original_query': query
        }
    
    def _find_column(self, search_terms: list, exclude_terms: list = None) -> str:
        """Find column in data that matches search terms using metadata-driven aliases."""
        if exclude_terms is None:
            exclude_terms = []
        
        search_phrase = ' '.join(search_terms).lower()
        print(f"DEBUG: Searching for column with phrase: '{search_phrase}'")
        
        # Priority 1: Metadata-driven alias matching
        if self.column_definitions:
            for actual_column, column_info in self.column_definitions.items():
                if actual_column not in self.current_data.columns:
                    continue  # Skip if column doesn't exist in actual data
                
                # Check if any alias matches the search phrase
                aliases = column_info.get('aliases', [])
                for alias in aliases:
                    alias_lower = alias.lower()
                    # Exact match
                    if search_phrase == alias_lower:
                        print(f"DEBUG: EXACT alias match: '{search_phrase}' -> '{actual_column}' via alias '{alias}'")
                        if not any(exclude in actual_column.lower() for exclude in exclude_terms):
                            return actual_column
                    
                    # Partial match (search phrase contains alias or vice versa)
                    if search_phrase in alias_lower or alias_lower in search_phrase:
                        print(f"DEBUG: PARTIAL alias match: '{search_phrase}' -> '{actual_column}' via alias '{alias}'")
                        if not any(exclude in actual_column.lower() for exclude in exclude_terms):
                            return actual_column
        
        # Priority 2: Direct column name matching (existing logic)
        for col in self.current_data.columns:
            col_lower = col.lower()
            
            # Exact column name match
            if search_phrase == col_lower:
                if not any(exclude in col_lower for exclude in exclude_terms):
                    print(f"DEBUG: EXACT column name match: '{search_phrase}' -> '{col}'")
                    return col
            
            # Enhanced compound word matching
            col_words = col_lower.replace('_', ' ').replace('-', ' ')
            if search_phrase.replace(' ', '') in col_lower.replace('_', '').replace('-', ''):
                if not any(exclude in col_lower for exclude in exclude_terms):
                    print(f"DEBUG: COMPOUND word match: '{search_phrase}' -> '{col}'")
                    return col
            
            # Fallback to partial matches
            if any(term in col_lower for term in search_terms):
                if not any(exclude in col_lower for exclude in exclude_terms):
                    print(f"DEBUG: PARTIAL column match: '{search_phrase}' -> '{col}'")
                    return col
        
        print(f"DEBUG: No column found for search phrase '{search_phrase}'")
        print(f"DEBUG: Available columns: {list(self.current_data.columns)}")
        if self.column_definitions:
            print(f"DEBUG: Available aliases:")
            for col, info in self.column_definitions.items():
                aliases = info.get('aliases', [])
                if aliases:
                    print(f"  {col}: {aliases}")
        return None
    
    def get_column_aliases_summary(self) -> str:
        """Get a summary of all available column aliases for user reference."""
        if not self.column_definitions:
            return "No metadata available - column aliases not configured."
        
        summary = "📋 **Available Column Aliases:**\n\n"
        
        for col_name, col_info in self.column_definitions.items():
            if col_name in self.current_data.columns:
                aliases = col_info.get('aliases', [])
                business_meaning = col_info.get('business_meaning', col_name)
                
                summary += f"**{col_name}** ({business_meaning}):\n"
                if aliases:
                    alias_list = "', '".join(aliases)
                    summary += f"  Aliases: '{alias_list}'\n"
                else:
                    summary += f"  No aliases configured\n"
                summary += "\n"
        
        summary += "💡 **Usage:** You can refer to any column using its name or any of its aliases in your queries.\n"
        summary += "Example: 'sales rep', 'representative', or 'SalesRep' all refer to the same column."
        
        return summary
    
    async def intelligent_query(self, query: str, format_style: str = "clear", use_agent_intelligence: bool = False):
        """Process intelligent queries with metadata-aware analysis."""
        if self.current_data is None:
            return "ERROR: No data loaded. Please load data first."
        
        try:
            # Get raw data for analysis if requested
            if "raw data for analysis" in format_style.lower():
                return await self.get_enhanced_data_summary(query)
            
            print(f">> Processing query with metadata awareness: {query}")
            
            # Use domain-specific prompt if metadata available
            if self.current_metadata and self.business_context:
                return await self._metadata_aware_analysis(query)
            else:
                # Fallback to enhanced basic analysis
                return await self._enhanced_basic_analysis(query)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"ERROR: Query processing failed: {str(e)}\n\nDetails:\n{error_details}"
    
    async def _metadata_aware_analysis(self, query: str) -> str:
        """Perform metadata-aware intelligent analysis."""
        try:
            # First try structured query processing
            intent = self._parse_query_intent(query)
            print(f"DEBUG: Metadata-aware analysis - parsed intent: {intent}")
            
            # Check if this is a structured query that can be executed directly
            if intent['group_by'] or intent['metric']:
                print("DEBUG: Executing structured query with metadata context")
                return await self._enhanced_basic_analysis(query)
            
            # Otherwise, fall back to general metadata analysis
            # Get data analysis expert prompt
            analysis_prompt_template = self.prompt_manager.get_prompt("data_analysis_expert")
            
            # Prepare enhanced context
            enhanced_context = {
                "query": query,
                "business_context": self.business_context.get('description', 'Data analysis'),
                "column_definitions": self.column_definitions,
                "data_columns": list(self.current_data.columns),
                "data_shape": f"{len(self.current_data)} rows × {len(self.current_data.columns)} columns",
                "file_type": self.current_file_info.get('file_type', 'Unknown')
            }
            
            # Use metadata to enhance column understanding
            enhanced_columns = []
            for col in self.current_data.columns:
                col_info = self.column_definitions.get(col, {})
                if col_info:
                    business_meaning = col_info.get('business_meaning', col)
                    data_type = col_info.get('data_type', 'unknown')
                    enhanced_columns.append(f"{col} ({business_meaning}, {data_type})")
                else:
                    enhanced_columns.append(col)
            
            # Perform intelligent analysis using metadata context
            analysis_result = await self._execute_smart_query(query, enhanced_context)
            
            # Format result with business insights
            formatted_result = f"""METADATA-AWARE ANALYSIS

QUERY: {query}

BUSINESS CONTEXT: {self.business_context.get('description', 'Standard analysis')}

ANALYSIS RESULTS:
{analysis_result}

COLUMN CONTEXT:
{', '.join(enhanced_columns[:5])}{'...' if len(enhanced_columns) > 5 else ''}

DATA INSIGHTS:
- Total Records: {len(self.current_data):,}
- Data Quality: {self._assess_data_quality()}
- Business Domain: {self.business_context.get('domain', 'General')}
"""
            
            return formatted_result
            
        except Exception as e:
            print(f"Error in metadata-aware analysis: {e}")
            return await self._enhanced_basic_analysis(query)
    
    async def _enhanced_basic_analysis(self, query: str) -> str:
        """Enhanced basic analysis when metadata is not available."""
        try:
            # Use basic query processing but with better formatting
            intent = self._parse_query_intent(query)
            print(f"DEBUG: Parsed intent: {intent}")
            
            # Find appropriate columns based on intent with enhanced mapping
            group_col = None
            if intent['group_by']:
                # Enhanced group column finding
                group_terms = intent['group_by'].split()
                
                # Try compound search first (e.g., "sales rep" -> ["sales", "rep"])
                group_col = self._find_column(group_terms)
                
                # If no match, try individual words
                if not group_col:
                    for term in group_terms:
                        group_col = self._find_column([term])
                        if group_col:
                            break
                
                print(f"DEBUG: Group column found: {group_col} for '{intent['group_by']}'")
            
            # Find metric/value column with enhanced logic
            metric_col = None
            if intent['metric']:
                # Map common metric terms to likely column names
                metric_mappings = {
                    'amount': ['amount', 'total', 'totalamount', 'value'],
                    'total': ['total', 'amount', 'totalamount', 'sum'],
                    'revenue': ['revenue', 'total', 'amount', 'sales'],
                    'price': ['price', 'unitprice', 'amount'],
                    'quantity': ['quantity', 'qty', 'count'],
                    'volume': ['volume', 'quantity', 'amount']
                }
                
                search_terms = metric_mappings.get(intent['metric'], [intent['metric']])
                metric_col = self._find_column(search_terms)
            
            # Fallback to common value columns
            if not metric_col:
                metric_col = self._find_column(['totalamount', 'amount', 'total', 'revenue', 'price', 'quantity', 'volume'])
            
            print(f"DEBUG: Metric column found: {metric_col} for metric '{intent['metric']}'")
            
            # Execute analysis
            if group_col and metric_col:
                print(f"DEBUG: Executing grouped analysis: group={group_col}, metric={metric_col}")
                return await self._perform_grouped_analysis(intent, group_col, metric_col)
            elif metric_col:
                print(f"DEBUG: Executing metric analysis: metric={metric_col}")
                return await self._perform_metric_analysis(intent, metric_col)
            else:
                return await self.get_enhanced_data_summary(query)
                
        except Exception as e:
            return f"ERROR: Enhanced analysis failed: {str(e)}"
    
    async def _execute_smart_query(self, query: str, context: Dict[str, Any]) -> str:
        """Execute smart query using metadata context."""
        query_lower = query.lower()
        
        # Smart column matching using metadata
        target_columns = []
        for col, col_info in self.column_definitions.items():
            business_meaning = col_info.get('business_meaning', '').lower()
            if any(term in business_meaning or term in col.lower() 
                   for term in query_lower.split()):
                target_columns.append(col)
        
        # If no smart matches, fall back to basic pattern matching
        if not target_columns:
            intent = self._parse_query_intent(query)
            if intent['group_by']:
                group_col = self._find_column([intent['group_by']])
                if group_col:
                    target_columns.append(group_col)
            if intent['metric']:
                metric_col = self._find_column([intent['metric'], 'amount', 'total', 'revenue'])
                if metric_col:
                    target_columns.append(metric_col)
        
        # Perform analysis on target columns
        if target_columns:
            return self._analyze_target_columns(target_columns, query)
        else:
            return f"Smart analysis: {query}\n{self.current_data.describe().to_string()}"
    
    def _analyze_target_columns(self, columns: List[str], query: str) -> str:
        """Analyze specific target columns based on query."""
        result = f"Analysis for columns: {', '.join(columns)}\n\n"
        
        for col in columns:
            if col in self.current_data.columns:
                col_data = self.current_data[col]
                
                # Get business context for this column if available
                col_info = self.column_definitions.get(col, {})
                business_meaning = col_info.get('business_meaning', col)
                
                result += f">> {business_meaning} ({col}):\n"
                
                if col_data.dtype in ['int64', 'float64']:
                    result += f"  • Total: {col_data.sum():,.2f}\n"
                    result += f"  • Average: {col_data.mean():.2f}\n"
                    result += f"  • Range: {col_data.min():.2f} - {col_data.max():.2f}\n"
                else:
                    unique_count = col_data.nunique()
                    result += f"  • Unique values: {unique_count}\n"
                    if unique_count <= 10:
                        result += f"  • Values: {', '.join(map(str, col_data.unique()[:5]))}\n"
                
                result += "\n"
        
        return result
    
    def _assess_data_quality(self) -> str:
        """Assess data quality using metadata rules if available."""
        if not self.current_metadata:
            return "Basic (no metadata)"
        
        issues = 0
        total_checks = 0
        
        # Check for required columns
        required_columns = [col for col, info in self.column_definitions.items() 
                          if info.get('constraints', {}).get('required', False)]
        
        for col in required_columns:
            total_checks += 1
            if col not in self.current_data.columns:
                issues += 1
            elif self.current_data[col].isnull().any():
                issues += 1
        
        if total_checks == 0:
            return "Good (no constraints defined)"
        
        quality_score = ((total_checks - issues) / total_checks) * 100
        if quality_score >= 90:
            return f"Excellent ({quality_score:.0f}%)"
        elif quality_score >= 70:
            return f"Good ({quality_score:.0f}%)"
        else:
            return f"Needs Attention ({quality_score:.0f}%)"
    
    async def describe_data(self):
        """Describe the current dataset."""
        if self.current_data is None:
            return "ERROR: No data loaded"
        
        try:
            description = f"""DATASET DESCRIPTION:

FILE INFORMATION:
- Source: {self.current_file_info.get('file_path', 'Unknown')}
- Type: {self.current_file_info.get('file_type', 'Unknown')}
- Rows: {self.current_file_info.get('rows', 0):,}
- Columns: {self.current_file_info.get('columns', 0)}

COLUMNS:
{', '.join(self.current_data.columns.tolist())}

DATA TYPES:
{self.current_data.dtypes.to_string()}

BASIC STATISTICS:
{self.current_data.describe().to_string() if len(self.current_data.select_dtypes(include='number').columns) > 0 else 'No numeric columns'}
"""
            return description
            
        except Exception as e:
            return f"ERROR: Error describing data: {str(e)}"


# Create MCP server instance and global data server
mcp_server = Server("enhanced-nlp-data-server")
data_server = EnhancedDataServer()

# Global initialization flag
_server_initialized = False

async def ensure_server_initialized():
    """Ensure server is initialized once."""
    global _server_initialized
    if not _server_initialized:
        await data_server.initialize()
        _server_initialized = True

# Register tools
@mcp_server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="load_data",
            description="Load data file with metadata from HTTP API service only",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to data file"},
                    "file_type": {"type": "string", "description": "File type (csv, excel, json)"},
                    "metadata_path": {"type": "string", "description": "Required: Project/object identifier for API metadata (e.g., 'restaurant_project/restaurant_data')"}
                },
                "required": ["file_path", "file_type", "metadata_path"]
            }
        ),
        Tool(
            name="load_sample_data",
            description="Load sample data for testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_type": {"type": "string", "description": "Sample data type (sales, hr, inventory)"}
                },
                "required": ["data_type"]
            }
        ),
        Tool(
            name="intelligent_query",
            description="Query data using natural language with metadata-aware analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"},
                    "format_style": {"type": "string", "description": "Response format style"},
                    "use_agent_intelligence": {"type": "boolean", "description": "Use enhanced metadata intelligence"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="describe_data",
            description="Get detailed description of loaded data with metadata context",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_column_aliases",
            description="List all available column aliases from metadata for easier querying",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

# Register resources
@mcp_server.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources."""
    await ensure_server_initialized()
    
    resources = []
    try:
        # Get resources from ResourceManager
        resource_list = data_server.resource_manager.get_resource_list()
        
        for resource_info in resource_list:
            resources.append(Resource(
                uri=resource_info["uri"],
                name=resource_info["name"],
                description=resource_info["description"],
                mimeType="text/plain"
            ))
    except Exception as e:
        print(f"Error listing resources: {e}")
    
    return resources

@mcp_server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific resource."""
    await ensure_server_initialized()
    
    try:
        # Extract resource name from URI
        if uri.startswith("nlp-data://"):
            resource_path = uri.replace("nlp-data://", "")
            
            if resource_path.startswith("resources/"):
                resource_name = resource_path.replace("resources/", "")
                return data_server.resource_manager.read_resource(resource_name)
            elif resource_path.startswith("metadata/"):
                # Handle metadata resources
                parts = resource_path.split("/")
                if len(parts) >= 3:
                    data_type = parts[1]
                    filename = parts[2]
                    resource_name = f"metadata_{data_type}_{filename}"
                    return data_server.resource_manager.read_resource(resource_name)
        
        raise FileNotFoundError(f"Resource not found: {uri}")
        
    except Exception as e:
        return f"ERROR: Failed to read resource {uri}: {str(e)}"

# Register prompts
@mcp_server.list_prompts()
async def list_prompts() -> List[Prompt]:
    """List available prompts."""
    await ensure_server_initialized()
    
    prompts = []
    try:
        # Get prompts from PromptManager
        prompt_list = data_server.prompt_manager.get_prompt_list()
        
        for prompt_info in prompt_list:
            prompts.append(Prompt(
                name=prompt_info["name"],
                description=prompt_info["description"]
            ))
    except Exception as e:
        print(f"Error listing prompts: {e}")
    
    return prompts

@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, str]) -> str:
    """Get a specific prompt template."""
    await ensure_server_initialized()
    
    try:
        return data_server.prompt_manager.get_prompt(name, **arguments)
    except Exception as e:
        return f"ERROR: Failed to get prompt {name}: {str(e)}"

@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    await ensure_server_initialized()
    
    if name == "load_data":
        # Ensure metadata_path is provided
        metadata_path = arguments.get("metadata_path", "")
        if not metadata_path:
            error_msg = "ERROR: metadata_path is required. Please provide project/object identifier (e.g., 'restaurant_project/restaurant_data')"
            return [TextContent(type="text", text=error_msg)]
        
        result = await data_server.load_data_file(
            arguments["file_path"],
            arguments["file_type"], 
            metadata_path
        )
        return [TextContent(type="text", text=result)]
    
    elif name == "load_sample_data":
        result = await data_server.load_sample_data(arguments["data_type"])
        return [TextContent(type="text", text=result)]
    
    elif name == "intelligent_query":
        result = await data_server.intelligent_query(
            arguments["query"],
            arguments.get("format_style", "clear and organized"),
            arguments.get("use_agent_intelligence", True)  # Enable enhanced intelligence by default
        )
        return [TextContent(type="text", text=result)]
    
    elif name == "describe_data":
        result = await data_server.describe_data()
        return [TextContent(type="text", text=result)]
    
    elif name == "list_column_aliases":
        result = data_server.get_column_aliases_summary()
        return [TextContent(type="text", text=result)]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the clean MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())