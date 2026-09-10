import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.claude_process import ensure_workspace_trusted
from backend.database import init_pool, init_schema
from backend.routers import session
from backend.ws import ws_endpoint
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="claudeconsole", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("claudeconsole")

app = FastAPI(title="ClaudeConsole", version="0.1.0")

# Allow Vite dev server on any localhost port during development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(session.router, prefix="/api")
app.add_api_websocket_route("/api/claudeconsole/ws", ws_endpoint)


@app.on_event("startup")
def on_startup() -> None:
    ensure_workspace_trusted()
    for attempt in range(1, 11):
        try:
            log.info("Initialising connection pool (attempt %d)...", attempt)
            init_pool()
            log.info("Running schema init...")
            init_schema()
            log.info("Ready.")
            return
        except Exception as exc:
            log.warning("DB not ready (attempt %d/10): %s", attempt, exc)
            if attempt < 10:
                time.sleep(3)
    log.error("Could not connect to database after 10 attempts — requests will fail.")
