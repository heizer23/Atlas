FROM python:3.11-slim

WORKDIR /app

# Platform: MCPGateway (auth + transport)
COPY 02_Platform/MCPGateway/app/ ./app/

# Application: FoodTracker tools (domain layer)
COPY 03_Application/FoodTracker/ ./foodtracker/

RUN pip install --no-cache-dir fastmcp "psycopg[binary]"

EXPOSE 8002

CMD ["python", "-m", "app.main"]
