# FoodTracker

## MCP Tools

`tools.py` at the application root provides FoodTracker MCP tool definitions (`log_meal`, `get_nutrition_summary`). These are plain Python functions with no FastMCP dependency, registered into `02_Platform/MCPGateway` at startup. This file is not imported by the backend routers.

## Architecture Exceptions

Non-Dataset endpoint shapes are formally registered in `ARCHITECTURE_EXCEPTIONS.md`.

## Sprint Conventions

FoodTracker skips the `10_specs/` stage. See `sprint_conventions.md`.
