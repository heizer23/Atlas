FROM python:3.11-slim

WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

# Copy app source and install dependencies (including dev extras)
COPY 03_Application/FoodTracker/pyproject.toml .
COPY 03_Application/FoodTracker/backend/ ./backend/
COPY 03_Application/FoodTracker/schema.sql ./schema.sql
COPY 03_Application/FoodTracker/tests/ ./tests/

RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
