FROM python:3.11-slim

WORKDIR /app

# Platform: MCPGateway (auth + transport)
COPY 02_Platform/MCPGateway/app/ ./app/

# Application: FoodTracker tools (domain layer)
COPY 03_Application/FoodTracker/ ./foodtracker/

# Application: TaskTracker tools (domain layer)
COPY 03_Application/TaskTracker/ ./tasktracker/

RUN --mount=type=cache,target=/root/.cache/pip pip install fastmcp "psycopg[binary]" httpx

EXPOSE 8002

CMD ["python", "-m", "app.main"]
