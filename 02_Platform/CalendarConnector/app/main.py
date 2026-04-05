"""
CalendarConnector FastAPI application entry point.

Configures CORS, installs platform error handlers and request timing,
mounts the calendar router, initialises the DB pool and schema on startup.

Port: CALENDAR_CONNECTOR_PORT (default 8021), container listens on :8000.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

from app.database import init_pool, init_schema
from app.routers import calendar
from app.routers.calendar import _validate_target_calendar_id

setup_logging(
    app_name="calendar_connector",
    log_dir=Path(__file__).resolve().parents[1] / "logs",
)
log = logging.getLogger("calendar_connector")

app = FastAPI(title="CalendarConnector", version="0.1.0")

# Allow Vite dev server on any localhost port during development (matches Atlas pattern)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)

app.include_router(calendar.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    try:
        log.info("Initialising connection pool...")
        init_pool()
        log.info("Running schema init...")
        init_schema()
        log.info("Validating CALENDAR_TARGET_CALENDAR_ID...")
        _validate_target_calendar_id()   # raises RuntimeError if env var absent
        log.info("CalendarConnector ready.")
    except Exception as exc:
        log.error("Startup failed: %s", exc)
        log.error("Requests will fail until configuration is corrected.")
        raise
