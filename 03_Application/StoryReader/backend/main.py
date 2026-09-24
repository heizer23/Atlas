import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool, init_schema
from backend.routers import stories
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="storyreader", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("storyreader")

app = FastAPI(title="StoryReader", version="0.1.0")

# Allow Vite dev server on any localhost port during development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(stories.router, prefix="/api")


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
    log.error("Could not connect to database after 10 attempts — requests will fail.")
