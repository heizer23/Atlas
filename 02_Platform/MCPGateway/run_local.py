"""
Local dev runner — starts the MCP server WITHOUT auth on port 8002.
Use this to test tool logic before deploying to the Pi.

Run:  python run_local.py
Test: python -c "import httpx; print(httpx.post('http://localhost:8002/mcp', ...))"
"""
import sys
import os

# Point Python at the app package
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP

mcp = FastMCP("Atlas Food MCP (local/no-auth)")

FRUIT_COLORS: dict[str, str] = {
    "apple": "red",
    "banana": "yellow",
    "mango": "orange",
}

@mcp.tool
def get_fruit_color(fruit: str) -> str:
    """
    Return the typical color for a given fruit.
    Supported fruits: apple, banana, mango.
    """
    key = fruit.strip().lower()
    color = FRUIT_COLORS.get(key)
    if color is None:
        known = ", ".join(sorted(FRUIT_COLORS.keys()))
        return f"Unknown fruit '{fruit}'. Known fruits: {known}."
    return color

if __name__ == "__main__":
    print("Starting MCP server locally on http://localhost:8002 (no auth)")
    print("MCP endpoint: http://localhost:8002/mcp")
    mcp.run(transport="http", host="127.0.0.1", port=8002)
