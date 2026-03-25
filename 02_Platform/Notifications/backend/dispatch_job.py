"""
APScheduler job that polls Postgres for due pending notifications and dispatches
them through FCM.

Called every 5 seconds by the BackgroundScheduler registered in scheduler.py.

INVARIANT: fcm_token must never appear in any log output. This module
explicitly excludes the token from every log statement.

delta_ms is computed as (dispatched_at - fire_at) in milliseconds,
not (dispatched_at - created_at).
"""

import logging
from datetime import datetime, timezone

from backend.database import get_db
from backend.fcm_client import send_fcm_message

log = logging.getLogger("notifications.dispatch")


def dispatch_due_notifications() -> None:
    """Query pending notifications with fire_at <= now() and dispatch each via FCM.

    For each due notification:
    - Builds a data-only FCM message.
    - Calls send_fcm_message().
    - Records dispatched_at, computes delta_ms = dispatched_at - fire_at (milliseconds).
    - Logs at INFO: notification_id, fire_at, dispatched_at, delta_ms.
    - Updates status to 'dispatched' on success, 'failed' on FCM error.

    fcm_token is fetched from Postgres but is never logged.
    """
    select_sql = """
        SELECT id, fire_at, title, body, label, deep_link, fcm_token
        FROM notifications.notification
        WHERE status = 'pending' AND fire_at <= NOW()
    """
    update_dispatched_sql = """
        UPDATE notifications.notification
        SET status = 'dispatched'
        WHERE id = %s
    """
    update_failed_sql = """
        UPDATE notifications.notification
        SET status = 'failed'
        WHERE id = %s
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(select_sql)
            rows = cur.fetchall()

        for row in rows:
            notification_id = str(row["id"])
            fire_at         = row["fire_at"]
            # fcm_token is used only for dispatch — never logged
            fcm_token       = row["fcm_token"]

            try:
                send_fcm_message(
                    token           = fcm_token,
                    notification_id = notification_id,
                    title           = row["title"],
                    body            = row["body"],
                    label           = row["label"],
                    deep_link       = row["deep_link"],
                )
                dispatched_at = datetime.now(timezone.utc)
                # delta_ms is fire_at-relative, not created_at-relative
                if fire_at.tzinfo is None:
                    fire_at = fire_at.replace(tzinfo=timezone.utc)
                delta_ms = int((dispatched_at - fire_at).total_seconds() * 1000)

                log.info(
                    "dispatched notification_id=%s fire_at=%s dispatched_at=%s delta_ms=%d",
                    notification_id,
                    fire_at.isoformat(),
                    dispatched_at.isoformat(),
                    delta_ms,
                )
                with conn.cursor() as cur:
                    cur.execute(update_dispatched_sql, (notification_id,))
                    conn.commit()

            except Exception as exc:
                log.error(
                    "FCM dispatch failed notification_id=%s error=%s",
                    notification_id,
                    exc,
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute(update_failed_sql, (notification_id,))
                        conn.commit()
                except Exception as db_exc:
                    log.error(
                        "Failed to update status=failed notification_id=%s db_error=%s",
                        notification_id,
                        db_exc,
                    )
