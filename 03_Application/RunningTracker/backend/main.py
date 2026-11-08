import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool, init_schema
from backend.routers import native, pairing_web, routes, runs
from backend.security import AppError
from platform_errorhandling import api_error
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="runningtracker", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("runningtracker")

app = FastAPI(title="RunningTracker", version="0.1.0")

# Allow Vite dev server on any localhost port during development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return api_error(exc.code, exc.message, status=exc.status)


# Request logging (install_request_timing) records method, path and status only: no bodies, headers or samples.
app.include_router(runs.router, prefix="/api/runningtracker")
app.include_router(routes.router, prefix="/api/runningtracker")
app.include_router(pairing_web.router, prefix="/api/runningtracker")
app.include_router(native.router, prefix="/api/runningtracker")


@app.on_event("startup")
def on_startup() -> None:
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
    log.error("Could not connect to database after 10 attempts - requests will fail.")
