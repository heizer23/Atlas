import uuid
from fastapi.responses import JSONResponse


def api_error(code: str, message: str, detail: object = None, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code":       code,
                "message":    message,
                "detail":     detail,
                "request_id": uuid.uuid4().hex[:8],
            }
        },
    )
