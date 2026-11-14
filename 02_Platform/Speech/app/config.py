"""Speech runtime settings. Read from the environment once; secrets are masked in repr."""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class SpeechSettings:
    whisper_key: str = field(default="", repr=False)
    model: str = "gpt-transcribe"
    fallback_model: str = "gpt-4o-transcribe"
    allowed_mime_types: tuple = ("audio/webm", "audio/ogg", "audio/mp4")
    chunk_timeslice_ms: int = 15000
    max_chunk_bytes: int = 2097152
    max_total_bytes: int = 20971520
    max_chunks: int = 80
    max_duration_s: int = 600
    max_active_recordings: int = 4
    idle_ttl_s: int = 900
    upstream_timeout_s: int = 120
    ffmpeg_timeout_s: int = 60
    tmp_dir: str = "/tmp/speech"
    budget_path: str = "/data/budget.json"
    daily_audio_s: int = 3600
    hourly_transcriptions: int = 30
    vocabulary_path: str = str(Path(__file__).resolve().parents[1] / "config" / "vocabulary.json")

    def __repr__(self) -> str:  # never reveal secrets
        return "SpeechSettings(<masked>)"


@lru_cache
def get_settings() -> SpeechSettings:
    e = os.environ.get
    return SpeechSettings(
        whisper_key=e("SPEECH_OPENAI_KEY", ""),
        model=e("SPEECH_MODEL", "gpt-transcribe"),
        fallback_model=e("SPEECH_FALLBACK_MODEL", "gpt-4o-transcribe"),
        chunk_timeslice_ms=_int("SPEECH_CHUNK_TIMESLICE_MS", 15000),
        max_chunk_bytes=_int("SPEECH_MAX_CHUNK_BYTES", 2097152),
        max_total_bytes=_int("SPEECH_MAX_TOTAL_BYTES", 20971520),
        max_chunks=_int("SPEECH_MAX_CHUNKS", 80),
        max_duration_s=_int("SPEECH_MAX_DURATION_S", 600),
        max_active_recordings=_int("SPEECH_MAX_ACTIVE", 4),
        idle_ttl_s=_int("SPEECH_IDLE_TTL_S", 900),
        upstream_timeout_s=_int("SPEECH_UPSTREAM_TIMEOUT_S", 120),
        ffmpeg_timeout_s=_int("SPEECH_FFMPEG_TIMEOUT_S", 60),
        tmp_dir=e("SPEECH_TMP_DIR", "/tmp/speech"),
        budget_path=e("SPEECH_BUDGET_PATH", "/data/budget.json"),
        daily_audio_s=_int("SPEECH_DAILY_AUDIO_S", 3600),
        hourly_transcriptions=_int("SPEECH_HOURLY_TRANSCRIPTIONS", 30),
    )
