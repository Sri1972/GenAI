"""Maps product codes to MCP server config keys from .mcp.json."""

PRODUCT_MCP_MAP: dict[str, str] = {
    "CFI": "cfi_new_reg",
    "CS4": "cornerstone",
}


def resolve_mcp_server(product_code: str) -> str:
    """Return the MCP server key for a given product code (case-insensitive)."""
    key = PRODUCT_MCP_MAP.get(product_code.upper())
    if key is None:
        available = ", ".join(PRODUCT_MCP_MAP.keys())
        raise ValueError(
            f"Unknown product code '{product_code}'. Available: {available}"
        )
    return key
