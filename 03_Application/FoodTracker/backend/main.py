import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool
from backend.routers import food, report, entries, standards
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="foodtracker", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("foodtracker")

app = FastAPI(title="FoodTracker", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(food.router,    prefix="/api")
app.include_router(report.router,  prefix="/api")
app.include_router(entries.router,    prefix="/api")
app.include_router(standards.router,  prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    try:
        log.info("Initialising connection pool...")
        init_pool()
        log.info("Ready.")
    except Exception as exc:
        log.error("Startup failed (database may not be reachable): %s", exc)
        log.error("Requests will fail until the database is available.")
