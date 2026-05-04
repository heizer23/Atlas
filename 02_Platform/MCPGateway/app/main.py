import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

# ---------------------------------------------------------------------------
# Auth: FastMCP proxies OAuth to Google.
# ChatGPT authenticates once; token validated on every request.
# ---------------------------------------------------------------------------
auth = GoogleProvider(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    base_url=os.environ["MCP_BASE_URL"],  # https://mcp.linspad.net
)

mcp = FastMCP("Atlas MCP Gateway", auth=auth)

# ---------------------------------------------------------------------------
# Register domain tools from applications.
# Each application exposes plain functions; the gateway owns the MCP protocol.
# Add new application tool modules here as Atlas grows.
# ---------------------------------------------------------------------------
from foodtracker.tools import log_meal, get_nutrition_summary  # noqa: E402

mcp.tool(log_meal)
mcp.tool(get_nutrition_summary)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8002)
