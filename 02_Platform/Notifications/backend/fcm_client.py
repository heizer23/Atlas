"""
FCM credential loading and firebase_admin initialisation.

Isolates credential management from dispatch logic.
Called once during FastAPI startup via init_fcm().

SECURITY: FCM credentials are loaded from environment variables only.
They must never be hardcoded or read from a config file checked into source control.

INVARIANT: fcm_token must never appear in any log output.
"""

import json
import os

import firebase_admin
from firebase_admin import credentials, messaging


def init_fcm() -> None:
    """Load FCM service account credential from environment and initialise firebase_admin.

    Checks FCM_SERVICE_ACCOUNT_JSON_PATH (file path) first, then
    FCM_SERVICE_ACCOUNT_JSON_CONTENT (raw JSON string).
    Raises RuntimeError if neither env var is set.
    """
    path = os.environ.get("FCM_SERVICE_ACCOUNT_JSON_PATH")
    content = os.environ.get("FCM_SERVICE_ACCOUNT_JSON_CONTENT")

    if path:
        cred = credentials.Certificate(path)
    elif content:
        service_account_info = json.loads(content)
        cred = credentials.Certificate(service_account_info)
    else:
        raise RuntimeError(
            "FCM credential not configured. "
            "Set FCM_SERVICE_ACCOUNT_JSON_PATH or FCM_SERVICE_ACCOUNT_JSON_CONTENT."
        )

    firebase_admin.initialize_app(cred)


def send_fcm_message(
    token: str,
    notification_id: str,
    title: str,
    body: str,
    label: str,
    deep_link: str,
) -> str:
    """Build a data-only FCM message and send it via firebase_admin.

    Returns the FCM message ID string on success.
    Raises on FCM error — caller is responsible for catching and setting status=failed.

    The FCM payload contains exactly these 5 fields as per fcm_payload_contract.json v1.0:
        notification_id, title, body, label, deep_link

    All values are strings. No 'notification' key is included (data-only message).
    The token is not logged — never pass it to any logging call.
    """
    message = messaging.Message(
        token=token,
        data={
            "notification_id": notification_id,
            "title":           title,
            "body":            body,
            "label":           label,
            "deep_link":       deep_link,
        },
        # Intentionally no messaging.Notification() — data-only per contract.
    )
    return messaging.send(message)
