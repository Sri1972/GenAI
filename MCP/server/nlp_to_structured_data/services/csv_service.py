"""
CSV Service for NLP to Structured Data System

Handles CSV file loading, parsing, and basic operations.
Provides clean interface for CSV data manipulation.
"""

import pandas as pd
import aiofiles
import asyncio
from typing import Optional, Dict, Any, List, Union
import chardet
import logging
from pathlib import Path
import requests
from io import StringIO, BytesIO


class CSVService:
    """
    Service for handling CSV file operations.
    
    Provides async methods for loading, parsing, and basic manipulation
    of CSV data from various sources (local files, URLs, etc.).
    """
    
    def __init__(self):
        self.logger = logging.getLogger("services.csv_service")
        self.logger.setLevel(logging.INFO)
    
    async def load_csv(self, 
                      source: str, 
                      encoding: Optional[str] = None,
                      delimiter: Optional[str] = None,
                      **kwargs) -> pd.DataFrame:
        """
        Load CSV data from file path or URL.
        
        Args:
            source: File path or URL to CSV
            encoding: Character encoding (auto-detected if None)
            delimiter: Column delimiter (auto-detected if None)
            **kwargs: Additional pandas read_csv parameters
            
        Returns:
            Loaded DataFrame
        """
        try:
            if source.startswith(('http://', 'https://')):
                return await self._load_from_url(source, encoding, delimiter, **kwargs)
            else:
                return await self._load_from_file(source, encoding, delimiter, **kwargs)
                
        except Exception as e:
            self.logger.error(f"Failed to load CSV from {source}: {str(e)}")
            raise
    
    async def _load_from_file(self, 
                             file_path: str, 
                             encoding: Optional[str] = None,
                             delimiter: Optional[str] = None,
                             **kwargs) -> pd.DataFrame:
        """
        Load CSV from local file.
        
        Args:
            file_path: Path to CSV file
            encoding: Character encoding
            delimiter: Column delimiter
            **kwargs: Additional pandas parameters
            
        Returns:
            Loaded DataFrame
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Auto-detect encoding if not specified
        if encoding is None:
            encoding = await self._detect_encoding(file_path)
        
        # Auto-detect delimiter if not specified
        if delimiter is None:
            delimiter = await self._detect_delimiter(file_path, encoding)
        
        # Load CSV with pandas
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            delimiter=delimiter,
            **kwargs
        )
        
        self.logger.info(f"Loaded CSV: {len(df)} rows, {len(df.columns)} columns from {file_path}")
        return df
    
    async def _load_from_url(self, 
                            url: str, 
                            encoding: Optional[str] = None,
                            delimiter: Optional[str] = None,
                            **kwargs) -> pd.DataFrame:
        """
        Load CSV from URL.
        
        Args:
            url: URL to CSV file
            encoding: Character encoding
            delimiter: Column delimiter
            **kwargs: Additional pandas parameters
            
        Returns:
            Loaded DataFrame
        """
        # Download content
        response = requests.get(url)
        response.raise_for_status()
        
        content = response.content
        
        # Auto-detect encoding if not specified
        if encoding is None:
            detected = chardet.detect(content)
            encoding = detected.get('encoding', 'utf-8')
        
        # Convert to string
        content_str = content.decode(encoding)
        
        # Auto-detect delimiter if not specified
        if delimiter is None:
            delimiter = self._detect_delimiter_from_content(content_str)
        
        # Load CSV with pandas
        df = pd.read_csv(
            StringIO(content_str),
            delimiter=delimiter,
            **kwargs
        )
        
        self.logger.info(f"Loaded CSV from URL: {len(df)} rows, {len(df.columns)} columns")
        return df
    
    async def _detect_encoding(self, file_path: str) -> str:
        """
        Detect file encoding.
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected encoding
        """
        async with aiofiles.open(file_path, 'rb') as f:
            raw_data = await f.read(10000)  # Read first 10KB
            
        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'utf-8')
        confidence = detected.get('confidence', 0)
        
        self.logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
        return encoding
    
    async def _detect_delimiter(self, file_path: str, encoding: str) -> str:
        """
        Detect CSV delimiter.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding
            
        Returns:
            Detected delimiter
        """
        async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
            sample = await f.read(1024)  # Read first 1KB
            
        return self._detect_delimiter_from_content(sample)
    
    def _detect_delimiter_from_content(self, content: str) -> str:
        """
        Detect delimiter from content sample.
        
        Args:
            content: Sample content
            
        Returns:
            Detected delimiter
        """
        # Common delimiters to check
        delimiters = [',', ';', '\t', '|']
        
        delimiter_counts = {}
        for delimiter in delimiters:
            # Count occurrences in first few lines
            lines = content.split('\n')[:5]
            counts = [line.count(delimiter) for line in lines if line.strip()]
            
            if counts:
                # Check if delimiter count is consistent across lines
                avg_count = sum(counts) / len(counts)
                consistency = 1 - (max(counts) - min(counts)) / (max(counts) + 1)
                
                delimiter_counts[delimiter] = avg_count * consistency
        
        # Choose delimiter with highest score
        if delimiter_counts:
            best_delimiter = max(delimiter_counts.items(), key=lambda x: x[1])[0]
            self.logger.info(f"Detected delimiter: '{best_delimiter}'")
            return best_delimiter
        
        # Default to comma
        return ','
    
    async def save_csv(self, 
                      df: pd.DataFrame, 
                      file_path: str,
                      encoding: str = 'utf-8',
                      **kwargs) -> None:
        """
        Save DataFrame to CSV file.
        
        Args:
            df: DataFrame to save
            file_path: Output file path
            encoding: Character encoding
            **kwargs: Additional pandas to_csv parameters
        """
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save CSV
        df.to_csv(file_path, encoding=encoding, index=False, **kwargs)
        
        self.logger.info(f"Saved CSV: {len(df)} rows to {file_path}")
    
    def get_csv_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get comprehensive information about CSV data.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            CSV information dictionary
        """
        info = {
            "shape": {
                "rows": len(df),
                "columns": len(df.columns)
            },
            "columns": {
                "names": df.columns.tolist(),
                "dtypes": df.dtypes.to_dict()
            },
            "memory": {
                "usage_bytes": df.memory_usage(deep=True).sum(),
                "usage_mb": df.memory_usage(deep=True).sum() / (1024 * 1024)
            },
            "data_quality": {
                "has_nulls": df.isnull().any().any(),
                "null_counts": df.isnull().sum().to_dict(),
                "duplicate_rows": df.duplicated().sum()
            }
        }
        
        # Add sample data
        if len(df) > 0:
            info["sample"] = {
                "head": df.head(3).to_dict('records'),
                "tail": df.tail(3).to_dict('records') if len(df) > 3 else []
            }
        
        return info
    
    async def validate_csv_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Validate CSV file structure without loading full data.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Validation results
        """
        try:
            # Read just the header and first few rows
            sample_df = pd.read_csv(file_path, nrows=5)
            
            validation = {
                "is_valid": True,
                "columns": sample_df.columns.tolist(),
                "sample_rows": len(sample_df),
                "issues": []
            }
            
            # Check for common issues
            if sample_df.columns.duplicated().any():
                validation["issues"].append("Duplicate column names detected")
            
            if sample_df.columns.str.contains(r'Unnamed:').any():
                validation["issues"].append("Unnamed columns detected")
            
            if validation["issues"]:
                validation["is_valid"] = False
            
            return validation
            
        except Exception as e:
            return {
                "is_valid": False,
                "error": str(e),
                "issues": [f"Failed to parse CSV: {str(e)}"]
            }
    
    def filter_dataframe(self, 
                        df: pd.DataFrame, 
                        filters: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply multiple filters to DataFrame.
        
        Args:
            df: DataFrame to filter
            filters: List of filter dictionaries
            
        Returns:
            Filtered DataFrame
        """
        filtered_df = df.copy()
        
        for filter_dict in filters:
            column = filter_dict.get('column')
            operator = filter_dict.get('operator', '==')
            value = filter_dict.get('value')
            
            if column not in filtered_df.columns:
                continue
            
            if operator == '==':
                filtered_df = filtered_df[filtered_df[column] == value]
            elif operator == '!=':
                filtered_df = filtered_df[filtered_df[column] != value]
            elif operator == '>':
                filtered_df = filtered_df[filtered_df[column] > value]
            elif operator == '>=':
                filtered_df = filtered_df[filtered_df[column] >= value]
            elif operator == '<':
                filtered_df = filtered_df[filtered_df[column] < value]
            elif operator == '<=':
                filtered_df = filtered_df[filtered_df[column] <= value]
            elif operator == 'contains':
                filtered_df = filtered_df[
                    filtered_df[column].astype(str).str.contains(str(value), case=False, na=False)
                ]
            elif operator == 'in':
                if isinstance(value, list):
                    filtered_df = filtered_df[filtered_df[column].isin(value)]
        
        return filtered_df
    
    def get_column_statistics(self, df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific column.
        
        Args:
            df: DataFrame
            column: Column name
            
        Returns:
            Column statistics
        """
        if column not in df.columns:
            return {"error": f"Column '{column}' not found"}
        
        col_data = df[column]
        
        stats = {
            "name": column,
            "dtype": str(col_data.dtype),
            "count": len(col_data),
            "null_count": col_data.isnull().sum(),
            "unique_count": col_data.nunique()
        }
        
        if pd.api.types.is_numeric_dtype(col_data):
            stats.update({
                "mean": col_data.mean(),
                "median": col_data.median(),
                "std": col_data.std(),
                "min": col_data.min(),
                "max": col_data.max(),
                "quartiles": {
                    "q25": col_data.quantile(0.25),
                    "q50": col_data.quantile(0.50),
                    "q75": col_data.quantile(0.75)
                }
            })
        else:
            # String/categorical statistics
            value_counts = col_data.value_counts().head(10)
            stats.update({
                "most_common": value_counts.to_dict(),
                "unique_sample": col_data.dropna().unique()[:10].tolist()
            })
        
        return stats