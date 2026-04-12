FROM python:3.12-slim
WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

COPY 03_Application/NumericSeries/pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"

COPY 03_Application/NumericSeries/backend/ ./backend/
COPY 03_Application/NumericSeries/tests/ ./tests/
COPY 03_Application/NumericSeries/Sprint01/20_Data/schema.sql ./Sprint01/20_Data/schema.sql
COPY 03_Application/NumericSeries/00_architecture/measurement_definitions.json ./00_architecture/measurement_definitions.json

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
