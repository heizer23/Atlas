FROM python:3.11-slim

WORKDIR /app

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

# Copy app source and install dependencies
COPY 03_Application/WorkoutTracker/pyproject.toml .
COPY 03_Application/WorkoutTracker/backend/ ./backend/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
