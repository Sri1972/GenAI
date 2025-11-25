"""
Data Normalizer - Comprehensive Implementation

Handles data normalization, type detection, and format conversion across different data types.
Provides standardized data transformation for consistent processing across agents.
"""

import pandas as pd
import numpy as np
import logging
import re
import json
from typing import Any, Dict, List, Union, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal


class DataNormalizer:
    """Comprehensive data normalizer for consistent data processing across agents."""
    
    def __init__(self):
        """Initialize the data normalizer with configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Configuration for normalization behavior
        self.config = {
            "max_sample_size": 1000,
            "clean_column_names": True,
            "standardize_dtypes": True,
            "handle_mixed_types": True,
            "date_inference": True,
            "numeric_conversion": True
        }
        
        # Common data type patterns
        self.type_patterns = {
            "email": re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            "phone": re.compile(r'^[\+]?[1-9]?[\d\s\-\(\)\.]{7,15}$'),
            "url": re.compile(r'^https?://'),
            "date_iso": re.compile(r'^\d{4}-\d{2}-\d{2}'),
            "currency": re.compile(r'^[\$\€\£\¥][\d,\.]+$')
        }
    
    def normalize_data(self, data: Any) -> Any:
        """
        Normalize data structure for consistent processing.
        
        Args:
            data: Input data of various types
            
        Returns:
            Normalized data structure
        """
        try:
            if data is None:
                return None
            
            # Handle different data types
            if isinstance(data, pd.DataFrame):
                return self.normalize_dataframe(data)
            elif isinstance(data, dict):
                return self._normalize_dict(data)
            elif isinstance(data, list):
                return self._normalize_list(data)
            elif isinstance(data, (str, int, float, bool)):
                return self._normalize_scalar(data)
            else:
                self.logger.warning(f"Unknown data type: {type(data)}")
                return data
                
        except Exception as e:
            self.logger.error(f"Error normalizing data: {str(e)}")
            return data
    
    def normalize_column_names(self, columns: List[str]) -> List[str]:
        """
        Normalize column names for consistency.
        
        Args:
            columns: List of column names
            
        Returns:
            List of normalized column names
        """
        if not self.config["clean_column_names"]:
            return columns
        
        normalized = []
        for col in columns:
            # Convert to string if not already
            col_str = str(col)
            
            # Clean the column name
            cleaned = (col_str
                      .strip()
                      .replace(' ', '_')
                      .replace('-', '_')
                      .replace('.', '_')
                      .replace('(', '')
                      .replace(')', '')
                      .replace('[', '')
                      .replace(']', '')
                      .replace('/', '_')
                      .replace('\\', '_'))
            
            # Remove multiple underscores
            cleaned = re.sub(r'_+', '_', cleaned)
            
            # Remove leading/trailing underscores
            cleaned = cleaned.strip('_')
            
            # Ensure it starts with letter or underscore
            if cleaned and not cleaned[0].isalpha() and cleaned[0] != '_':
                cleaned = f"col_{cleaned}"
            
            # Handle empty names
            if not cleaned:
                cleaned = f"column_{len(normalized)}"
            
            normalized.append(cleaned)
        
        return normalized
    
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize a pandas DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Normalized DataFrame
        """
        try:
            # Work on a copy
            normalized_df = df.copy()
            
            # Normalize column names
            if self.config["clean_column_names"]:
                normalized_df.columns = self.normalize_column_names(normalized_df.columns.tolist())
            
            # Standardize data types
            if self.config["standardize_dtypes"]:
                normalized_df = self._standardize_dataframe_types(normalized_df)
            
            # Handle mixed types
            if self.config["handle_mixed_types"]:
                normalized_df = self._handle_mixed_types(normalized_df)
            
            return normalized_df
            
        except Exception as e:
            self.logger.error(f"Error normalizing DataFrame: {str(e)}")
            return df
    
    def normalize_to_records(self, data: Any) -> List[Dict[str, Any]]:
        """
        Convert data to list of record dictionaries.
        
        Args:
            data: Input data (DataFrame, dict, list, etc.)
            
        Returns:
            List of record dictionaries
        """
        try:
            if data is None:
                return []
            
            if isinstance(data, pd.DataFrame):
                # Convert DataFrame to records
                return data.fillna('').to_dict('records')
            
            elif isinstance(data, list):
                if not data:
                    return []
                
                # If list of dictionaries, return as-is (normalized)
                if isinstance(data[0], dict):
                    return [self._normalize_record(record) for record in data]
                
                # If list of lists, convert to records with column names
                elif isinstance(data[0], (list, tuple)):
                    records = []
                    for i, row in enumerate(data):
                        record = {}
                        for j, value in enumerate(row):
                            record[f"column_{j}"] = self._normalize_scalar(value)
                        records.append(record)
                    return records
                
                # If list of scalars, convert to single column
                else:
                    return [{"value": self._normalize_scalar(item)} for item in data]
            
            elif isinstance(data, dict):
                # If single dictionary, wrap in list
                if self._is_record_dict(data):
                    return [self._normalize_record(data)]
                
                # If dictionary with array values, transpose
                else:
                    return self._dict_to_records(data)
            
            else:
                # Single scalar value
                return [{"value": self._normalize_scalar(data)}]
                
        except Exception as e:
            self.logger.error(f"Error converting to records: {str(e)}")
            return []
    
    def get_data_types(self, records: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Infer data types from list of records.
        
        Args:
            records: List of record dictionaries
            
        Returns:
            Dictionary mapping column names to inferred data types
        """
        if not records:
            return {}
        
        try:
            # Get all column names
            all_columns = set()
            for record in records:
                all_columns.update(record.keys())
            
            data_types = {}
            
            for column in all_columns:
                # Collect non-null values for this column
                values = [record.get(column) for record in records if record.get(column) is not None]
                
                if not values:
                    data_types[column] = "unknown"
                    continue
                
                # Infer type based on values
                inferred_type = self._infer_column_type(values)
                data_types[column] = inferred_type
            
            return data_types
            
        except Exception as e:
            self.logger.error(f"Error inferring data types: {str(e)}")
            return {}
    
    def create_sample_dataset(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a sample dataset with metadata for quick overview.
        
        Args:
            records: List of record dictionaries
            
        Returns:
            Dictionary with sample data and metadata
        """
        if not records:
            return {"sample": [], "metadata": {}}
        
        try:
            # Limit sample size
            sample_records = records[:self.config["max_sample_size"]]
            
            # Get column information
            all_columns = set()
            for record in sample_records:
                all_columns.update(record.keys())
            
            column_info = {}
            for column in all_columns:
                values = [record.get(column) for record in sample_records if record.get(column) is not None]
                
                column_info[column] = {
                    "data_type": self._infer_column_type(values) if values else "unknown",
                    "sample_values": list(set(values))[:5] if values else [],
                    "null_count": sum(1 for record in sample_records if record.get(column) is None),
                    "total_count": len(sample_records)
                }
            
            return {
                "sample": sample_records,
                "metadata": {
                    "total_records": len(records),
                    "sample_size": len(sample_records),
                    "columns": column_info,
                    "created_at": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error creating sample dataset: {str(e)}")
            return {"sample": records[:10], "metadata": {"error": str(e)}}
    
    def detect_data_types(self, data: Any) -> Dict[str, str]:
        """
        Detect data types in various data structures.
        
        Args:
            data: Input data
            
        Returns:
            Dictionary of detected data types
        """
        try:
            if isinstance(data, pd.DataFrame):
                return {col: str(dtype) for col, dtype in data.dtypes.items()}
            
            elif isinstance(data, list) and data:
                records = self.normalize_to_records(data)
                return self.get_data_types(records)
            
            elif isinstance(data, dict):
                records = self.normalize_to_records(data)
                return self.get_data_types(records)
            
            else:
                return {"value": type(data).__name__}
                
        except Exception as e:
            self.logger.error(f"Error detecting data types: {str(e)}")
            return {}
    
    def clean_data(self, data: Any) -> Any:
        """
        Clean data by removing null values, standardizing formats, etc.
        
        Args:
            data: Input data
            
        Returns:
            Cleaned data
        """
        try:
            if isinstance(data, pd.DataFrame):
                return self._clean_dataframe(data)
            elif isinstance(data, list):
                return [self.clean_data(item) for item in data if item is not None]
            elif isinstance(data, dict):
                return {k: self.clean_data(v) for k, v in data.items() if v is not None}
            else:
                return self._clean_scalar(data)
                
        except Exception as e:
            self.logger.error(f"Error cleaning data: {str(e)}")
            return data
    
    # Private helper methods
    
    def _normalize_dict(self, data: Dict) -> Dict:
        """Normalize dictionary data."""
        normalized = {}
        for key, value in data.items():
            # Normalize key
            clean_key = self._clean_key(str(key))
            # Normalize value
            normalized[clean_key] = self.normalize_data(value)
        return normalized
    
    def _normalize_list(self, data: List) -> List:
        """Normalize list data."""
        return [self.normalize_data(item) for item in data]
    
    def _normalize_scalar(self, value: Any) -> Any:
        """Normalize scalar values."""
        if value is None:
            return None
        
        # Handle special numeric types
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            return float(value)
        elif isinstance(value, np.bool_):
            return bool(value)
        else:
            return value
    
    def _normalize_record(self, record: Dict) -> Dict:
        """Normalize a single record dictionary."""
        normalized = {}
        for key, value in record.items():
            clean_key = self._clean_key(str(key))
            normalized[clean_key] = self._normalize_scalar(value)
        return normalized
    
    def _clean_key(self, key: str) -> str:
        """Clean dictionary keys."""
        return key.strip().replace(' ', '_').replace('-', '_')
    
    def _is_record_dict(self, data: Dict) -> bool:
        """Check if dictionary represents a single record vs. columnar data."""
        # If all values are scalars or None, it's likely a record
        return all(not isinstance(v, (list, dict)) for v in data.values())
    
    def _dict_to_records(self, data: Dict) -> List[Dict]:
        """Convert columnar dictionary to list of records."""
        if not data:
            return []
        
        # Find the maximum length
        max_length = max(len(v) if isinstance(v, list) else 1 for v in data.values())
        
        records = []
        for i in range(max_length):
            record = {}
            for key, value in data.items():
                if isinstance(value, list):
                    record[key] = value[i] if i < len(value) else None
                else:
                    record[key] = value if i == 0 else None
            records.append(record)
        
        return records
    
    def _infer_column_type(self, values: List[Any]) -> str:
        """Infer the data type of a column based on its values."""
        if not values:
            return "unknown"
        
        # Count different types
        type_counts = {}
        pattern_matches = {}
        
        for value in values:
            if value is None or value == '':
                continue
            
            value_str = str(value).strip()
            
            # Check for specific patterns
            for pattern_name, pattern in self.type_patterns.items():
                if pattern.match(value_str):
                    pattern_matches[pattern_name] = pattern_matches.get(pattern_name, 0) + 1
            
            # Basic type detection
            if isinstance(value, bool):
                type_counts["boolean"] = type_counts.get("boolean", 0) + 1
            elif isinstance(value, int):
                type_counts["integer"] = type_counts.get("integer", 0) + 1
            elif isinstance(value, float):
                type_counts["float"] = type_counts.get("float", 0) + 1
            elif self._is_numeric_string(value_str):
                if '.' in value_str:
                    type_counts["float"] = type_counts.get("float", 0) + 1
                else:
                    type_counts["integer"] = type_counts.get("integer", 0) + 1
            elif self._is_date_string(value_str):
                type_counts["datetime"] = type_counts.get("datetime", 0) + 1
            else:
                type_counts["string"] = type_counts.get("string", 0) + 1
        
        # Return the most specific pattern match first
        if pattern_matches:
            return max(pattern_matches.keys(), key=pattern_matches.get)
        
        # Return the most common basic type
        if type_counts:
            return max(type_counts.keys(), key=type_counts.get)
        
        return "string"
    
    def _is_numeric_string(self, value: str) -> bool:
        """Check if string represents a number."""
        try:
            float(value.replace(',', ''))
            return True
        except (ValueError, AttributeError):
            return False
    
    def _is_date_string(self, value: str) -> bool:
        """Check if string represents a date."""
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}',
            r'^\d{2}/\d{2}/\d{4}',
            r'^\d{2}-\d{2}-\d{4}',
            r'^\w+ \d{1,2}, \d{4}'
        ]
        
        return any(re.match(pattern, value) for pattern in date_patterns)
    
    def _standardize_dataframe_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize DataFrame column types."""
        for column in df.columns:
            try:
                # Try to convert numeric columns
                if df[column].dtype == 'object':
                    # Try numeric conversion
                    numeric_series = pd.to_numeric(df[column], errors='coerce')
                    if not numeric_series.isna().all():
                        df[column] = numeric_series
                    
                    # Try datetime conversion
                    elif self.config["date_inference"]:
                        try:
                            datetime_series = pd.to_datetime(df[column], errors='coerce')
                            if not datetime_series.isna().all():
                                df[column] = datetime_series
                        except:
                            pass
            except Exception as e:
                self.logger.debug(f"Could not standardize column {column}: {str(e)}")
        
        return df
    
    def _handle_mixed_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle columns with mixed data types."""
        for column in df.columns:
            if df[column].dtype == 'object':
                # Convert mixed types to strings
                df[column] = df[column].astype(str)
        
        return df
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DataFrame data."""
        cleaned = df.copy()
        
        # Remove completely empty rows
        cleaned = cleaned.dropna(how='all')
        
        # Clean string columns
        for column in cleaned.select_dtypes(include=['object']).columns:
            cleaned[column] = cleaned[column].astype(str).str.strip()
            # Replace empty strings with NaN
            cleaned[column] = cleaned[column].replace('', np.nan)
        
        return cleaned
    
    def _clean_scalar(self, value: Any) -> Any:
        """Clean scalar values."""
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return value