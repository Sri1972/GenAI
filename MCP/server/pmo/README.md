# PMO MCP Server - Refactored Version

A robust, modular, and configurable MCP server for Project Management Office (PMO) operations.

## What's New in the Refactored Version

### Key Improvements

1. **Modular Architecture**: Clean separation of concerns with dedicated modules
2. **Configuration Management**: External YAML configuration with environment variable support
3. **Externalized Prompts**: All prompts in separate YAML files for easy customization
4. **Enhanced Error Handling**: Custom exception classes with consistent error responses
5. **Comprehensive Validation**: Input validation for all fields with detailed error messages
6. **Robust API Client**: Built-in retry logic, timeout handling, and connection management
7. **Better Logging**: Structured logging with configurable levels
8. **Metadata-Driven**: Enhanced metadata management with caching

## Architecture

```
pmo_refactored/
├── config/
│   ├── __init__.py
│   ├── settings.py           # Configuration management
│   ├── config.yaml           # Main configuration file
│   ├── prompts.yaml          # Externalized prompts
│   └── .env.example          # Environment variables template
├── core/
│   ├── __init__.py
│   ├── api_client.py         # HTTP client with retry logic
│   ├── exceptions.py         # Custom exception classes
│   └── validators.py         # Input validation
├── utils/
│   ├── __init__.py
│   ├── metadata.py           # Metadata management
│   └── prompts.py            # Prompt management
├── tools/
│   ├── __init__.py
│   ├── projects.py           # Project-related tools
│   ├── resources.py          # Resource-related tools
│   └── allocations.py        # Allocation-related tools
├── server.py                 # Main server entry point
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Access to PMO API (default: http://localhost:5000)

### Setup Steps

1. **Navigate to the refactored directory**:
   ```bash
   cd D:\GenAI\MCP\server\pmo\pmo_refactored
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Or with uv:
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Copy metadata files** from parent directory:
   ```bash
   # On Windows
   xcopy /E /I ..\metadata metadata

   # On Unix/Linux/Mac
   cp -r ../metadata .
   ```

4. **Configure the server** (optional):
   - Copy `.env.example` to `.env` and customize
   - Edit `config/config.yaml` for advanced settings
   - Edit `config/prompts.yaml` to customize prompts

## Configuration

### Quick Configuration with Environment Variables

Create a `.env` file:

```env
# API Configuration
PMO_API_BASE_URL=http://localhost:5000
PMO_API_TIMEOUT=30

# Server Configuration
PMO_SERVER_DEBUG=false
PMO_LOG_LEVEL=INFO
```

### Advanced Configuration with config.yaml

Edit [`config/config.yaml`](config/config.yaml) for fine-grained control:

```yaml
api:
  base_url: "http://localhost:5000"
  timeout: 30
  retry_attempts: 3

server:
  name: "PMO"
  debug: false
  log_level: "INFO"

validation:
  strict_mode: true
  allowed_intervals:
    - "Weekly"
    - "Monthly"
    - "Quarterly"
```

### Customizing Prompts

Edit [`config/prompts.yaml`](config/prompts.yaml) to customize all prompts:

```yaml
prompts:
  project_overview:
    title: "Project Overview Analysis"
    content: |
      Your custom prompt here...
```

## Usage

### Running the Server

```bash
python server.py
```

Or with MCP:

```bash
mcp run server.py
```

