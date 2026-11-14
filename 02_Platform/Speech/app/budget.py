"""Spend safeguard: caps transcribed audio per day and transcriptions per hour.

State is a small JSON file so a container restart does not reset the budget.
Only successfully transcribed audio is charged. Counts audio seconds, not money:
cost scales linearly with audio duration for OpenAI transcription.
"""

import json
import threading
import time
from functools import lru_cache

from fastapi import Depends
from pathlib import Path

from app.config import SpeechSettings, get_settings
from app.errors import SpeechError


class Budget:
    def __init__(self, path: str, daily_audio_s: int, hourly_transcriptions: int):
        self._path = Path(path)
        self._daily_audio_s = daily_audio_s
        self._hourly = hourly_transcriptions
        self._lock = threading.Lock()
        self._events: list[list[float]] = []  # [timestamp, audio_seconds]
        try:
            self._events = json.loads(self._path.read_text())
        except (OSError, ValueError):
            pass

    def _prune(self, now: float) -> None:
        self._events = [e for e in self._events if now - e[0] < 86400]

    def check(self, audio_s: float) -> None:
        """Raise BUDGET_EXCEEDED if transcribing audio_s more seconds would break a cap."""
        now = time.time()
        with self._lock:
            self._prune(now)
            if sum(e[1] for e in self._events) + audio_s > self._daily_audio_s:
                raise SpeechError("BUDGET_EXCEEDED", "Daily speech budget reached. Try again later.")
            if sum(1 for e in self._events if now - e[0] < 3600) >= self._hourly:
                raise SpeechError("BUDGET_EXCEEDED", "Hourly transcription limit reached. Try again later.")

    def record(self, audio_s: float) -> None:
        now = time.time()
        with self._lock:
            self._prune(now)
            self._events.append([now, audio_s])
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(json.dumps(self._events))
            except OSError:
                pass  # in-memory accounting still enforces the cap until restart


@lru_cache
def _store(path: str, daily: int, hourly: int) -> Budget:
    return Budget(path, daily, hourly)


def get_budget(s: SpeechSettings = Depends(get_settings)) -> Budget:
    return _store(s.budget_path, s.daily_audio_s, s.hourly_transcriptions)
