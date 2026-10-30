import logging
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool, init_schema
from backend.migrate_fsrs_state import migrate_legacy_fsrs_state
from backend.migrate_recall_state import migrate_legacy_unguided_to_recall
from backend.routers import essays, examinations, exploration, flashcards, guided, images, nuggets, progress, recall, review_stats, sentence_feedback
from platform_errorhandling.api_response import api_error
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.performance import install_request_timing

setup_logging(app_name="essaycards", log_dir=Path(__file__).resolve().parents[1] / "logs")
log = logging.getLogger("essaycards")

_ID_QUERY_PARAMS = ("essay_id", "section_id", "nugget_id")
_ID_PARAMS = ("id", "essay_id", "section_id", "flashcard_id", "nugget_id")


class MalformedId(Exception):
    def __init__(self, value: str) -> None:
        self.value = value


def _require_uuid_path_ids(request: Request) -> None:
    """Malformed id in the URL -> 404 (same as an unknown id), never a DB cast 500."""
    for name in _ID_PARAMS:
        value = request.path_params.get(name)
        if value is None:
            continue
        try:
            uuid.UUID(value)
        except ValueError:
            raise MalformedId(value)
    # Id-valued query params (empty = "not given", as the routes treat it).
    for name in _ID_QUERY_PARAMS:
        value = request.query_params.get(name)
        if not value:
            continue
        try:
            uuid.UUID(value)
        except ValueError:
            raise MalformedId(value)


app = FastAPI(title="EssayCards", version="0.1.0", dependencies=[Depends(_require_uuid_path_ids)])


@app.exception_handler(MalformedId)
async def _malformed_id_handler(request: Request, exc: MalformedId):
    return api_error("NOT_FOUND", f"{exc.value} not found", status=404)

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
# Registered after flashcards.router — see backend/routers/exploration.py docstring.
app.include_router(exploration.router, prefix="/api/essaycards")
app.include_router(examinations.router, prefix="/api/essaycards")
app.include_router(guided.router, prefix="/api/essaycards")
app.include_router(images.router, prefix="/api/essaycards")
app.include_router(nuggets.router, prefix="/api/essaycards")
app.include_router(progress.router, prefix="/api/essaycards")
app.include_router(recall.router, prefix="/api/essaycards")
app.include_router(review_stats.router, prefix="/api/essaycards")
app.include_router(sentence_feedback.router, prefix="/api/essaycards")


@app.on_event("startup")
def on_startup() -> None:
    for attempt in range(1, 11):
        try:
            log.info("Initialising connection pool (attempt %d)...", attempt)
            init_pool()
            log.info("Running schema init...")
            init_schema()
            log.info("Running legacy FSRS-state backfill...")
            from backend.database import get_db
            with get_db() as conn:
                migrate_legacy_fsrs_state(conn)
                log.info("recall seed: %s", migrate_legacy_unguided_to_recall(conn))
            log.info("Ready.")
            return
        except Exception as exc:
            log.warning("DB not ready (attempt %d/10): %s", attempt, exc)
            if attempt < 10:
                time.sleep(3)
    log.error("Could not connect to database after 10 attempts — requests will fail.")
