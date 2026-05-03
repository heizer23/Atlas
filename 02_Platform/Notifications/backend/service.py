"""
Notification lifecycle operations: create, cancel, replace, send_immediate.

These methods are platform-internal. They have no domain knowledge of the
application that created a notification. The 'source' field is an opaque tag.

All database access goes through database.get_db().
"""

import uuid
from datetime import datetime, timezone

from backend.database import get_db
from backend.fcm_client import send_fcm_message
from backend.models import (
    ImmediateSendRequest,
    ImmediateSendResponse,
    NotificationCreateRequest,
    NotificationRecord,
)


class NotificationNotFoundError(Exception):
    """Raised when a notification id does not exist in Postgres."""
    def __init__(self, notification_id: str):
        self.notification_id = notification_id
        super().__init__(f"Notification not found: {notification_id}")


class NoDefaultDeviceError(Exception):
    """Raised when notifications.device has no row for device_id='default'."""


class FCMDispatchError(Exception):
    """Raised when send_fcm_message() raises during an immediate send.

    Wraps the original FCM exception as the cause.
    INVARIANT: must not include fcm_token in message or attributes.
    """
    def __init__(self, cause: Exception):
        super().__init__(f"FCM dispatch failed: {type(cause).__name__}")
        self.__cause__ = cause


class NotificationService:

    def create(self, payload: NotificationCreateRequest) -> NotificationRecord:
        """Generate a UUID, write a pending notification row to Postgres,
        return NotificationRecord (without fcm_token).
        """
        notification_id = str(uuid.uuid4())
        sql = """
            INSERT INTO notifications.notification
                (id, source, fire_at, title, body, label, deep_link, fcm_token, status)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            RETURNING id, source, fire_at, title, body, label, deep_link, status, created_at
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    notification_id,
                    payload.source,
                    payload.fire_at,
                    payload.title,
                    payload.body,
                    payload.label,
                    payload.deep_link,
                    payload.fcm_token,
                ))
                row = cur.fetchone()
                conn.commit()
        return NotificationRecord(
            id=str(row["id"]),
            source=row["source"],
            fire_at=row["fire_at"],
            title=row["title"],
            body=row["body"],
            label=row["label"],
            deep_link=row["deep_link"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def cancel(self, notification_id: str) -> None:
        """Set status=cancelled if status=pending.
        No-op (return success) if status=dispatched, cancelled, or failed —
        cancel is idempotent for all terminal states.
        Raise NotificationNotFoundError if id does not exist.
        """
        select_sql = """
            SELECT status FROM notifications.notification WHERE id = %s
        """
        update_sql = """
            UPDATE notifications.notification
            SET status = 'cancelled'
            WHERE id = %s AND status = 'pending'
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(select_sql, (notification_id,))
                row = cur.fetchone()
                if row is None:
                    raise NotificationNotFoundError(notification_id)
                # For terminal states (dispatched, cancelled, failed): no-op.
                if row["status"] == "pending":
                    cur.execute(update_sql, (notification_id,))
                    conn.commit()

    def replace(
        self,
        old_id: str,
        new_payload: NotificationCreateRequest,
    ) -> NotificationRecord:
        """Cancel old notification then create new one.

        Not atomic. If cancel fails, error is returned before create is attempted.
        If create fails after cancel succeeds, old record remains cancelled and
        the caller receives an error for the create step.
        """
        self.cancel(old_id)
        return self.create(new_payload)

    def send_immediate(self, payload: ImmediateSendRequest) -> ImmediateSendResponse:
        """Dispatch a notification immediately to the default device.

        Steps:
          1. Fetch FCM token from notifications.device WHERE device_id='default'.
             Raises NoDefaultDeviceError if no device is registered.
          2. Generate a new UUID for the notification record.
          3. Call send_fcm_message() synchronously.
             Raises FCMDispatchError if FCM raises. No DB write on FCM failure.
          4. Persist the notification with status='dispatched', fire_at=NULL.
          5. Return ImmediateSendResponse with the server-captured dispatched_at.

        INVARIANT: fcm_token is never logged or returned in the response.
        """
        select_device_sql = """
            SELECT fcm_token FROM notifications.device WHERE device_id = 'default'
        """
        insert_sql = """
            INSERT INTO notifications.notification
                (id, source, fire_at, title, body, label, deep_link, fcm_token, status)
            VALUES
                (%s, %s, NULL, %s, %s, '', '', %s, 'dispatched')
        """

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(select_device_sql)
                device_row = cur.fetchone()

            if device_row is None:
                raise NoDefaultDeviceError()

            # fcm_token used only for dispatch — never logged per module invariant
            fcm_token = device_row["fcm_token"]
            notification_id = str(uuid.uuid4())

            try:
                send_fcm_message(
                    token=fcm_token,
                    notification_id=notification_id,
                    title=payload.title,
                    body=payload.body,
                    label="",
                    deep_link="atlas://",
                )
            except Exception as exc:
                raise FCMDispatchError(exc) from exc

            # Capture dispatched_at after successful FCM send
            dispatched_at = datetime.now(timezone.utc)

            with conn.cursor() as cur:
                cur.execute(insert_sql, (
                    notification_id,
                    payload.source,
                    payload.title,
                    payload.body,
                    fcm_token,
                ))
            conn.commit()

        return ImmediateSendResponse(
            id=notification_id,
            title=payload.title,
            body=payload.body,
            dispatched_at=dispatched_at,
        )
