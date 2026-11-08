"""Hashing, device tokens, native auth dependencies and the public-route backstop (flow step 3)."""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from backend.config import DEVICE_LAST_USED_THROTTLE_SECONDS, MAX_BODY_BYTES
from backend.database import get_db


class AppError(Exception):
    """Raised anywhere; main.py turns it into the platform ApiError envelope."""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class DeviceContext:
    device_id: str
    name: str


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_device_token() -> str:
    """256-bit CSPRNG token (43 url-safe chars)."""
    return secrets.token_urlsafe(32)


def native_guard(request: Request) -> None:
    """Dependency for ALL native routes (E1 backstop; the nginx 404 block is the control)."""
    if "cf-connecting-ip" in request.headers:
        raise AppError("NATIVE_ROUTE_FORBIDDEN", "Native routes are not available on this path.", 403)
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_BODY_BYTES:
        raise AppError("PAYLOAD_TOO_LARGE", "Request body too large.", 413)
    # Limitation: only Content-Length is checked; a chunked body is not capped here (tailnet-only, single user).


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_device(request: Request) -> DeviceContext:
    """Bearer token -> non-revoked device, else 401 DEVICE_UNAUTHORIZED. Updates last_used_at (throttled)."""
    unauthorized = AppError("DEVICE_UNAUTHORIZED", "Device not authorized. Pair this phone again.", 401)
    token = _bearer(request)
    if token is None:
        raise unauthorized
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name from runningtracker.devices where token_hash = %s and revoked_at is null",
                (sha256_hex(token),),
            )
            row = cur.fetchone()
            if row is None:
                raise unauthorized
            cur.execute(
                """
                update runningtracker.devices set last_used_at = now()
                where id = %s and (last_used_at is null
                      or last_used_at < now() - make_interval(secs => %s))
                """,
                (row["id"], DEVICE_LAST_USED_THROTTLE_SECONDS),
            )
        conn.commit()
    return DeviceContext(device_id=str(row["id"]), name=row["name"])
