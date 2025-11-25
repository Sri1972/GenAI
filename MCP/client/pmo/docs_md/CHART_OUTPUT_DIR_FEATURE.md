# Chart Output Directory Control Feature

## Summary

Added client-side control over chart output directory location. Clients can now specify where chart HTML files are saved, instead of charts being saved only to the server's default directory.

## User Request

"I want the client to control where the file is created even though the server decides? That way each client can pick a place. D:\SourceCode\GenAI\MCP\client\pmo\html-charts I want it there"

## Changes Made

### 1. MCP Tool Interface Layer (d3_chart_mcp.py)

**File**: `D:\SourceCode\GenAI\MCP\server\charts\mcp-d3-stdio-custom\d3_chart_mcp.py`

#### Added output_dir parameter to render_chart_from_dataset tool (lines 456-483)

```python
@mcp.tool()
def render_chart_from_dataset(
    title: str = "Chart",
    data: Union[Dict, List] = None,
    chart_type: str = "line",
    framework: str = "d3",
    output_dir: Optional[str] = None  # ← NEW PARAMETER
) -> str:
    """
    Args:
        ...
        output_dir: Optional output directory path (defaults to server's html-charts dir)
    """
    arguments = {
        'title': title,
        'data': data,
        'chart_type': chart_type,
        'framework': framework
    }
    if output_dir:
        arguments['output_dir'] = output_dir  # ← Pass to API server
```

**Impact**: Clients can now pass `output_dir` parameter when calling the MCP tool.

---

### 2. API Server Layer (d3_chart_api_server.py)

**File**: `D:\SourceCode\GenAI\MCP\server\charts\mcp-d3-stdio-custom\d3_chart_api_server.py`

#### 2.1 Renamed OUTDIR → DEFAULT_OUTDIR (line 82)

```python
# OLD
OUTDIR = ROOT / 'html-charts'

# NEW
DEFAULT_OUTDIR = ROOT / 'html-charts'
```

**Reason**: More descriptive name indicating this is the fallback when no custom directory is provided.

#### 2.2 Updated save_html function signature (lines 93-115)

```python
def save_html(html_text: str, prefix: str = 'chart', output_dir: str = None) -> str:
    """
    Args:
        output_dir (str): Optional custom output directory path
    """
    # Use provided output_dir or default
    outdir = Path(output_dir) if output_dir else DEFAULT_OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    
    slug = hashlib.sha1(html_text.encode('utf-8')).hexdigest()[:8]
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"{prefix}_{ts}_{slug}.html"
    path = outdir / filename  # ← Uses custom or default directory
```

**Impact**: All chart saves can now use custom output directory.

#### 2.3 Updated helper functions to accept and pass output_dir

**render_using_script** (line 871):
```python
def render_using_script(script_fn, args, title=None, prefix='chart', output_dir=None):
    # ... existing logic ...
    path = save_html(html_text, prefix=prefix, output_dir=output_dir)
```

**handle_template** (line 1085):
```python
def handle_template(args, chart_type='line', stacked=False, output_dir=None):
    # ... existing logic ...
    path = save_html(html_text, prefix='packed', output_dir=output_dir)
    # ... (6 more save_html calls updated)
```

#### 2.4 Updated render_from_dataset_tool (main entry point)

**Lines 1208-1243**: Extract output_dir from args at function start
```python
def render_from_dataset_tool(args: dict):
    """Args: data, title, chart_type, framework, and output_dir"""
    try:
        # Extract output directory preference
        output_dir = args.get('output_dir') if isinstance(args, dict) else None
        # ... rest of function
```

**Updated all save_html calls** (3 direct calls):
- Line 1265: HTML-in-args case
- Line 1291: Chart.js rendering
- Line 1351: Final fallback

**Updated all helper function calls** to pass output_dir:
- Line 1286: handle_template for packed charts
- Line 1297-1305: render_using_script for grouped_bar, horizontal_bar, scatter
- Line 1347: handle_template for proportional charts

#### 2.5 Updated TOOLS registry lambdas (lines 908-935)

All lambda functions now extract and pass output_dir from args:

```python
TOOLS = {
    # OLD
    'line': lambda args: handle_template(args, chart_type='line'),
    
    # NEW
    'line': lambda args: handle_template(args, chart_type='line', 
                                        output_dir=args.get('output_dir') if isinstance(args, dict) else None),
}
```

**Total**: Updated 23 tool registry entries (10 handle_template, 13 render_using_script).

**Summary of d3_chart_api_server.py changes**:
- 1 constant renamed (OUTDIR → DEFAULT_OUTDIR)
- 3 function signatures updated (save_html, render_using_script, handle_template)
- 11 save_html calls updated (all now pass output_dir)
- 23 TOOLS registry lambdas updated
- 5 helper function calls updated in render_from_dataset_tool

---

### 3. Client Layer (pmo_mcp_client.py)

