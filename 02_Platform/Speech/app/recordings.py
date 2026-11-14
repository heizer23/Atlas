"""Ephemeral recording registry and chunk files under tmp_dir.

Single owner of recording lifecycle and deletion. All state mutation between
awaits is synchronous, so the single event loop makes status flips atomic.
"""

import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import Depends

from app.config import SpeechSettings, get_settings
from app.errors import SpeechError
from app.models import ChunkAck

MAX_LISTED_MISSING = 20


@dataclass
class RecordingState:
    recording_id: str
    mime_type: str
    status: str = "open"  # open | finalizing
    chunk_sizes: dict = field(default_factory=dict)
    total_bytes: int = 0
    upload_ms: int = 0
    created_at: float = 0.0
    last_activity: float = 0.0
    cancelled: bool = False


class RecordingStore:
    def __init__(self, settings: SpeechSettings):
        self.settings = settings
        self.root = Path(settings.tmp_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        for child in self.root.iterdir():  # startup sweep
            shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)
        self._recs: dict[str, RecordingState] = {}

    def dir_for(self, recording_id: str) -> Path:
        return self.root / recording_id

    def create(self, mime_type: str) -> RecordingState:
        base = mime_type.split(";")[0].strip().lower()
        if base not in self.settings.allowed_mime_types:
            raise SpeechError("UNSUPPORTED_MIME", f"Unsupported audio type: {base}")
        if len(self._recs) >= self.settings.max_active_recordings:
            raise SpeechError("TOO_MANY_RECORDINGS", "Too many active recordings.")
        rid = uuid.uuid4().hex
        self.dir_for(rid).mkdir(parents=True)
        now = time.time()
        st = RecordingState(recording_id=rid, mime_type=base, created_at=now, last_activity=now)
        self._recs[rid] = st
        return st

    def get(self, recording_id: str) -> RecordingState:
        st = self._recs.get(recording_id)
        if st is None:
            raise SpeechError("RECORDING_NOT_FOUND", "Recording not found (expired, cancelled or service restarted).")
        return st

    async def write_chunk(self, recording_id: str, index: int, stream: AsyncIterator[bytes],
                          content_type: Optional[str]) -> ChunkAck:
        st = self.get(recording_id)
        if st.status != "open":
            raise SpeechError("RECORDING_BUSY", "Recording is being finalized.")
        if index < 0:
            raise SpeechError("CHUNK_INDEX_INVALID", "Chunk index must be non-negative.")
        if index >= self.settings.max_chunks:
            raise SpeechError("TOO_MANY_CHUNKS", f"Chunk index must be below {self.settings.max_chunks}.")
        base = (content_type or "").split(";")[0].strip().lower()
        if base != st.mime_type:
            raise SpeechError("UNSUPPORTED_MIME", "Chunk content type does not match the recording.")

        d = self.dir_for(recording_id)
        part = d / f"{index}.part"
        size = 0
        t0 = time.perf_counter()
        try:
            with open(part, "wb") as f:
                async for piece in stream:
                    size += len(piece)
                    if size > self.settings.max_chunk_bytes:
                        raise SpeechError("CHUNK_TOO_LARGE", "Chunk exceeds the maximum chunk size.")
                    f.write(piece)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        st.upload_ms += int((time.perf_counter() - t0) * 1000)

        # The recording may have been cancelled/reaped/finalized while the body streamed.
        if self._recs.get(recording_id) is not st or st.cancelled:
            part.unlink(missing_ok=True)
            raise SpeechError("RECORDING_NOT_FOUND", "Recording not found (expired, cancelled or service restarted).")
        if st.status != "open":
            part.unlink(missing_ok=True)
            raise SpeechError("RECORDING_BUSY", "Recording is being finalized.")

        if index in st.chunk_sizes:
            part.unlink(missing_ok=True)
            if st.chunk_sizes[index] != size:
                raise SpeechError("CHUNK_CONFLICT", "Chunk index re-sent with a different size.")
        else:
            if st.total_bytes + size > self.settings.max_total_bytes:
                self.delete(recording_id)
                raise SpeechError("RECORDING_TOO_LARGE", "Recording exceeds the maximum total size.")
            part.replace(d / f"{index}.chunk")
            st.chunk_sizes[index] = size
            st.total_bytes += size
        st.last_activity = time.time()
        return ChunkAck(recording_id=recording_id, index=index,
                        chunks_received=len(st.chunk_sizes), total_bytes=st.total_bytes)

    def begin_finalize(self, recording_id: str, expected_chunks: int, client_duration_ms: int) -> list[Path]:
        st = self.get(recording_id)
        if st.status != "open":
            raise SpeechError("RECORDING_BUSY", "A stop is already in progress for this recording.")
        if expected_chunks > self.settings.max_chunks:
            raise SpeechError("CHUNK_INDEX_INVALID", f"expected_chunks exceeds the limit of {self.settings.max_chunks}.")
        if client_duration_ms > self.settings.max_duration_s * 1000:
            self.delete(recording_id)
            raise SpeechError("RECORDING_TOO_LONG", "Recording exceeds the maximum duration.")
        st.status = "finalizing"
        st.last_activity = time.time()
        expected = set(range(expected_chunks))
        have = set(st.chunk_sizes)
        missing = sorted(expected - have)
        extra = sorted(have - expected)
        if missing or extra:
            st.status = "open"
            raise SpeechError("MISSING_CHUNKS", "Chunks are missing or unexpected.",
                              {"missing": missing[:MAX_LISTED_MISSING], "unexpected": extra[:MAX_LISTED_MISSING]})
        d = self.dir_for(recording_id)
        return [d / f"{i}.chunk" for i in range(expected_chunks)]

    def end_finalize(self, recording_id: str, retain: bool) -> None:
        st = self._recs.get(recording_id)
        if st is None:
            return
        if retain and not st.cancelled:
            st.status = "open"
            st.last_activity = time.time()
            return
        self.delete(recording_id)

    def cancel(self, recording_id: str) -> None:
        st = self._recs.get(recording_id)
        if st is None:
            return
        if st.status == "finalizing":
            st.cancelled = True
            return
        self.delete(recording_id)

    def delete(self, recording_id: str) -> None:
        self._recs.pop(recording_id, None)
        shutil.rmtree(self.dir_for(recording_id), ignore_errors=True)

    def reap_idle(self, now: float) -> int:
        stale = [r for r, s in self._recs.items()
                 if s.status == "open" and now - s.last_activity > self.settings.idle_ttl_s]
        for r in stale:
            self.delete(r)
        return len(stale)


_store: Optional[RecordingStore] = None


def get_store(settings: SpeechSettings = Depends(get_settings)) -> RecordingStore:
    global _store
    if _store is None:
        _store = RecordingStore(settings)
    return _store
