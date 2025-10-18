from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
import requests
from urllib.parse import quote

api_url = "http://localhost:5000"

mcp = FastMCP("PMO")

# ================================================================================
# SERVER INSTRUCTIONS AND GENERAL RESOURCES
# ================================================================================

'''
@mcp.resource("pmo://system/instructions")
def server_instructions() -> str:
    return """
PMO (Project Management Office) Server - Provides access to project data and business intelligence.

QUERY ROUTING:
- For "all projects" (no filters) → use get_all_projects()
- For specific area queries → use get_business_lines() then get_all_projects_filtered()

DATA HANDLING:
- strategic_portfolio and product_line are case-sensitive
- Handle approximate/partial names by matching against business_lines
- technology_project accepts only "YES"/"NO" values
- Missing data fields may be null - always check before processing

WORKFLOW PATTERNS:
- Always validate user input against business_lines for filtered queries
- Use exact case-sensitive values from business_lines data
- Provide structured summaries with counts and resource breakdowns
"""
'''

# ================================================================================
# BUSINESS LINES SECTION
# ================================================================================

@mcp.tool()
def get_business_lines() -> List[Dict[str, Any]]:
    """
    Fetch all available business lines (strategic portfolios and product lines).
    Use this for validation and to understand the data structure before filtering.
    """
    try:
        url = f"{api_url}/business_lines"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_business_lines: {str(e)}"}]

@mcp.resource("pmo://docs/business_lines")
def business_lines_doc() -> str:
    return """
Business Lines Data Structure:
- strategic_portfolio: High-level business area (e.g., "Market & Sell", "Vehicles In Use")
- product_line: Specific product area (e.g., "VIN Solutions", "NA Industry Performance") 
- The combination defines the business context for projects

Case Sensitivity: All values are case-sensitive and must match exactly for filtering
"""

@mcp.prompt("business_lines_validation")
def business_lines_prompt() -> str:
    return """
Business Lines Validation Workflow:

When user provides portfolio/product line names (possibly approximate):
1. Call get_business_lines() to get exact values
2. Match user input against both strategic_portfolio and product_line fields
3. Handle variations: lowercase, partial matches, common abbreviations
4. Return exact case-sensitive values for subsequent filtering
5. If no match found, suggest closest alternatives

Examples:
- "vin solutions" → "VIN Solutions" (product_line)
- "market and sell" → "Market & Sell" (strategic_portfolio)
- "na industry" → "NA Industry Performance" (product_line)
"""

# ================================================================================
# ALL PROJECTS SECTION (Unfiltered)
# ================================================================================

@mcp.tool()
def get_all_projects() -> List[Dict[str, Any]]:
    """
    Fetch all projects without any filters. Use for comprehensive overviews.
    Returns complete project dataset with all fields.
    """
    try:
        url = f"{api_url}/projects"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_all_projects: {str(e)}"}]

@mcp.resource("pmo://docs/all_projects")
def all_projects_doc() -> str:
    return """
Complete Project Data Fields:

IDENTIFICATION:
- project_id: Unique identifier
- project_name: Display name
- strategic_portfolio: Business area
- product_line: Product area

PROJECT DETAILS:
- project_type: Category (e.g., "BladeRunner", "Concord", "New Product")
- project_description: Detailed description
- vitality, strategic, aim: Project classification flags

FINANCIAL:
- revenue_est_growth_pa: Annual growth estimate
- revenue_est_current_year: Current year revenue estimate
- revenue_est_current_year_plus_[1,2,3]: Future year estimates

TIMELINE:
- start_date_est, end_date_est: Estimated dates (YYYY-MM-DD)
- start_date_actual, end_date_actual: Actual dates (YYYY-MM-DD or null)

STATUS:
- current_status: Text status (e.g., "Work In Progress", "Not Started")
- rag_status: RAG indicator ("Red", "Amber", "Green", "N/A")

RESOURCES:
- project_resource_hours_planned/actual: Total hours
- project_resource_cost_planned/actual: Total costs
- resource_role_summary: Detailed breakdown by role (nested JSON)

METADATA:
- technology_project: "YES"/"NO" flag
- timesheet_project_name: Name used in timesheets
- comments, added_by, added_date, updated_by, updated_date: Audit trail
"""

@mcp.prompt("all_projects_summary")
def all_projects_prompt() -> str:
    return """
All Projects Summary Workflow:

For unfiltered "all projects" requests:
1. Call get_all_projects() directly (no business_lines call needed)
2. Organize results by strategic_portfolio and product_line
3. Provide summary statistics:
   - Total project count
   - Count by strategic_portfolio
   - Count by product_line
   - Count by project status
4. Resource summaries:
   - Total planned vs actual hours
   - Total planned vs actual costs
   - Resource breakdown by portfolio/product line
5. Highlight projects with missing data or unusual status
6. Format as structured overview with key insights
"""

# ================================================================================
# FILTERED PROJECTS SECTION
# ================================================================================

@mcp.tool()
def get_filtered_projects(
    strategic_portfolio: Optional[str] = None,
    product_line: Optional[str] = None,
    technology_project: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch projects filtered by strategic portfolio, product line, or technology flag.
    Use get_business_lines() first to ensure correct case-sensitive parameter values.
    """
    try:
        params = {}
        if strategic_portfolio:
            params["strategic_portfolio"] = strategic_portfolio
        if product_line:
            params["product_line"] = product_line
        if technology_project:
            params["technology_project"] = technology_project

        url = f"{api_url}/projects_filter"
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return [{"error": f"API request failed: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error in get_filtered_projects: {str(e)}"}]

@mcp.resource("pmo://docs/filtered_projects")
def filtered_projects_doc() -> str:
    return """
Project Filtering Options:

STRATEGIC PORTFOLIO (strategic_portfolio):
- "Auto Insights": AI and analytics projects
- "Market & Sell": Marketing and sales initiatives  
- "Plan & Build": Development and construction
- "Vehicles In Use": Post-sale vehicle services

PRODUCT LINE (product_line):
- "VIN Solutions": Vehicle identification services
- "NA Industry Performance": North America industry analytics
- "Cross-Product": Multi-product initiatives
- "Commercial", "PAS", "Recall", "SCT", etc.: Specific product areas

TECHNOLOGY PROJECT (technology_project):
- "YES": Technology-focused projects
- "NO": Business/operational projects

USAGE:
- Use exact case-sensitive values from get_business_lines()
- Can combine multiple filters (e.g., strategic_portfolio + technology_project)
- Empty/null parameters are ignored (acts as wildcard)
"""

@mcp.prompt("filtered_projects_workflow")
def filtered_projects_prompt() -> str:
    return """
Filtered Projects Workflow:

For specific portfolio/product/technology queries:
1. VALIDATION PHASE:
   - Call get_business_lines() to get valid filter values
   - Match user input against strategic_portfolio and product_line fields
   - Normalize case and handle partial matches

2. FILTERING PHASE:
   - Call get_all_projects_filtered() with exact matched values
   - Use only validated parameters from step 1

3. ANALYSIS PHASE:
   - Summarize filtered results with context
   - Compare to overall portfolio if relevant
   - Highlight key metrics: timelines, resources, status

PARAMETER MAPPING:
- User says "VIN Solutions" → product_line="VIN Solutions"  
- User says "Market & Sell" → strategic_portfolio="Market & Sell"
- User says "tech projects" → technology_project="YES"

ERROR HANDLING:
- If no matches found, suggest similar values from business_lines
- If ambiguous input, ask for clarification with available options
"""

if __name__ == "__main__":
    mcp.run()