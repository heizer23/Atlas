"""Minimal Outlook .msg reader (OLE compound file) for drag-and-drop task creation.

Reads only subject, sender, sent date and plain-text body. Attachments are never
touched. Pure parsing with `olefile`; input is untrusted, so every read is capped.
"""
import io
import struct
from datetime import datetime, timedelta, timezone
from typing import Any

import olefile

MAX_MSG_BYTES = 10 * 1024 * 1024
_MAX_STREAM_BYTES = 1024 * 1024
MAX_BODY_CHARS = 4000

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PROP_STREAM = "__properties_version1.0"
_TAG_SUBMIT_TIME = 0x00390040   # PidTagClientSubmitTime
_TAG_DELIVERY_TIME = 0x0E060040  # PidTagMessageDeliveryTime


class NotAMsgFile(ValueError):
    pass


def _read_stream(ole: Any, name: str) -> bytes | None:
    if not ole.exists(name):
        return None
    if ole.get_size(name) > _MAX_STREAM_BYTES:
        return None
    return ole.openstream(name).read(_MAX_STREAM_BYTES)


def _text(ole: Any, prop_id: str) -> str | None:
    """String property: unicode (001F) preferred, 8-bit (001E) as fallback."""
    raw = _read_stream(ole, f"__substg1.0_{prop_id}001F")
    if raw is not None:
        return raw.decode("utf-16-le", errors="replace").rstrip("\x00").strip() or None
    raw = _read_stream(ole, f"__substg1.0_{prop_id}001E")
    if raw is not None:
        return raw.decode("cp1252", errors="replace").rstrip("\x00").strip() or None
    return None


def _filetime(ole: Any) -> datetime | None:
    raw = _read_stream(ole, _PROP_STREAM)
    if not raw or len(raw) < 32:
        return None
    found: dict[int, int] = {}
    # 32-byte header for a top-level message, then 16-byte property entries.
    for off in range(32, len(raw) - 15, 16):
        tag, _flags, value = struct.unpack_from("<IIQ", raw, off)
        if tag in (_TAG_SUBMIT_TIME, _TAG_DELIVERY_TIME):
            found[tag] = value
    value = found.get(_TAG_SUBMIT_TIME) or found.get(_TAG_DELIVERY_TIME)
    if not value:
        return None
    try:
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value // 10)
    except OverflowError:
        return None


def parse_msg(data: bytes) -> dict[str, str | None]:
    """Return {subject, sender, sent_at (ISO), body}. Raises NotAMsgFile."""
    if len(data) > MAX_MSG_BYTES:
        raise NotAMsgFile("file too large")
    if not data.startswith(_OLE_MAGIC):
        raise NotAMsgFile("not an Outlook .msg file")
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception as exc:  # olefile raises many types on malformed input
        raise NotAMsgFile("unreadable .msg file") from exc
    try:
        if not ole.exists(_PROP_STREAM):
            raise NotAMsgFile("not an Outlook .msg file")
        return summarize(ole)
    finally:
        ole.close()


def summarize(ole: Any) -> dict[str, str | None]:
    name = _text(ole, "0C1A")
    # PidTagSenderSmtpAddress; PR_SENDER_EMAIL_ADDRESS is often an Exchange DN, so only a fallback.
    addr = _text(ole, "5D01")
    if not addr:
        cand = _text(ole, "0C1F")
        addr = cand if cand and "@" in cand else None
    if name and addr:
        sender = f"{name} <{addr}>"
    else:
        sender = name or addr
    sent = _filetime(ole)
    body = _text(ole, "1000")
    if body and len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS].rstrip() + " …"
    return {
        "subject": _text(ole, "0037"),
        "sender": sender,
        "sent_at": sent.isoformat() if sent else None,
        "body": body,
    }
