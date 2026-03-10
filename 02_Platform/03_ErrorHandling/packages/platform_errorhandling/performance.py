import logging
import time
from contextlib import contextmanager

from fastapi import Request

log = logging.getLogger("atlas")


def install_request_timing(app) -> None:
    @app.middleware("http")
    async def request_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        rid = getattr(request.state, "request_id", "n/a")
        log.info(
            "RID=%s %s %s status=%s duration_ms=%d",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            int(duration_ms),
        )
        return response


@contextmanager
def timed_block(logger: logging.Logger, block_name: str, request_id: str = "n/a"):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug(
            "PERF block=%s duration_ms=%d request_id=%s",
            block_name,
            duration_ms,
            request_id,
        )
