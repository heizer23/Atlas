"""
Notifications platform service — FastAPI entry point.

Startup sequence:
  1. Setup structured logging (platform_errorhandling)
  2. Install FastAPI exception handlers and request timing middleware
  3. Initialise Postgres connection pool
  4. Load FCM service account credential and initialise firebase_admin
  5. Start APScheduler BackgroundScheduler with 5-second dispatch job

Shutdown sequence:
  1. Stop APScheduler (waits for in-flight dispatch to complete)

The service fails to start if FCM credential env vars are absent.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_pool
from backend.fcm_client import init_fcm
from backend.routers import devices, notifications
from backend.scheduler import start_scheduler, stop_scheduler
from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers
from platform_errorhandling.performance import install_request_timing

setup_logging(
    app_name="notifications",
    log_dir=Path(__file__).resolve().parents[1] / "logs",
)
log = logging.getLogger("notifications")

# Silence high-frequency loggers that would otherwise write thousands of lines/day
# APScheduler logs "Running job..." + "Job executed successfully" on every 5s tick
logging.getLogger("apscheduler").setLevel(logging.WARNING)
# Uvicorn access log writes one line per HTTP request into the root logger file
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="Notifications", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)

install_exception_handlers(app)
install_request_timing(app)
app.include_router(notifications.router, prefix="/api")
app.include_router(devices.router, prefix="/api")

_scheduler = None


@app.on_event("startup")
def on_startup() -> None:
    import os
    global _scheduler
    log.info("Initialising Postgres connection pool...")
    init_pool()
    log.info("Postgres pool ready.")

    default_token = os.environ.get("FCM_DEFAULT_DEVICE_TOKEN", "").strip()
    if default_token:
        from backend.database import get_db
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.device (device_id, fcm_token, updated_at)
                    VALUES ('default', %s, NOW())
                    ON CONFLICT (device_id) DO UPDATE
                        SET fcm_token = EXCLUDED.fcm_token, updated_at = NOW()
                    """,
                    (default_token,),
                )
                conn.commit()
        log.info("Default device FCM token seeded from FCM_DEFAULT_DEVICE_TOKEN.")
    else:
        log.warning("FCM_DEFAULT_DEVICE_TOKEN not set — no default device registered.")

    log.info("Loading FCM credential...")
    init_fcm()
    log.info("FCM initialised.")

    log.info("Starting APScheduler dispatch job...")
    _scheduler = start_scheduler()
    log.info("Scheduler started. Notifications service ready.")


@app.on_event("shutdown")
def on_shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        log.info("Stopping APScheduler...")
        stop_scheduler(_scheduler)
        log.info("Scheduler stopped.")
