FROM python:3.12-slim
WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

COPY 02_Platform/PreferenceStore/pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

COPY 02_Platform/PreferenceStore/app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
