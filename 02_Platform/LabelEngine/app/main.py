"""
LabelEngine — FastAPI application entrypoint.

Mounts all routers under /api prefix.
Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_pool, init_schema
from app.routers import groups, labels, objects

try:
    from platform_errorhandling.logging import setup_logging
    from platform_errorhandling.logFastapi import install_exception_handlers
    from platform_errorhandling.performance import install_request_timing
    _has_error_handling = True
except ImportError:
    _has_error_handling = False

if _has_error_handling:
    setup_logging(
        app_name="label_engine",
        log_dir=Path(__file__).resolve().parents[1] / "logs",
    )

log = logging.getLogger("label_engine")

app = FastAPI(title="LabelEngine", version="0.1.0")

# Allow Atlas Shell (Vite dev server on any localhost port during development)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

if _has_error_handling:
    install_exception_handlers(app)
    install_request_timing(app)

app.include_router(labels.router,  prefix="/api")
app.include_router(objects.router, prefix="/api")
app.include_router(groups.router,  prefix="/api")


@app.get("/health")
def health() -> JSONResponse:
    """Liveness check — returns 200 when the service is running."""
    return JSONResponse({"status": "ok"})


@app.on_event("startup")
def on_startup() -> None:
    try:
        log.info("Initialising connection pool...")
        init_pool()
        log.info("Running schema init...")
        init_schema()
        log.info("LabelEngine ready.")
    except Exception as exc:
        log.error("Startup failed (database may not be reachable): %s", exc)
        log.error("Requests will fail until the database is available.")