**File**: `D:\SourceCode\GenAI\MCP\client\pmo\pmo_mcp_client.py`

#### Added automatic output_dir injection for chart tools (lines 1992-2000)

```python
# If parsed JSON indicates a tool invocation, execute it
if parsed and isinstance(parsed, dict) and 'tool' in parsed:
    tool_name = parsed['tool']
    tool_args = parsed.get('arguments', {}) or {}
            
    # Determine which server to route to
    is_chart_tool = tool_name.startswith('render_chart') or tool_name.startswith('create_')

    # Inject client-side output directory for chart tools
    if is_chart_tool and isinstance(tool_args, dict):
        # Set the output directory to client's html-charts folder
        client_chart_dir = Path(__file__).resolve().parent / "html-charts"
        tool_args['output_dir'] = str(client_chart_dir)
        print(f"[CHART OUTPUT] Charts will be saved to: {client_chart_dir}")
```

**Impact**: 
- All chart tool calls automatically include the client's preferred output directory
- No manual intervention needed - happens transparently
- Target directory: `D:\SourceCode\GenAI\MCP\client\pmo\html-charts`

---

## Architecture Overview

### 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 0: Client (pmo_mcp_client.py)                         │
│ - Detects chart tool calls                                   │
│ - Injects output_dir = "D:\...\client\pmo\html-charts"      │
│ - Passes arguments to MCP server                             │
└────────────────────┬─────────────────────────────────────────┘
                     │ JSON-RPC over STDIO
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: MCP Interface (d3_chart_mcp.py)                    │
│ - FastMCP tool decorator                                     │
│ - render_chart_from_dataset(output_dir=...)                 │
│ - Passes output_dir to API server                            │
└────────────────────┬─────────────────────────────────────────┘
                     │ Function call
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: API Server (d3_chart_api_server.py)                │
│ - render_from_dataset_tool extracts output_dir              │
│ - handle_template / render_using_script pass output_dir     │
│ - save_html uses output_dir or DEFAULT_OUTDIR               │
│ - Creates directory if needed                                │
│ - Saves HTML to specified location                           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Example

1. **User Query**: "Show me a chart of resource hours"
2. **Claude Response**: `{"tool": "render_chart_from_dataset", "arguments": {"title": "Hours", "data": {...}, "chart_type": "bar"}}`
3. **Client Injection**: Adds `"output_dir": "D:\\SourceCode\\GenAI\\MCP\\client\\pmo\\html-charts"`
4. **MCP Tool**: Receives output_dir, passes to API server
5. **API Server**: Extracts output_dir, passes through helper functions
6. **save_html**: Uses output_dir instead of DEFAULT_OUTDIR
7. **Result**: Chart saved to `D:\SourceCode\GenAI\MCP\client\pmo\html-charts\bar_20250131_123456_abc12345.html`

---

## Backwards Compatibility

✅ **Fully backwards compatible**

- If client doesn't pass `output_dir`, charts save to server's default directory
- Existing clients work without modification
- New clients can opt-in to custom directory by passing `output_dir` parameter

---

## Testing Checklist

- [ ] Start both MCP servers (PMO + Chart)
- [ ] Run client with chart generation query
- [ ] Verify chart HTML saved to `D:\SourceCode\GenAI\MCP\client\pmo\html-charts\`
- [ ] Verify chart opens correctly in browser
- [ ] Verify client console shows: `[CHART OUTPUT] Charts will be saved to: D:\SourceCode\GenAI\MCP\client\pmo\html-charts`
- [ ] Test various chart types (line, bar, pie, scatter, etc.)
- [ ] Test with and without explicit chart_type parameter
- [ ] Test with framework='d3' and framework='chartjs'

---

## Files Modified

1. `d3_chart_mcp.py` - 1 function signature updated
2. `d3_chart_api_server.py` - 1 constant, 3 functions, 11 save_html calls, 23 lambdas, 5 helper calls updated
3. `pmo_mcp_client.py` - 1 code block added for output_dir injection

**Total Lines Changed**: ~45 lines across 3 files

---

## Benefits

1. **Client Control**: Each client can choose where to save charts
2. **Organization**: Charts saved near client code, not buried in server directory
3. **Multi-Client**: Multiple clients can save to different directories
4. **Transparency**: Client logs show exactly where charts are saved
5. **Flexibility**: Can be configured per-client or per-environment

---

## Future Enhancements

- [ ] Add client configuration file for default output_dir
- [ ] Support environment variable override (e.g., `CHART_OUTPUT_DIR`)
- [ ] Add option to organize charts by date/type subdirectories
- [ ] Add cleanup mechanism for old chart files
- [ ] Support cloud storage backends (S3, Azure Blob, etc.)

---

## Completion Date

January 31, 2025

## Status

✅ **COMPLETE** - All changes implemented, no syntax errors, ready for testing.
