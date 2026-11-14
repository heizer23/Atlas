"""Chunk concatenation and ffmpeg interaction (argument lists only, never a shell)."""

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import SpeechSettings
from app.errors import SpeechError

_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4"}
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass
class AssembledAudio:
    path: Path
    size_bytes: int
    duration_ms: int
    mime_type: str
    assemble_ms: int


def _run(args: list, timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-y", *args],
                              capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        raise SpeechError("INVALID_AUDIO", "Audio could not be processed.")


def assemble(chunk_paths: list, mime_type: str, work_dir: Path, settings: SpeechSettings) -> AssembledAudio:
    t0 = time.perf_counter()
    ext = _EXT.get(mime_type, "webm")
    raw = work_dir / f"raw.{ext}"
    out = work_dir / f"audio.{ext}"
    with open(raw, "wb") as dst:
        for p in chunk_paths:
            with open(p, "rb") as src:
                while block := src.read(1 << 20):
                    dst.write(block)

    # Remux without re-encoding: repairs the missing duration header and proves decodability.
    r = _run(["-i", str(raw), "-vn", "-c", "copy", str(out)], settings.ffmpeg_timeout_s)
    if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise SpeechError("INVALID_AUDIO", "Reassembled audio is not decodable.")

    # Decode to the null muxer; do not trust the container header for duration.
    r = _run(["-i", str(out), "-vn", "-f", "null", "-"], settings.ffmpeg_timeout_s)
    if r.returncode != 0:
        raise SpeechError("INVALID_AUDIO", "Reassembled audio is not decodable.")
    times = _TIME_RE.findall(r.stderr.decode("utf-8", "replace"))
    if not times:
        raise SpeechError("INVALID_AUDIO", "Reassembled audio has no duration.")
    h, m, s = times[-1]
    duration_ms = int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)
    if duration_ms <= 0:
        raise SpeechError("INVALID_AUDIO", "Reassembled audio is empty.")
    if duration_ms > settings.max_duration_s * 1000:
        raise SpeechError("RECORDING_TOO_LONG", "Recording exceeds the maximum duration.")
    raw.unlink(missing_ok=True)
    return AssembledAudio(path=out, size_bytes=out.stat().st_size, duration_ms=duration_ms,
                          mime_type=mime_type, assemble_ms=int((time.perf_counter() - t0) * 1000))
