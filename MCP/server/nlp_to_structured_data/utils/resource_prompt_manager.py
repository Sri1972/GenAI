"""
Resource and Prompt Manager for NLP to Structured Data System

Centralized management of resources and prompts that can be shared
between MCP server and agents for consistency.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import logging


class ResourceManager:
    """Manages access to resource files for the data analysis system."""
    
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            # Default to the project root's resources directory
            current_file = Path(__file__)
            self.base_path = current_file.parent.parent / "resources"
        else:
            self.base_path = Path(base_path)
        
        self.logger = logging.getLogger("utils.resource_manager")
        
    def get_resource_list(self) -> List[Dict[str, str]]:
        """Get list of available resources including both static resources and metadata files."""
        resources = []
        
        # Add static resource files
        if self.base_path.exists():
            for file_path in self.base_path.glob("*.txt"):
                resources.append({
                    "name": file_path.stem,
                    "uri": f"nlp-data://resources/{file_path.stem}",
                    "description": self._get_resource_description(file_path),
                    "file_path": str(file_path),
                    "type": "static_resource"
                })
        
        # Add metadata files from metadata/ directory
        metadata_base = self.base_path.parent / "metadata"
        if metadata_base.exists():
            for data_type_dir in metadata_base.iterdir():
                if data_type_dir.is_dir():
                    data_type = data_type_dir.name
                    for metadata_file in data_type_dir.glob("*.json"):
                        resources.append({
                            "name": f"metadata_{data_type}_{metadata_file.stem}",
                            "uri": f"nlp-data://metadata/{data_type}/{metadata_file.stem}",
                            "description": f"Metadata for {data_type} data: {metadata_file.stem}",
                            "file_path": str(metadata_file),
                            "type": "metadata",
                            "data_type": data_type
                        })
        
        return resources
    
    def read_resource(self, resource_name: str) -> str:
        """Read a specific resource file or metadata file."""
        # Check if it's a metadata resource
        if resource_name.startswith("metadata_"):
            return self._read_metadata_resource(resource_name)
        
        # Handle static resource files
        file_path = self.base_path / f"{resource_name}.txt"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Resource not found: {resource_name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read resource {resource_name}: {e}")
            raise
    
    def _read_metadata_resource(self, resource_name: str) -> str:
        """Read a metadata resource file."""
        # Parse metadata resource name: metadata_{data_type}_{filename}
        parts = resource_name.split("_", 2)
        if len(parts) < 3:
            raise FileNotFoundError(f"Invalid metadata resource name: {resource_name}")
        
        data_type = parts[1]
        filename = parts[2]
        
        metadata_path = self.base_path.parent / "metadata" / data_type / f"{filename}.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata resource not found: {resource_name}")
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            self.logger.error(f"Failed to read metadata resource {resource_name}: {e}")
            raise
    
    def _get_resource_description(self, file_path: Path) -> str:
        """Extract description from resource file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read first few lines to get description
                lines = f.readlines()[:5]
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        return line
                return f"Resource file: {file_path.stem}"
        except:
            return f"Resource file: {file_path.stem}"


class PromptManager:
    """Manages access to prompt templates for the data analysis system."""
    
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            # Default to the project root's prompts directory  
            current_file = Path(__file__)
            self.base_path = current_file.parent.parent / "prompts"
        else:
            self.base_path = Path(base_path)
        
        self.logger = logging.getLogger("utils.prompt_manager")
        
    def get_prompt_list(self) -> List[Dict[str, str]]:
        """Get list of available prompt templates."""
        prompts = []
        
        if not self.base_path.exists():
            return prompts
            
        for file_path in self.base_path.glob("*.txt"):
            prompts.append({
                "name": file_path.stem,
                "description": self._get_prompt_description(file_path),
                "file_path": str(file_path)
            })
        
        return prompts
    
    def get_prompt(self, prompt_name: str, **kwargs) -> str:
        """Get a prompt template with optional formatting."""
        file_path = self.base_path / f"{prompt_name}.txt"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Apply formatting if kwargs provided
            if kwargs:
                try:
                    template = template.format(**kwargs)
                except KeyError as e:
                    self.logger.warning(f"Missing template variable in {prompt_name}: {e}")
            
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to read prompt {prompt_name}: {e}")
            raise
    
    def _get_prompt_description(self, file_path: Path) -> str:
        """Extract description from prompt file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Look for description in first few lines
                lines = f.readlines()[:10]
                description_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line.startswith("CONTEXT:") or line.startswith("DESCRIPTION:"):
                        # Next line usually contains the description
                        continue
                    elif line and not line.startswith("#") and len(line) > 20:
                        description_lines.append(line)
                        if len(description_lines) >= 2:
                            break
                
                if description_lines:
                    return ". ".join(description_lines)[:200] + "..."
                
                return f"Prompt template: {file_path.stem}"
        except:
            return f"Prompt template: {file_path.stem}"


# Singleton instances for easy access
_resource_manager = None
_prompt_manager = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


# Convenience functions
def read_resource(resource_name: str) -> str:
    """Read a resource file."""
    return get_resource_manager().read_resource(resource_name)


def get_prompt(prompt_name: str, **kwargs) -> str:
    """Get a formatted prompt template."""
    return get_prompt_manager().get_prompt(prompt_name, **kwargs)


def list_resources() -> List[Dict[str, str]]:
    """List available resources."""
    return get_resource_manager().get_resource_list()


def list_prompts() -> List[Dict[str, str]]:
    """List available prompts."""
    return get_prompt_manager().get_prompt_list()


def get_metadata_for_data_type(data_type: str) -> List[Dict[str, str]]:
    """Get all metadata files for a specific data type (csv, excel, json, api)."""
    resource_manager = get_resource_manager()
    all_resources = resource_manager.get_resource_list()
    
    metadata_resources = []
    for resource in all_resources:
        if resource.get("type") == "metadata" and resource.get("data_type") == data_type:
            metadata_resources.append(resource)
    
    return metadata_resources


def read_metadata(data_type: str, filename: str) -> str:
    """Read a specific metadata file."""
    resource_name = f"metadata_{data_type}_{filename}"
    return get_resource_manager().read_resource(resource_name)