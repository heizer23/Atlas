import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool, init_schema
from backend.routers import essays, examinations, flashcards, images
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="essaycards", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("essaycards")

app = FastAPI(title="EssayCards", version="0.1.0")

# Allow Vite dev server on any localhost port during development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(essays.router, prefix="/api/essaycards")
app.include_router(flashcards.router, prefix="/api/essaycards")
app.include_router(examinations.router, prefix="/api/essaycards")
app.include_router(images.router, prefix="/api/essaycards")


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
