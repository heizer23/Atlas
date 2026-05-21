import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool
from backend.routers import workout
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="workouttracker", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("workouttracker")

app = FastAPI(title="WorkoutTracker", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(workout.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    for attempt in range(1, 11):
        try:
            log.info("Initialising connection pool (attempt %d)...", attempt)
            init_pool()
            log.info("Ready.")
            return
        except Exception as exc:
            log.warning("DB not ready (attempt %d/10): %s", attempt, exc)
            if attempt < 10:
                time.sleep(3)
    log.error("Could not connect to database after 10 attempts — requests will fail.")
