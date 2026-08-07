# PMO Model Context Protocol (MCP) Server

## Overview
Comprehensive MCP server providing programmatic access to Project Management Office (PMO) data through REST API integration.

## Core Components

### **pmo_comprehensive.py** - Main MCP Server
Complete implementation with **18 specialized tools** covering:
- **Project Management**: Get projects, filter by portfolio/product line, dynamic filtering
- **Resource Management**: Resource discovery, capacity allocation, utilization analysis  
- **Organizational Structure**: Business lines, strategic portfolios, product lines
- **Capacity Planning**: Time-based resource allocation and project resource planning
- **Metadata-Driven Documentation**: Field definitions, API endpoints, request validation

### **Metadata Integration** 🆕
The MCP server now **actively uses the JSON metadata files** for:
- **Dynamic field descriptions** with constraints and business context
- **Request validation** against metadata field constraints  
- **Enhanced error handling** with metadata-aware error messages
- **Auto-generated documentation** from structured metadata
- **Field enumeration** and validation from metadata definitions

## Directory Structure

```
pmo/
├── pmo_comprehensive.py          # Main MCP server implementation (18 tools)
├── metadata/                     # 🆕 ACTIVELY USED - API metadata and documentation (7 files)
│   ├── api_master_index.metadata.json      # Central registry (LOADED)
│   ├── business_lines_api.metadata.json    # Organizational structure APIs (LOADED)
│   ├── projects_api.metadata.json          # Project management APIs (LOADED)
│   ├── resources_api.metadata.json         # Resource management APIs (LOADED)
│   ├── allocations_api.metadata.json       # Allocation APIs (LOADED)
│   ├── managers_timeoff_api.metadata.json  # Hierarchy and time off APIs (LOADED)
│   └── allocation_actual_import_api.metadata.json # Import APIs (LOADED)
├── examples/                     # Example implementations and utilities
├── docs/                        # Implementation guides and analysis
└── [standard Python project files]
```

## Tools Available

### Project Management Tools (5)
- `get_all_projects()` - Complete project list **with metadata context**
- `get_project_by_id(id)` - Specific project details
- `get_project_by_name(name)` - Find project by name
- `get_projects_by_portfolio_and_product_line()` - Filter by organizational structure
- `get_projects_dynamic_filter()` - Advanced filtering with custom conditions

### Resource Management Tools (3)
- `get_all_resources()` - Complete resource directory
- `get_resource_by_id(id)` - Specific resource details
- `get_resource_by_name(name)` - Find resource by name

### Capacity & Allocation Tools (3)
- `get_resource_capacity_allocation()` - Resource capacity over time
- `get_project_resource_allocation()` - Resources allocated to specific project
- `get_resources_by_portfolio_allocation()` - Portfolio-based resource allocation

### Organizational Structure Tools (3)
- `get_business_lines()` - Complete organizational hierarchy
- `get_strategic_portfolios()` - Strategic portfolio list
- `get_product_lines_by_portfolio()` - Product lines within portfolio

### 🆕 Metadata-Driven Documentation Tools (3)
- `get_api_field_definitions(entity_type)` - Field definitions with constraints from metadata
- `get_api_endpoints_summary()` - Complete API endpoint overview from metadata
- `validate_api_request_data(entity_type, data)` - Request validation using metadata constraints

### Built-in Prompts (4)
- `project_overview` - Comprehensive project portfolio analysis
- `resource_utilization_analysis` - Resource capacity and utilization insights
- `portfolio_deep_dive` - Detailed portfolio-level analysis
- `project_resource_planning` - Resource planning and optimization

## Features

### 🆕 Metadata-Powered Intelligence
- **Dynamic field descriptions** loaded from JSON metadata files
- **Automatic validation** against metadata field constraints
- **Enhanced error messages** with metadata context and guidance
- **Self-documenting APIs** with business rules and field meanings
- **Real-time field enumeration** for valid values and constraints

### Smart Helper Functions
- Automatic project/resource name-to-ID resolution
- Centralized error handling with metadata-enhanced debugging
- Case-sensitive validation guidance with available values
- Field constraint validation using metadata definitions

### Response Formats
- Structured JSON responses from PMO API
- **Metadata context** included in successful responses
- Enhanced error handling and user feedback
- Optional field selection for optimized queries

### API Integration
- RESTful integration with PMO backend (localhost:5000)
- Support for filtering, dynamic queries, and time-based analysis
- Comprehensive parameter validation and error handling

## Metadata System

### Comprehensive Documentation
- **6 metadata files** covering all API endpoints
- **Business context** and governance information
- **Field definitions** with constraints and validation rules
- **Usage patterns** and workflow guidance

### Single Source of Truth
- All field definitions centralized in metadata
- Resource files focus on usage context
- No duplication between documentation files
- Consistent formatting and structure

## Usage

The MCP server is designed to be consumed by LLM clients for:
- Project portfolio analysis and reporting
- Resource utilization and capacity planning
- Organizational structure navigation
- Cross-portfolio resource optimization

### Development Notes

### 🆕 Metadata Integration Architecture
- ✅ **Active metadata usage** - All 7 JSON metadata files loaded and used
- ✅ **Dynamic field validation** - Constraints enforced from metadata
- ✅ **Self-documenting tools** - Descriptions generated from metadata
- ✅ **Enhanced error handling** - Metadata-aware error messages
- ✅ **Eliminated redundancy** - Removed unused text files, single source of truth in JSON

### Clean Architecture
- ✅ **Metadata-driven design** - All field info comes from structured JSON metadata
- ✅ **Removed redundant text files** - Replaced with dynamic metadata loading
- ✅ **Enhanced validation** - Field constraints validated against metadata
- ✅ **Improved documentation** - Auto-generated from comprehensive metadata

### Production Ready
- Comprehensive error handling
- Debug logging for API calls
- Graceful degradation for network issues
- Optimized for LLM client consumption
