"""
Google OAuth 2.0 helpers for CalendarConnector.

Handles authorization URL construction, code-for-token exchange, and token refresh.
Uses httpx for HTTP calls. Reads GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from environment.

Scope: https://www.googleapis.com/auth/calendar.readonly (this slice only).
Does NOT touch the existing Atlas login flow. These helpers are calendar-specific.
"""
import logging
import os
from urllib.parse import urlencode

import httpx

log = logging.getLogger("calendar_connector")

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
# Sprint02: upgraded from calendar.readonly to calendar (read+write superset).
# Operator must re-run GET /api/calendar/google/connect/start to re-consent with
# the expanded scope. Existing read functionality continues to work — calendar
# scope is a superset of calendar.readonly.


def _client_id() -> str:
    val = os.environ.get("GoogleAuth_ClientID") or os.environ.get("GOOGLE_CLIENT_ID", "")
    if not val:
        raise RuntimeError("GoogleAuth_ClientID environment variable not set")
    return val


def _client_secret() -> str:
    val = os.environ.get("GoogleAuth_Secret") or os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not val:
        raise RuntimeError("GoogleAuth_Secret environment variable not set")
    return val


def build_authorization_url(state: str, redirect_uri: str) -> str:
    """Return the Google OAuth authorization URL with scope=calendar.readonly,
    access_type=offline, and prompt=consent.

    prompt=consent ensures a refresh_token is returned on every grant, even if
    the user has previously authorized.
    """
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """POST to Google token endpoint with auth code.

    Returns the token response dict containing access_token, refresh_token,
    expires_in, token_type, scope (and optionally id_token).
    Raises ValueError on error response from Google.
    """
    response = httpx.post(
        _GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    data = response.json()
    if response.status_code != 200 or "error" in data:
        error_desc = data.get("error_description", data.get("error", "unknown"))
        raise ValueError(f"Google token exchange failed: {error_desc}")
    return data


def refresh_access_token(refresh_token: str) -> dict:
    """POST to Google token endpoint with refresh_token.

    Returns updated token dict with at minimum access_token and expires_in.
    Raises ValueError on 4xx (revoked or expired refresh token).
    """
    response = httpx.post(
        _GOOGLE_TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15.0,
    )
    data = response.json()
    if response.status_code != 200 or "error" in data:
        error_desc = data.get("error_description", data.get("error", "unknown"))
        raise ValueError(f"Google token refresh failed (status={response.status_code}): {error_desc}")
    return data


def get_account_email(access_token: str) -> str | None:
    """Fetch account email from Google userinfo endpoint using the access_token.

    Returns the email string, or None if unavailable.
    This avoids needing a JWT library to decode the id_token.
    """
    try:
        response = httpx.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json().get("email")
    except Exception as exc:
        log.warning("Could not fetch account email from userinfo endpoint: %s", exc)
    return None
