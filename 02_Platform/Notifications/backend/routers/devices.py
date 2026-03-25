"""
Device token registration endpoints.

Stores the FCM token for a device so that application frontends can retrieve it
when scheduling notifications. Keyed by device_id — "default" is used for the
single-device MVP case.

Endpoints:
  POST /api/devices/token   — upsert FCM token for a device
  GET  /api/devices/token   — retrieve current FCM token for a device
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from platform_errorhandling.api_response import api_error

log = logging.getLogger("notifications.devices")
router = APIRouter()


class DeviceTokenRequest(BaseModel):
    token: str
    device_id: str = "default"


@router.post("/devices/token", status_code=200)
def register_token(body: DeviceTokenRequest) -> JSONResponse:
    """Upsert FCM token for a device. Called by the Android app on token refresh."""
    sql = """
        INSERT INTO notifications.device (device_id, fcm_token, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (device_id) DO UPDATE
            SET fcm_token  = EXCLUDED.fcm_token,
                updated_at = NOW()
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (body.device_id, body.token))
            conn.commit()
    log.info("FCM token registered for device_id=%s", body.device_id)
    return JSONResponse(status_code=200, content={"registered": True, "device_id": body.device_id})


@router.get("/devices/token")
def get_token(device_id: str = "default") -> JSONResponse:
    """Return the current FCM token for a device. Called by application frontends."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fcm_token FROM notifications.device WHERE device_id = %s",
                (device_id,),
            )
            row = cur.fetchone()
    if row is None:
        return api_error(
            code="DEVICE_NOT_FOUND",
            message=f"No device registered with id '{device_id}'. Open AtlasPhone to register.",
            detail={"device_id": device_id},
            status=404,
        )
    return JSONResponse(status_code=200, content={"device_id": device_id, "token": row["fcm_token"]})
