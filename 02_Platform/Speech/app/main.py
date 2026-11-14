"""Speech — FastAPI entrypoint. Same-origin via shell nginx; no CORS."""

import asyncio
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import SpeechError
from app.recordings import RecordingStore
import app.recordings as recordings
from app.routers import speech

try:
    from platform_errorhandling.logging import setup_logging
    from platform_errorhandling.logFastapi import install_exception_handlers
    from platform_errorhandling.performance import install_request_timing
    _has_error_handling = True
except ImportError:
    _has_error_handling = False

if _has_error_handling:
    setup_logging(app_name="speech", log_dir=Path(__file__).resolve().parents[1] / "logs")

# Never let HTTP client internals log request details.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

log = logging.getLogger("speech")

app = FastAPI(title="Speech", version="0.1.0")

if _has_error_handling:
    install_exception_handlers(app)
    install_request_timing(app)


@app.exception_handler(SpeechError)
async def speech_error_handler(request: Request, exc: SpeechError) -> JSONResponse:
    return exc.to_response()


app.include_router(speech.router)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def _reaper() -> None:
    while True:
        await asyncio.sleep(60)
        if recordings._store is not None:
            n = recordings._store.reap_idle(time.time())
            if n:
                log.info("reaped %d idle recordings", n)


@app.on_event("startup")
async def on_startup() -> None:
    recordings._store = RecordingStore(get_settings())  # startup sweep
    app.state.reaper = asyncio.create_task(_reaper())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    app.state.reaper.cancel()
