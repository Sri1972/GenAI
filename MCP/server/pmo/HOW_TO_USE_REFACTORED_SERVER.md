# How to Use Your Client with the Refactored PMO MCP Server

## TL;DR - Quick Steps

**Your client at `D:\GenAI\MCP\client\pmo\pmo_mcp_client.py` works without changes!**

Just update the server path:

```python
# Change from:
pmo_server = Path(...) / 'pmo_mcp_server.py'

# To:
pmo_server = Path(...) / 'pmo_refactored' / 'server.py'
```

That's it! Everything else works the same.

---

## Detailed Steps

### 1. Setup the Refactored Server (One-time)

```bash
cd D:\GenAI\MCP\server\pmo\pmo_refactored
setup.bat
```

This copies metadata and installs dependencies.

### 2. Update Your Client

**File:** `D:\GenAI\MCP\client\pmo\pmo_mcp_client.py`

Find where you create `StdioServerParameters` and update:

```python
# OLD
server_path = Path(__file__).parents[1] / 'server' / 'pmo' / 'pmo_mcp_server.py'

# NEW
server_path = Path(__file__).parents[1] / 'server' / 'pmo' / 'pmo_refactored' / 'server.py'
```

### 3. Test It

```bash
cd D:\GenAI\MCP\client\pmo
python example_with_refactored_server.py
```

This will:
- ✅ Test the connection
- ✅ Call several tools
- ✅ Show new validation features
- ✅ Confirm everything works

---

## What You Get (Without Changing Your Code!)

### ✨ Better Error Messages

**Before:**
```json
{"error": "API request failed: 500"}
```

**After:**
```json
{
  "error": "API request failed: Internal server error",
  "details": {
    "status_code": 500,
    "response": "Detailed error info..."
  }
}
```

### 🛡️ Input Validation

The server now validates inputs before calling the API:

```python
# Your code stays the same
result = await session.call_tool("get_resource_capacity_allocation", {
    "resource_id": -1,  # Invalid!
    "start_date": "2024-13-99",  # Invalid date!
    "end_date": "2024-01-01"
})

# Server returns helpful error immediately (no API call made)
```

### 🔄 Automatic Retry

Connection failures? The server retries automatically (3 times by default).

### ⚙️ Easy Configuration

Need to change API URL? Edit `server/pmo/pmo_refactored/.env`:

```env
PMO_API_BASE_URL=http://your-server:5000
```

Your client doesn't need to change!

---

## Configuration (Optional)

You can pass config from your client to the server:

```python
server_params = StdioServerParameters(
    command="python",
    args=[str(server_path)],
    env={
        "PMO_API_BASE_URL": "http://localhost:5000",
        "PMO_LOG_LEVEL": "INFO",  # or DEBUG for detailed logs
        "PMO_API_TIMEOUT": "30",
        "PMO_API_RETRY_ATTEMPTS": "3"
    }
)
```

---

## Example Files Created for You

### 1. **[USING_REFACTORED_SERVER.md](client/pmo/USING_REFACTORED_SERVER.md)**
   Complete guide with examples

### 2. **[example_with_refactored_server.py](client/pmo/example_with_refactored_server.py)**
   Working example you can run right now

---

## Quick Test

**Terminal 1 - Run the refactored server:**
```bash
cd D:\GenAI\MCP\server\pmo\pmo_refactored
python server.py
```

**Terminal 2 - Run your client:**
```bash
cd D:\GenAI\MCP\client\pmo
python pmo_mcp_client.py
```

or

```bash
python example_with_refactored_server.py
```

---

## Troubleshooting

### "Module not found: yaml"
```bash
cd D:\GenAI\MCP\server\pmo\pmo_refactored
pip install -r requirements.txt
```

### "Configuration file not found"
```bash
cd D:\GenAI\MCP\server\pmo\pmo_refactored
setup.bat
```

### "Failed to connect to API"
1. Check PMO API is running: `curl http://localhost:5000/projects`
2. Check `.env` file: `notepad D:\GenAI\MCP\server\pmo\pmo_refactored\.env`
3. Verify `PMO_API_BASE_URL=http://localhost:5000`

---

## Switching Between Servers

Want to test both? Easy:

```python
USE_REFACTORED = True  # or False

if USE_REFACTORED:
    server_path = Path(...) / 'pmo_refactored' / 'server.py'
else:
    server_path = Path(...) / 'pmo_mcp_server.py'
```

---

## Files You Need to Know About

### Your Client
```
D:\GenAI\MCP\client\pmo\
├── pmo_mcp_client.py              # Your main client (update server path)
├── USING_REFACTORED_SERVER.md     # ← Detailed guide
└── example_with_refactored_server.py  # ← Test example
```

### Refactored Server
```
D:\GenAI\MCP\server\pmo\pmo_refactored\
├── server.py                      # Main entry point
├── .env                           # Configuration (created by setup.bat)
├── config/
│   ├── config.yaml                # Server settings
│   └── prompts.yaml               # Customizable prompts
├── setup.bat                      # Setup script (run once)
├── README.md                      # Full documentation
├── QUICKSTART.md                  # Quick start guide
└── MIGRATION_GUIDE.md             # Migration details
```

---

## Summary

**What changes in your client:**
- Update server path (1 line of code)

**What stays the same:**
- All tool names
- All tool parameters
- All return formats
- All your existing code

**What you get for free:**
- ✅ Better error messages
- ✅ Input validation
- ✅ Automatic retry
- ✅ Easy configuration
- ✅ Better logging
- ✅ Performance improvements

---

## Next Steps

1. ✅ Run setup: `cd D:\GenAI\MCP\server\pmo\pmo_refactored && setup.bat`
2. ✅ Update client: Change server path in `pmo_mcp_client.py`
3. ✅ Test: `python example_with_refactored_server.py`
4. ✅ Done! Use your client as before

---

## Documentation

- **Client Guide:** [client/pmo/USING_REFACTORED_SERVER.md](client/pmo/USING_REFACTORED_SERVER.md)
- **Server Docs:** [server/pmo/pmo_refactored/README.md](server/pmo/pmo_refactored/README.md)
- **Quick Start:** [server/pmo/pmo_refactored/QUICKSTART.md](server/pmo/pmo_refactored/QUICKSTART.md)
- **What's New:** [server/pmo/pmo_refactored/IMPROVEMENTS.md](server/pmo/pmo_refactored/IMPROVEMENTS.md)

---

**Questions? Issues?**
- Check the guides above
- Run the example: `python example_with_refactored_server.py`
- Enable debug logging: Set `PMO_LOG_LEVEL=DEBUG` in `.env`
