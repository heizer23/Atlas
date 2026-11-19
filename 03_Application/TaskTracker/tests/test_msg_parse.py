import struct

import pytest

from backend import msg_parse


class FakeOle:
    def __init__(self, streams: dict[str, bytes]):
        self.streams = streams

    def exists(self, name): return name in self.streams
    def get_size(self, name): return len(self.streams[name])

    def openstream(self, name):
        import io
        return io.BytesIO(self.streams[name])


def _u(s: str) -> bytes:
    return s.encode("utf-16-le") + b"\x00\x00"


def test_summarize_reads_subject_sender_date_body():
    ft = (134774 * 86400 + 0) * 10_000_000  # 1601 + 134774 days = 1970-01-01
    props = bytes(32) + struct.pack("<IIQ", 0x00390040, 0, ft)
    ole = FakeOle({
        "__substg1.0_0037001F": _u("Quarterly report"),
        "__substg1.0_0C1A001F": _u("Ada"),
        "__substg1.0_5D01001F": _u("ada@example.com"),
        "__substg1.0_1000001F": _u("Please review."),
        "__properties_version1.0": props,
    })
    out = msg_parse.summarize(ole)
    assert out["subject"] == "Quarterly report"
    assert out["sender"] == "Ada <ada@example.com>"
    assert out["sent_at"].startswith("1970-01-01")
    assert out["body"] == "Please review."


def test_exchange_dn_sender_address_is_ignored():
    ole = FakeOle({
        "__substg1.0_0C1A001F": _u("Ada"),
        "__substg1.0_0C1F001F": _u("/O=EXCH/OU=X/CN=ADA"),
    })
    assert msg_parse.summarize(ole)["sender"] == "Ada"


def test_rejects_non_msg_and_oversize():
    with pytest.raises(msg_parse.NotAMsgFile):
        msg_parse.parse_msg(b"hello")
    with pytest.raises(msg_parse.NotAMsgFile):
        msg_parse.parse_msg(b"\0" * (msg_parse.MAX_MSG_BYTES + 1))
