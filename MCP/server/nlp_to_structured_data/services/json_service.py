"""
JSON Service for NLP to Structured Data System

Handles JSON file operations including loading, parsing,
nested data navigation, and JSON-specific operations.
"""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging
import pandas as pd
from utils.data_normalizer import DataNormalizer


class JSONService:
    """
    Service for JSON file operations.
    
    Handles .json, .jsonl, and .ndjson files with support for
    nested structures, arrays, and complex JSON operations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("services.json_service")
        self.logger.setLevel(logging.INFO)
        self.data_normalizer = DataNormalizer()
    
    async def load_json(self, file_path: Union[str, Path], 
                       encoding: str = 'utf-8') -> Union[Dict, List]:
        """
        Load JSON file.
        
        Args:
            file_path: Path to JSON file
            encoding: File encoding
            
        Returns:
            Parsed JSON data
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"JSON file not found: {file_path}")
            
            # Detect if it's JSONL/NDJSON format
            if path.suffix.lower() in ['.jsonl', '.ndjson']:
                return await self._load_jsonlines(path, encoding)
            
            # Load regular JSON
            async with aiofiles.open(path, 'r', encoding=encoding) as f:
                content = await f.read()
            
            data = json.loads(content)
            self.logger.info(f"Loaded JSON file: {file_path}")
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {file_path}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load JSON file {file_path}: {str(e)}")
            raise
    
    async def _load_jsonlines(self, file_path: Path, encoding: str) -> List[Dict]:
        """Load JSONL/NDJSON file (one JSON object per line)."""
        try:
            data = []
            
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                async for line in f:
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            data.append(obj)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Skipping invalid JSON line: {line[:50]}...")
                            continue
            
            self.logger.info(f"Loaded {len(data)} JSON objects from {file_path}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to load JSONL file {file_path}: {str(e)}")
            raise
    
    def navigate_nested_data(self, data: Union[Dict, List], 
                           path: str) -> Any:
        """
        Navigate nested JSON data using dot notation.
        
        Args:
            data: JSON data structure
            path: Dot-separated path (e.g., 'user.profile.name')
            
        Returns:
            Value at the specified path
        """
        try:
            if not path:
                return data
            
            parts = path.split('.')
            current = data
            
            for part in parts:
                if isinstance(current, dict):
                    # Handle array index notation (e.g., 'items[0]')
                    if '[' in part and part.endswith(']'):
                        key, index_str = part.split('[')
                        index = int(index_str.rstrip(']'))
                        if key:
                            current = current.get(key, [])
                        if isinstance(current, list) and 0 <= index < len(current):
                            current = current[index]
                        else:
                            return None
                    else:
                        current = current.get(part)
                elif isinstance(current, list):
                    try:
                        index = int(part)
                        if 0 <= index < len(current):
                            current = current[index]
                        else:
                            return None
                    except ValueError:
                        return None
                else:
                    return None
                
                if current is None:
                    return None
            
            return current
            
        except Exception as e:
            self.logger.error(f"Navigation failed for path '{path}': {str(e)}")
            return None
    
    def flatten_json(self, data: Union[Dict, List], 
                    separator: str = '.') -> Dict[str, Any]:
        """
        Flatten nested JSON structure.
        
        Args:
            data: JSON data to flatten
            separator: Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        def _flatten(obj, parent_key='', sep='.'):
            items = []
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{parent_key}{sep}{key}" if parent_key else key
                    if isinstance(value, (dict, list)):
                        items.extend(_flatten(value, new_key, sep).items())
                    else:
                        items.append((new_key, value))
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    new_key = f"{parent_key}[{i}]"
                    if isinstance(value, (dict, list)):
                        items.extend(_flatten(value, new_key, sep).items())
                    else:
                        items.append((new_key, value))
            else:
                items.append((parent_key, obj))
            
            return dict(items)
        
        try:
            return _flatten(data, '', separator)
        except Exception as e:
            self.logger.error(f"Flattening failed: {str(e)}")
            return {}
    
    def get_json_schema(self, data: Union[Dict, List]) -> Dict[str, Any]:
        """
        Analyze JSON structure and generate schema information.
        
        Args:
            data: JSON data to analyze
            
        Returns:
            Schema information
        """
        try:
            def _analyze_value(value):
                if value is None:
                    return {"type": "null"}
                elif isinstance(value, bool):
                    return {"type": "boolean"}
                elif isinstance(value, int):
                    return {"type": "integer"}
                elif isinstance(value, float):
                    return {"type": "number"}
                elif isinstance(value, str):
                    return {"type": "string"}
                elif isinstance(value, list):
                    if not value:
                        return {"type": "array", "items": {"type": "unknown"}}
                    
                    # Analyze array items
                    item_types = set()
                    for item in value[:5]:  # Sample first 5 items
                        item_analysis = _analyze_value(item)
                        item_types.add(item_analysis["type"])
                    
                    if len(item_types) == 1:
                        item_type = list(item_types)[0]
                        if item_type == "object":
                            # Analyze object structure
                            sample_obj = next((item for item in value if isinstance(item, dict)), {})
                            return {
                                "type": "array",
                                "items": _analyze_value(sample_obj)
                            }
                        else:
                            return {
                                "type": "array",
                                "items": {"type": item_type}
                            }
                    else:
                        return {
                            "type": "array",
                            "items": {"type": "mixed", "types": list(item_types)}
                        }
                
                elif isinstance(value, dict):
                    properties = {}
                    for key, val in value.items():
                        properties[key] = _analyze_value(val)
                    
                    return {
                        "type": "object",
                        "properties": properties,
                        "required": list(value.keys())
                    }
                else:
                    return {"type": "unknown"}
            
            return _analyze_value(data)
            
        except Exception as e:
            self.logger.error(f"Schema analysis failed: {str(e)}")
            return {"type": "unknown", "error": str(e)}
    
    def extract_values_by_key(self, data: Union[Dict, List], 
                             key: str) -> List[Any]:
        """
        Extract all values for a specific key from nested JSON.
        
        Args:
            data: JSON data structure
            key: Key to search for
            
        Returns:
            List of all values found for the key
        """
        try:
            values = []
            
            def _extract(obj):
                if isinstance(obj, dict):
                    if key in obj:
                        values.append(obj[key])
                    for value in obj.values():
                        _extract(value)
                elif isinstance(obj, list):
                    for item in obj:
                        _extract(item)
            
            _extract(data)
            return values
            
        except Exception as e:
            self.logger.error(f"Value extraction failed for key '{key}': {str(e)}")
            return []
    
    def filter_json_data(self, data: Union[Dict, List], 
                        filters: Dict[str, Any]) -> Union[Dict, List]:
        """
        Filter JSON data based on conditions.
        
        Args:
            data: JSON data to filter
            filters: Dictionary of path -> condition mappings
            
        Returns:
            Filtered JSON data
        """
        try:
            if isinstance(data, list):
                # Filter array of objects
                filtered_items = []
                
                for item in data:
                    matches = True
                    
                    for path, condition in filters.items():
                        value = self.navigate_nested_data(item, path)
                        
                        if not self._matches_condition(value, condition):
                            matches = False
                            break
                    
                    if matches:
                        filtered_items.append(item)
                
                return filtered_items
            
            elif isinstance(data, dict):
                # Check if single object matches filters
                for path, condition in filters.items():
                    value = self.navigate_nested_data(data, path)
                    
                    if not self._matches_condition(value, condition):
                        return {}
                
                return data
            
            return data
            
        except Exception as e:
            self.logger.error(f"Filtering failed: {str(e)}")
            return data
    
    def _matches_condition(self, value: Any, condition: Any) -> bool:
        """Check if value matches condition."""
        try:
            if isinstance(condition, dict):
                operator = condition.get('operator', 'equals')
                expected = condition.get('value')
                
                if operator == 'equals':
                    return value == expected
                elif operator == 'not_equals':
                    return value != expected
                elif operator == 'greater_than':
                    return value > expected
                elif operator == 'less_than':
                    return value < expected
                elif operator == 'contains':
                    return expected in str(value)
                elif operator == 'in':
                    return value in expected
                elif operator == 'exists':
                    return value is not None
                
            else:
                # Simple equality check
                return value == condition
            
            return False
            
        except Exception:
            return False
    
    async def save_json(self, data: Union[Dict, List], 
                       file_path: Union[str, Path],
                       indent: Optional[int] = 2,
                       encoding: str = 'utf-8') -> bool:
        """
        Save data to JSON file.
        
        Args:
            data: Data to save
            file_path: Output file path
            indent: JSON indentation (None for compact)
            encoding: File encoding
            
        Returns:
            True if successful
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            json_str = json.dumps(data, indent=indent, ensure_ascii=False)
            
            async with aiofiles.open(path, 'w', encoding=encoding) as f:
                await f.write(json_str)
            
            self.logger.info(f"Saved JSON to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON to {file_path}: {str(e)}")
            return False
    
    async def save_jsonlines(self, data: List[Dict], 
                            file_path: Union[str, Path],
                            encoding: str = 'utf-8') -> bool:
        """
        Save data to JSONL file.
        
        Args:
            data: List of dictionaries to save
            file_path: Output file path
            encoding: File encoding
            
        Returns:
            True if successful
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(path, 'w', encoding=encoding) as f:
                for item in data:
                    json_line = json.dumps(item, ensure_ascii=False) + '\n'
                    await f.write(json_line)
            
            self.logger.info(f"Saved {len(data)} JSON objects to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save JSONL to {file_path}: {str(e)}")
            return False
    
    def convert_to_dataframe(self, data: Union[Dict, List], flatten_nested: bool = True) -> pd.DataFrame:
        """
        Convert JSON data to pandas DataFrame.
        
        Args:
            data: JSON data to convert
            flatten_nested: Whether to flatten nested dictionaries for better analysis
            
        Returns:
            Pandas DataFrame
        """
        try:
            if isinstance(data, list):
                # List of objects - use as records
                if all(isinstance(item, dict) for item in data):
                    df = pd.DataFrame(data)
                else:
                    # Mixed types - create single column
                    df = pd.DataFrame({"value": data})
            
            elif isinstance(data, dict):
                # Single object - create single row
                df = pd.DataFrame([data])
            
            else:
                # Single value
                df = pd.DataFrame({"value": [data]})
            
            # Apply flattening if requested
            if flatten_nested:
                df = self._flatten_dataframe_columns(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"DataFrame conversion failed: {str(e)}")
            return pd.DataFrame()
    
    def _flatten_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flatten nested dictionary columns in a DataFrame for better analysis.
        
        Args:
            df: DataFrame with potentially nested columns
            
        Returns:
            DataFrame with flattened columns
        """
        try:
            flattened_df = df.copy()
            
            for col in df.columns:
                # Check if column contains dictionaries
                if df[col].dtype == 'object':
                    sample_value = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                    
                    if isinstance(sample_value, dict):
                        # Flatten the dictionary column using pandas json_normalize
                        nested_df = pd.json_normalize(df[col])
                        
                        # Rename columns to avoid conflicts
                        nested_df.columns = [f"{col}_{subcol}" for subcol in nested_df.columns]
                        
                        # Drop original column and concatenate flattened columns
                        flattened_df = flattened_df.drop(columns=[col])
                        flattened_df = pd.concat([flattened_df, nested_df], axis=1)
            
            self.logger.info(f"Flattened DataFrame from {len(df.columns)} to {len(flattened_df.columns)} columns")
            return flattened_df
            
        except Exception as e:
            self.logger.warning(f"Could not flatten DataFrame columns: {e}")
            return df  # Return original if flattening fails
    
    def get_data_statistics(self, data: Union[Dict, List]) -> Dict[str, Any]:
        """
        Get statistics about JSON data structure.
        
        Args:
            data: JSON data to analyze
            
        Returns:
            Statistics dictionary
        """
        try:
            stats = {
                "total_size": len(json.dumps(data)),
                "structure_type": type(data).__name__
            }
            
            if isinstance(data, list):
                stats.update({
                    "array_length": len(data),
                    "item_types": {},
                    "sample_items": data[:3] if data else []
                })
                
                # Analyze item types
                for item in data:
                    item_type = type(item).__name__
                    stats["item_types"][item_type] = stats["item_types"].get(item_type, 0) + 1
            
            elif isinstance(data, dict):
                stats.update({
                    "key_count": len(data),
                    "keys": list(data.keys())[:10],  # First 10 keys
                    "nested_levels": self._get_max_depth(data)
                })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Statistics generation failed: {str(e)}")
            return {"error": str(e)}
    
    def _get_max_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Get maximum nesting depth of JSON object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_max_depth(value, current_depth + 1) 
                      for value in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_max_depth(item, current_depth + 1) 
                      for item in obj)
        else:
            return current_depth