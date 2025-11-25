"""
PowerPoint MCP Prompts

Pre-configured prompts for common PowerPoint generation tasks.
"""

from typing import Dict, List

# Prompt templates for common presentation scenarios
PROMPTS = {
    "create_business_presentation": {
        "name": "create_business_presentation",
        "description": "Create a professional business presentation with standard sections",
        "template": """Create a business presentation with the following structure:
1. Title slide with company name and topic
2. Executive summary with key points
3. Problem statement
4. Proposed solution
5. Benefits and ROI
6. Implementation timeline
7. Conclusion and next steps

Use professional formatting and include relevant charts where applicable."""
    },
    
    "create_technical_presentation": {
        "name": "create_technical_presentation",
        "description": "Create a technical architecture or system design presentation",
        "template": """Create a technical presentation with:
1. Title slide with system/project name
2. Architecture overview diagram
3. Component breakdown
4. Technology stack
5. Data flow and integration points
6. Security considerations
7. Performance metrics

Use diagrams and technical details where appropriate."""
    },
    
    "create_data_analysis_presentation": {
        "name": "create_data_analysis_presentation",
        "description": "Create a data analysis presentation with charts and insights",
        "template": """Create a data analysis presentation including:
1. Title and overview
2. Data sources and methodology
3. Key findings with supporting charts
4. Trend analysis
5. Insights and recommendations
6. Next steps

Focus on visual data representation with charts and tables."""
    },
    
    "create_project_status_presentation": {
        "name": "create_project_status_presentation",
        "description": "Create a project status update presentation",
        "template": """Create a project status presentation with:
1. Title slide with project name and date
2. Executive summary
3. Milestones achieved
4. Current progress (with progress charts)
5. Upcoming tasks
6. Risks and issues
7. Budget status
8. Next steps

Include visual progress indicators and status charts."""
    },
    
    "slide_design_guidelines": {
        "name": "slide_design_guidelines",
        "description": "Best practices for slide design and content organization",
        "template": """Follow these slide design principles:

Content:
- Keep text concise (5-7 bullet points max per slide)
- Use one main idea per slide
- Avoid complete sentences, use bullet points
- Include visual elements (charts, diagrams, images)

Layout:
- Maintain consistent fonts and colors
- Use high contrast for readability
- Leave sufficient white space
- Align elements consistently

Charts and Data:
- Label all axes and data points clearly
- Use appropriate chart types for data
- Limit colors to 3-5 per chart
- Include data sources

Accessibility:
- Use readable font sizes (minimum 24pt for body text)
- Ensure color contrast meets standards
- Provide alt text for images"""
    },
    
    "chart_selection_guide": {
        "name": "chart_selection_guide",
        "description": "Guide for selecting appropriate chart types for different data",
        "template": """Chart Type Selection Guide:

BAR CHARTS:
- Use for comparing categories
- Best for showing differences between groups
- Good for ranking data
- Horizontal orientation for long labels

COLUMN CHARTS:
- Similar to bar charts but vertical
- Better for time-series with few data points
- Good for showing changes over time

LINE CHARTS:
- Best for continuous data over time
- Show trends and patterns
- Good for multiple series comparison
- Useful for forecasting

PIE CHARTS:
- Show parts of a whole (100%)
- Best with 3-6 segments
- Use for simple proportions
- Avoid for precise comparisons

TABLE:
- Use when exact values are important
- Good for detailed data presentation
- Best when comparisons need precision
- Limit to 5-7 columns for readability"""
    }
}


def get_prompt(prompt_name: str) -> Dict[str, str]:
    """
    Get a specific prompt template.
    
    Args:
        prompt_name: Name of the prompt to retrieve
        
    Returns:
        Dict with prompt information
    """
    return PROMPTS.get(prompt_name, {})


def list_prompts() -> List[Dict[str, str]]:
    """
    List all available prompts.
    
    Returns:
        List of prompt metadata
    """
    return [
        {
            "name": prompt_name,
            "description": prompt_data["description"]
        }
        for prompt_name, prompt_data in PROMPTS.items()
    ]


def get_prompt_template(prompt_name: str) -> str:
    """
    Get the template text for a specific prompt.
    
    Args:
        prompt_name: Name of the prompt
        
    Returns:
        Template text or empty string if not found
    """
    prompt = PROMPTS.get(prompt_name, {})
    return prompt.get("template", "")
