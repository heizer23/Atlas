FROM python:3.12-slim
WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

COPY 03_Application/TaskTracker/pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"

COPY 03_Application/TaskTracker/backend/ ./backend/
COPY 03_Application/TaskTracker/schema.sql ./schema.sql

# Copy PersonalDevelopment tests (run in this container against the tasktracker schema)
COPY 03_Application/PersonalDevelopment/tests/ ./tests/

# Copy TaskTracker-specific sprint tests into the same tests/ directory.
# They share the conftest from PersonalDevelopment and create their own data directly.
COPY 03_Application/TaskTracker/tests/test_scheduled_status.py ./tests/test_scheduled_status.py

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
