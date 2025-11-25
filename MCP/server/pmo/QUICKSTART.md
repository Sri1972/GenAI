# PMO MCP Server - Quick Start Guide

Get up and running with the refactored PMO MCP Server in 5 minutes!

## Prerequisites

- ✅ Python 3.11 or higher installed
- ✅ PMO API running (default: http://localhost:5000)
- ✅ Git or ability to download files

## 1. Setup (2 minutes)

### Windows
```bash
cd D:\GenAI\MCP\server\pmo\pmo_refactored
setup.bat
```

### Linux/Mac
```bash
cd D:/GenAI/MCP/server/pmo/pmo_refactored
chmod +x setup.sh
./setup.sh
```

This will:
- ✓ Copy metadata files
- ✓ Create `.env` file
- ✓ Install Python dependencies

## 2. Configure (1 minute)

Edit `.env` file:
```env
PMO_API_BASE_URL=http://localhost:5000
PMO_LOG_LEVEL=INFO
```

**That's it!** Default configuration works for most cases.

## 3. Test (1 minute)

```bash
python server.py
```

You should see:
```
INFO - Initializing PMO MCP Server v1.0.0
INFO - API Base URL: http://localhost:5000
INFO - Starting PMO MCP Server...
```

Press `Ctrl+C` to stop.

## 4. Use with Claude Desktop (1 minute)

Edit your Claude Desktop config file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Add this:
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

Restart Claude Desktop.

## 5. Verify (30 seconds)

In Claude Desktop, ask:
> "What projects do we have?"

Claude should use the `get_all_projects()` tool to fetch and display your projects!

## Common Issues

### "Module not found: yaml"
```bash
pip install pyyaml
```

### "Failed to connect to API"
1. Check if API is running: `curl http://localhost:5000/projects`
2. Verify `PMO_API_BASE_URL` in `.env`

### "Metadata file not found"
Run setup script again:
```bash
setup.bat  # Windows
./setup.sh # Linux/Mac
```

## Next Steps

1. **Customize Prompts**: Edit `config/prompts.yaml`
2. **Adjust Config**: Edit `config/config.yaml`
3. **Read Docs**: See [README.md](README.md) for full documentation
4. **Migration**: See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if upgrading

## Quick Configuration Examples

### Change API Timeout
Edit `config/config.yaml`:
```yaml
api:
  timeout: 60  # seconds
```

### Enable Debug Logging
Edit `.env`:
```env
PMO_LOG_LEVEL=DEBUG
```

### Add Custom Prompt
Edit `config/prompts.yaml`:
```yaml
prompts:
  my_analysis:
    title: "My Custom Analysis"
    content: |
      Perform analysis including:
      - Step 1
      - Step 2
```

## Testing Individual Components

```python
# Test configuration
from config import get_settings
print(get_settings().api.base_url)

# Test API client
from core import get_api_client
client = get_api_client()
projects = client.get("/projects", operation_name="test")
print(f"Got {len(projects)} projects")

# Test tools
from tools import projects
all_projects = projects.get_all_projects()
print(all_projects[0])
```

## Support

- 📖 Full docs: [README.md](README.md)
- 🔄 Migration: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- ✨ What's new: [IMPROVEMENTS.md](IMPROVEMENTS.md)

---

**You're ready to go!** The refactored PMO MCP Server is now running with improved reliability, configurability, and maintainability.
