PMO MCP Server Documentation
============================

This folder contains HTML documentation for the PMO MCP server (generated from `pmo_mcp_server.py` and the metadata files).

Files:
- `index.html` — single-page overview of the PMO MCP server, tools, metadata, examples, and troubleshooting.

How to view locally
-------------------
Open `server/pmo/docs/index.html` in your browser (e.g. double-click the file or use your editor's preview).

Key locations
-------------
- Server source: `server/pmo/pmo_comprehensive.py`
- Metadata: `server/pmo/metadata/` (api_master_index.metadata.json, projects_api.metadata.json, resources_api.metadata.json, allocations_api.metadata.json, ...)

Notes
-----
- The MCP server registers tools with `@mcp.tool()` and several document resources with `@mcp.resource()`.
- If you update metadata files, restart the MCP server to pick up changes.
- If you want richer generated docs (per-endpoint pages or markdown export), I can add a script to generate them from the metadata automatically.