FROM python:3.12-slim
WORKDIR /app

# Node 20 LTS + Claude Code CLI. No other Atlas container combines Node and
# Python — this is the first. Verify the Node version against Claude Code's
# actual engine requirement if the CLI fails to install/run; 20 LTS is a
# reasonable current default, not empirically verified for this app.
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

# Copy platform packages (path relative to repo root build context)
COPY 02_Platform/packages /platform_packages
ENV PYTHONPATH="/platform_packages"

COPY 03_Application/ClaudeConsole/pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"

COPY 03_Application/ClaudeConsole/backend/ ./backend/
COPY 03_Application/ClaudeConsole/schema.sql ./schema.sql
COPY 03_Application/ClaudeConsole/tests/ ./tests/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
