FROM python:3.12-slim
WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

COPY 03_Application/NumericSeries/pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

COPY 03_Application/NumericSeries/backend/ ./backend/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
