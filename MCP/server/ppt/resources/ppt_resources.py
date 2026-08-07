"""
PowerPoint MCP Resources

Static and dynamic resources for presentation templates and configurations.
"""

from typing import Dict, List, Any
from pathlib import Path
import json

# Default presentation configurations
DEFAULT_CONFIGS = {
    "standard": {
        "name": "Standard Business Template",
        "description": "Professional business presentation template",
        "slide_width": 10,  # inches
        "slide_height": 7.5,  # inches
        "font_name": "Calibri",
        "font_size": {
            "title": 44,
            "heading": 32,
            "body": 24
        },
        "colors": {
            "primary": "#1F4E78",
            "secondary": "#4472C4",
            "accent": "#ED7D31",
            "text": "#000000",
            "background": "#FFFFFF"
        }
    },
    
    "technical": {
        "name": "Technical Presentation Template",
        "description": "Template for technical and architecture presentations",
        "slide_width": 10,
        "slide_height": 7.5,
        "font_name": "Segoe UI",
        "font_size": {
            "title": 40,
            "heading": 28,
            "body": 20
        },
        "colors": {
            "primary": "#0078D4",
            "secondary": "#106EBE",
            "accent": "#00BCF2",
            "text": "#323130",
            "background": "#F3F2F1"
        }
    },
    
    "modern": {
        "name": "Modern Minimal Template",
        "description": "Clean, minimal design for contemporary presentations",
        "slide_width": 10,
        "slide_height": 7.5,
        "font_name": "Arial",
        "font_size": {
            "title": 48,
            "heading": 32,
            "body": 24
        },
        "colors": {
            "primary": "#2C3E50",
            "secondary": "#34495E",
            "accent": "#E74C3C",
            "text": "#2C3E50",
            "background": "#ECF0F1"
        }
    }
}

# Layout guides
LAYOUT_GUIDES = {
    "title_slide": {
        "layout_index": 0,
        "description": "Title slide with main title and subtitle",
        "placeholders": ["title", "subtitle"]
    },
    "title_and_content": {
        "layout_index": 1,
        "description": "Title with content area below",
        "placeholders": ["title", "body"]
    },
    "section_header": {
        "layout_index": 2,
        "description": "Section divider with large title",
        "placeholders": ["title"]
    },
    "two_content": {
        "layout_index": 3,
        "description": "Title with two side-by-side content areas",
        "placeholders": ["title", "content_left", "content_right"]
    },
    "comparison": {
        "layout_index": 4,
        "description": "Compare two items side by side",
        "placeholders": ["title", "left_content", "right_content"]
    },
    "title_only": {
        "layout_index": 5,
        "description": "Title with blank content area",
        "placeholders": ["title"]
    },
    "blank": {
        "layout_index": 6,
        "description": "Completely blank slide",
        "placeholders": []
    }
}

# Slide content best practices
CONTENT_GUIDELINES = {
    "text": {
        "max_bullets_per_slide": 7,
        "max_words_per_bullet": 10,
        "max_characters_per_line": 50,
        "recommended_font_size_range": [18, 28]
    },
    "charts": {
        "max_data_series": 5,
        "max_categories": 10,
        "recommended_types": ["bar", "column", "line", "pie"],
        "color_palette": ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"]
    },
    "tables": {
        "max_columns": 7,
        "max_rows": 10,
        "recommended_column_width": 1.5,  # inches
        "recommended_row_height": 0.4  # inches
    },
    "images": {
        "recommended_formats": ["PNG", "JPG", "SVG"],
        "max_file_size_mb": 5,
        "recommended_dpi": 150
    }
}


class ResourceManager:
    """Manages PowerPoint resources and configurations."""
    
    def __init__(self, resource_dir: str = "resources"):
        self.resource_dir = Path(resource_dir)
        self.resource_dir.mkdir(exist_ok=True)
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """Get a presentation configuration template."""
        return DEFAULT_CONFIGS.get(config_name, DEFAULT_CONFIGS["standard"])
    
    def list_configs(self) -> List[Dict[str, str]]:
        """List all available configuration templates."""
        return [
            {
                "name": name,
                "description": config["description"]
            }
            for name, config in DEFAULT_CONFIGS.items()
        ]
    
    def get_layout_guide(self, layout_name: str) -> Dict[str, Any]:
        """Get information about a specific layout."""
        return LAYOUT_GUIDES.get(layout_name, {})
    
    def list_layouts(self) -> List[Dict[str, Any]]:
        """List all available slide layouts."""
        return [
            {
                "name": name,
                "description": layout["description"],
                "placeholders": layout["placeholders"]
            }
            for name, layout in LAYOUT_GUIDES.items()
        ]
    
    def get_content_guidelines(self, content_type: str = None) -> Dict[str, Any]:
        """
        Get content guidelines for presentation elements.
        
        Args:
            content_type: Specific type (text, charts, tables, images) or None for all
            
        Returns:
            Guidelines dictionary
        """
        if content_type and content_type in CONTENT_GUIDELINES:
            return CONTENT_GUIDELINES[content_type]
        return CONTENT_GUIDELINES
    
    def save_template(self, template_name: str, template_path: str) -> Dict[str, Any]:
        """Save a template file path for future use."""
        templates_file = self.resource_dir / "templates.json"
        
        templates = {}
        if templates_file.exists():
            with open(templates_file, 'r') as f:
                templates = json.load(f)
        
        templates[template_name] = str(Path(template_path).absolute())
        
        with open(templates_file, 'w') as f:
            json.dump(templates, f, indent=2)
        
        return {
            "success": True,
            "message": f"Saved template '{template_name}'"
        }
    
    def get_template_path(self, template_name: str) -> str:
        """Get the file path for a saved template."""
        templates_file = self.resource_dir / "templates.json"
        
        if not templates_file.exists():
            return ""
        
        with open(templates_file, 'r') as f:
            templates = json.load(f)
        
        return templates.get(template_name, "")
    
    def list_templates(self) -> List[str]:
        """List all saved template names."""
        templates_file = self.resource_dir / "templates.json"
        
        if not templates_file.exists():
            return []
        
        with open(templates_file, 'r') as f:
            templates = json.load(f)
        
        return list(templates.keys())
