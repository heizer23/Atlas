"""Speech error codes and the single exception type."""

from fastapi.responses import JSONResponse
from platform_errorhandling.api_response import api_error

SpeechErrorCode = {
    "SPEECH_NOT_CONFIGURED": 503,
    "UNSUPPORTED_MIME": 415,
    "TOO_MANY_RECORDINGS": 429,
    "BUDGET_EXCEEDED": 429,
    "RECORDING_NOT_FOUND": 404,
    "RECORDING_BUSY": 409,
    "CHUNK_INDEX_INVALID": 400,
    "TOO_MANY_CHUNKS": 413,
    "CHUNK_TOO_LARGE": 413,
    "RECORDING_TOO_LARGE": 413,
    "CHUNK_CONFLICT": 409,
    "MISSING_CHUNKS": 409,
    "RECORDING_TOO_LONG": 413,
    "INVALID_AUDIO": 422,
    "TRANSCRIPTION_FAILED": 502,
    "TRANSCRIPTION_TIMEOUT": 504,
}


class SpeechError(Exception):
    def __init__(self, code: str, message: str, detail: object = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_response(self) -> JSONResponse:
        return api_error(self.code, self.message, self.detail, status=SpeechErrorCode[self.code])
