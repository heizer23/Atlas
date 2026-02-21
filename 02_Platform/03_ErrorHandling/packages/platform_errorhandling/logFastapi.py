import logging
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse

log = logging.getLogger("atlas")

def install_exception_handlers(app):
    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "n/a")

        # Full traceback goes to logs
        log.exception("RID=%s %s %s", rid, request.method, request.url.path)

        # API routes get JSON; page routes get simple HTML
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "request_id": rid,
                    "message": "Unexpected error. Search logs for this request_id.",
                },
            )

        return HTMLResponse(
            status_code=500,
            content=(
                "<h2>Internal Server Error</h2>"
                f"<p>Request ID: <code>{rid}</code></p>"
                "<p>Check the server log for details.</p>"
            ),
        )
