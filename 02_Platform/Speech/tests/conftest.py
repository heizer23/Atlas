"""Speech test fixtures. No database; no real OpenAI call.

Run inside the test container:
    docker exec atlas-speech-test pytest tests/ -v
"""

import json
import os
import subprocess
import sys
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_platform_packages = os.path.abspath(os.path.join(_app_root, "..", "packages"))
for p in (_platform_packages, _app_root):
    if p not in sys.path:
        sys.path.insert(0, p)

import app.recordings as recordings  # noqa: E402
from app.budget import _store as _budget_store  # noqa: E402
from app.config import SpeechSettings, get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.recordings import RecordingStore  # noqa: E402
from app.transcriber import Transcriber, get_transcriber  # noqa: E402

OPENAI_KEY = "sk-SECRET-KEY-123"
HEADERS: dict = {}


class FakeTranscriber:
    """Replaces Transcriber wholesale; records what it received."""

    def __init__(self):
        self.calls = []
        self.text = "hello world"
        self.fail = None  # a SpeechError to raise

    async def transcribe(self, audio, vocab):
        from app.transcriber import TranscriptionOutcome
        with open(audio.path, "rb") as f:
            data = f.read()
        self.calls.append({"vocab": vocab, "bytes": data, "duration_ms": audio.duration_ms})
        if self.fail:
            raise self.fail
        return TranscriptionOutcome(text=self.text, model_used="fake-model", fallback_used=False,
                                    languages=None, api_ms=1)


@pytest.fixture(scope="session")
def sample_webm(tmp_path_factory):
    out = tmp_path_factory.mktemp("sample") / "s.webm"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "libopus", str(out)], check=True, capture_output=True)
    return out.read_bytes()


def split3(data: bytes):
    a, b = len(data) // 3, 2 * len(data) // 3 + 7
    return [data[:a], data[a:b], data[b:]]


@pytest.fixture
def make_client(tmp_path):
    """Factory: make_client(**setting_overrides) -> (TestClient, settings, fake)."""
    fake = FakeTranscriber()

    def _make(**overrides):
        base = SpeechSettings(whisper_key=OPENAI_KEY, tmp_dir=str(tmp_path / "speech"),
                              budget_path=str(tmp_path / "budget.json"),
                              vocabulary_path=str(tmp_path / "vocab.json"))
        (tmp_path / "vocab.json").write_text(json.dumps(
            {"prompt": "P0", "keywords": ["k0"], "languages": ["en"]}))
        settings = replace(base, **overrides)
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_transcriber] = lambda: fake
        recordings._store = RecordingStore(settings)
        _budget_store.cache_clear()
        return TestClient(app), settings, fake

    yield _make
    app.dependency_overrides.clear()
    recordings._store = None


@pytest.fixture
def client(make_client):
    return make_client()[0]


@pytest.fixture
def fake(make_client):
    return make_client()[2]


def mock_transcriber(settings, handler):
    """Real Transcriber with the OpenAI HTTP side replaced by httpx.MockTransport."""
    app.dependency_overrides[get_transcriber] = lambda: Transcriber(settings, httpx.MockTransport(handler))


def new_recording(c, mime="audio/webm"):
    r = c.post("/api/speech/recordings", json={"mime_type": mime}, headers=HEADERS)
    assert r.status_code == 201, r.text
    return r.json()["recording_id"]


def put_chunk(c, rid, idx, data, ctype="audio/webm"):
    return c.put(f"/api/speech/recordings/{rid}/chunks/{idx}", content=data,
                 headers={**HEADERS, "Content-Type": ctype})


def stop(c, rid, n=3, duration=2000, **extra):
    return c.post(f"/api/speech/recordings/{rid}/stop",
                  json={"expected_chunks": n, "client_duration_ms": duration, **extra}, headers=HEADERS)


def tmp_files(settings):
    return [p for p in os.scandir(settings.tmp_dir)]
