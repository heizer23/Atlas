FROM python:3.11-slim

WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

# Copy service source and install dependencies
COPY 02_Platform/Notifications/pyproject.toml .
COPY 02_Platform/Notifications/backend/ ./backend/

RUN --mount=type=cache,target=/root/.cache/pip pip install .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
