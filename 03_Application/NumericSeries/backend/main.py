"""
NumericSeries — FastAPI application entry point.

Source of truth: Sprint01/20_design/architecture.json + scaffolding.json
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool, init_schema
from backend.routers import series, batch, catalog
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="numericseries", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("numericseries")

app = FastAPI(title="NumericSeries", version="0.1.0")

# Allow Vite dev server on any localhost port during development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(catalog.router, prefix="/api")
app.include_router(series.router, prefix="/api")
app.include_router(batch.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    try:
        log.info("Initialising connection pool...")
        init_pool()
        log.info("Running schema init...")
        init_schema()
        log.info("Ready.")
    except Exception as exc:
        log.error("Startup failed (database may not be reachable): %s", exc)
        log.error("Requests will fail until the database is available.")
