"""Pairing code lifecycle, lockout and device revocation (invariants S3, S4)."""

import secrets
from datetime import datetime
from typing import Optional

from backend.config import (
    PAIRING_CODE_ALPHABET, PAIRING_CODE_LENGTH, PAIRING_CODE_TTL_SECONDS,
    PAIRING_FAILURE_WINDOW_SECONDS, PAIRING_MAX_FAILURES,
)
from backend.models import PairResponse
from backend.security import new_device_token, sha256_hex


class PairingFailed(Exception):
    """Unknown, expired, used or locked code (generic, 403)."""


class PairingRateLimited(Exception):
    """Lockout window active (429)."""


def new_code(length: int, alphabet: str = PAIRING_CODE_ALPHABET) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_pairing_code(conn) -> tuple[str, str, datetime]:
    """Returns (code_id, plain_code, expires_at); only the hash is stored."""
    with conn.cursor() as cur:
        for _ in range(10):  # retry on hash collision
            code = new_code(PAIRING_CODE_LENGTH)
            cur.execute(
                """
                insert into runningtracker.pairing_codes (code_hash, expires_at)
                values (%s, now() + make_interval(secs => %s))
                on conflict (code_hash) do nothing
                returning id, expires_at
                """,
                (sha256_hex(code), PAIRING_CODE_TTL_SECONDS),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                return str(row["id"]), code, row["expires_at"]
    raise RuntimeError("could not generate a unique pairing code")


def _lock_active_codes(cur) -> None:
    cur.execute(
        """
        update runningtracker.pairing_codes set locked_at = now()
        where used_at is null and locked_at is null and expires_at > now()
        """
    )


def _failures_in_window(cur) -> int:
    cur.execute(
        "select count(*) as n from runningtracker.pairing_failures where failed_at > now() - make_interval(secs => %s)",
        (PAIRING_FAILURE_WINDOW_SECONDS,),
    )
    return cur.fetchone()["n"]


def redeem_pairing_code(conn, code: str, device_name: str) -> PairResponse:
    """Applies S3/S4. Commits its own work (lockout must persist even though an exception follows)."""
    with conn.cursor() as cur:
        if _failures_in_window(cur) >= PAIRING_MAX_FAILURES:
            _lock_active_codes(cur)
            conn.commit()
            raise PairingRateLimited()

        # Atomic conditional redeem: two concurrent requests cannot both consume one code.
        cur.execute(
            """
            update runningtracker.pairing_codes set used_at = now()
            where code_hash = %s and used_at is null and locked_at is null and expires_at > now()
            returning id
            """,
            (sha256_hex(code.strip().upper()),),
        )
        redeemed = cur.fetchone()
        if redeemed is None:
            cur.execute("insert into runningtracker.pairing_failures default values")
            if _failures_in_window(cur) >= PAIRING_MAX_FAILURES:
                _lock_active_codes(cur)
            conn.commit()
            raise PairingFailed()

        token = new_device_token()
        cur.execute(
            "insert into runningtracker.devices (name, token_hash) values (%s, %s) returning id",
            (device_name, sha256_hex(token)),
        )
        device_id = str(cur.fetchone()["id"])
        cur.execute(
            "update runningtracker.pairing_codes set device_id = %s where id = %s",
            (device_id, redeemed["id"]),
        )
    conn.commit()
    return PairResponse(device_id=device_id, device_token=token, device_name=device_name)


def revoke_device(conn, device_id: str) -> Optional[dict]:
    """Set revoked_at once (idempotent); None if the device is unknown."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update runningtracker.devices set revoked_at = coalesce(revoked_at, now())
            where id = %s
            returning id, name, created_at, last_used_at, revoked_at
            """,
            (device_id,),
        )
        row = cur.fetchone()
    conn.commit()
    return row