### Using with Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "pmo": {
      "command": "python",
      "args": ["D:\\GenAI\\MCP\\server\\pmo\\pmo_refactored\\server.py"],
      "env": {
        "PMO_API_BASE_URL": "http://localhost:5000"
      }
    }
  }
}
```

## Available Tools

### Project Management
- `get_all_projects()` - Get all projects
- `get_project_by_id(project_id)` - Get project by ID
- `get_project_by_name(project_name)` - Get project by name
- `get_projects_by_portfolio_and_product_line()` - Filter projects
- `get_projects_dynamic_filter()` - Advanced filtering

### Resource Management
- `get_all_resources()` - Get all resources
- `get_resource_by_id(resource_id)` - Get resource by ID
- `get_resource_by_name(resource_name)` - Get resource by name
- `get_business_lines()` - Get organizational structure
- `get_strategic_portfolios()` - Get portfolios
- `get_product_lines_by_portfolio()` - Get product lines

### Capacity & Allocation
- `get_resource_capacity_allocation()` - Get resource capacity
- `get_project_resource_allocation()` - Get project allocations
- `get_resources_by_portfolio_allocation()` - Get portfolio allocations

### Metadata & Documentation
- `get_api_field_definitions(entity_type)` - Get field definitions
- `get_api_endpoints_summary()` - Get API endpoints

## Migration Guide

### From Original to Refactored Version

1. **Configuration Changes**:
   - Old: Hardcoded `api_url = "http://localhost:5000"`
   - New: Set in `config/config.yaml` or `PMO_API_BASE_URL` env var

2. **Prompt Changes**:
   - Old: Hardcoded `TOOL_SELECTION_GUIDE` string
   - New: Edit `config/prompts.yaml`

3. **Error Handling**:
   - Old: Inconsistent error returns
   - New: Consistent error format with `.to_dict()` method

4. **Validation**:
   - Old: Limited validation
   - New: Comprehensive validation with helpful error messages

5. **Metadata**:
   - Old: Manual metadata loading
   - New: Automatic caching and reload support

### Key Differences

| Feature | Original | Refactored |
|---------|----------|------------|
| Configuration | Hardcoded | YAML + env vars |
| Prompts | Embedded in code | External YAML file |
| Error Handling | Basic | Custom exceptions |
| Validation | Minimal | Comprehensive |
| Logging | Print statements | Structured logging |
| Code Organization | Single file | Modular structure |
| API Client | Direct requests | Retry + timeout handling |

## Development

### Adding New Tools

1. Create tool function in appropriate module (`tools/projects.py`, etc.)
2. Add tool registration in `server.py`
3. Add tests if needed

Example:

```python
# In tools/projects.py
def get_project_statistics() -> Dict[str, Any]:
    """Get project statistics."""
    # Implementation here
    pass

# In server.py
@mcp.tool()
def get_project_statistics() -> Dict[str, Any]:
    """Get project statistics."""
    return projects.get_project_statistics()
```

### Adding New Prompts

Edit `config/prompts.yaml`:

```yaml
prompts:
  my_new_prompt:
    title: "My New Prompt"
    description: "Description of what this prompt does"
    content: |
      Your prompt content here...
```

Register in `server.py`:

```python
@mcp.prompt("my_new_prompt")
def my_new_prompt() -> str:
    """My new prompt description."""
    return prompt_mgr.get_prompt("my_new_prompt")
```

### Adding New Validation Rules

Add to `core/validators.py`:

```python
def validate_my_field(self, value: str, field_name: str) -> str:
    """Validate custom field."""
    # Validation logic
    return value
```

## Troubleshooting

### Common Issues

1. **"Failed to connect to PMO API"**
   - Check if API server is running
   - Verify `PMO_API_BASE_URL` configuration
   - Check firewall/network settings

2. **"Metadata file not found"**
   - Ensure metadata files are copied to `metadata/` directory
   - Check file permissions

3. **"Invalid date format"**
   - Dates must be in YYYY-MM-DD format
   - Example: "2024-01-15"

4. **"Invalid interval"**
   - Must be one of: "Weekly", "Monthly", "Quarterly"
   - Check `config/config.yaml` for allowed values

### Debug Mode

Enable debug mode for detailed logging:

```env
PMO_SERVER_DEBUG=true
PMO_LOG_LEVEL=DEBUG
```

Or in `config/config.yaml`:

```yaml
server:
  debug: true
  log_level: "DEBUG"
```

## Testing

### Manual Testing

Test the server is working:

```python
# Test configuration loading
from config import get_settings
settings = get_settings()
print(f"API URL: {settings.api.base_url}")

# Test API client
from core import get_api_client
client = get_api_client()
projects = client.get("/projects", operation_name="test")
print(f"Got {len(projects)} projects")
```

### Running Specific Tools

```python
from tools import projects
all_projects = projects.get_all_projects()
print(all_projects)
```

## Performance Considerations

- **Metadata Caching**: Enabled by default, reduces file I/O
- **API Retries**: Configurable retry attempts (default: 3)
- **Connection Pooling**: Reuses HTTP connections
- **Lazy Loading**: Managers initialize on first use

To disable caching (for development):

```yaml
metadata:
  cache_enabled: false
```

## Security Considerations

1. **API Credentials**: Use environment variables, never commit to version control
2. **Sensitive Data**: Add `.env` to `.gitignore`
3. **Input Validation**: All inputs are validated before API calls
4. **Error Messages**: No sensitive data in error responses

## License

Same as parent project.

## Support

For issues, questions, or contributions, refer to the main project repository.

---

**Note**: This is a refactored version of the PMO MCP Server. The original version ([pmo_mcp_server.py](../pmo_mcp_server.py)) is still available for reference.
