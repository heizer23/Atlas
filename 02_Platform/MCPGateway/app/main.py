import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

# ---------------------------------------------------------------------------
# Auth: FastMCP proxies the OAuth dance to Google.
# ChatGPT redirects the user to Google sign-in, gets a token back, and sends
# it on every MCP request. FastMCP validates it against Google's tokeninfo API.
# No auth code beyond this configuration is needed.
# ---------------------------------------------------------------------------
auth = GoogleProvider(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    base_url=os.environ["MCP_BASE_URL"],  # https://mcp.linspad.net
)

mcp = FastMCP("Atlas Food MCP", auth=auth)

# ---------------------------------------------------------------------------
# Data: hardcoded fruit→color mapping (MVP).
# Replace with a Postgres lookup when building the real FoodTracker.
# ---------------------------------------------------------------------------
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
    Returns the color string (e.g. 'red'), or an error message if the
    fruit is not in the database.
    """
    key = fruit.strip().lower()
    color = FRUIT_COLORS.get(key)
    if color is None:
        known = ", ".join(sorted(FRUIT_COLORS.keys()))
        return f"Unknown fruit '{fruit}'. Known fruits: {known}."
    return color


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8002)
