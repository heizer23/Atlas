import logging
import time

import httpx

from app.errors import SpeechError
import app.recordings as recordings
from tests.conftest import (HEADERS, OPENAI_KEY, mock_transcriber, new_recording, put_chunk,
                            split3, stop, tmp_files)

EBML = bytes.fromhex("1a45dfa3")


def upload_all(c, rid, sample, order=(0, 1, 2)):
    parts = split3(sample)
    for i in order:
        assert put_chunk(c, rid, i, parts[i]).status_code == 200


def test_happy_path_chunks_reassemble_and_transcribe(make_client, sample_webm):
    c, s, fake = make_client()
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"] == "hello world" and body["model_used"] == "fake-model"
    m = body["metrics"]
    assert m["chunk_count"] == 3 and m["audio_duration_ms"] > 0 and m["total_bytes"] == len(sample_webm)
    assert fake.calls[0]["bytes"].startswith(EBML)  # remuxed (not byte-identical) valid webm
    assert 1500 < fake.calls[0]["duration_ms"] < 2600
    assert tmp_files(s) == []


def test_out_of_order_arrival_is_reassembled_by_index(make_client, sample_webm):
    c, s, fake = make_client()
    rid = new_recording(c)
    upload_all(c, rid, sample_webm, order=(2, 0, 1))
    assert stop(c, rid).status_code == 200
    rid2 = new_recording(c)
    upload_all(c, rid2, sample_webm)
    assert stop(c, rid2).status_code == 200
    assert abs(fake.calls[0]["duration_ms"] - fake.calls[1]["duration_ms"]) < 50


def test_duplicate_chunk_upload_is_idempotent(client, sample_webm):
    rid = new_recording(client)
    parts = split3(sample_webm)
    first = put_chunk(client, rid, 0, parts[0]).json()
    again = put_chunk(client, rid, 0, parts[0]).json()
    assert again["total_bytes"] == first["total_bytes"] and again["chunks_received"] == 1
    r = put_chunk(client, rid, 0, parts[0] + b"x")
    assert r.status_code == 409 and r.json()["error"]["code"] == "CHUNK_CONFLICT"


def test_gap_is_rejected_and_recoverable(make_client, sample_webm):
    c, s, fake = make_client()
    rid = new_recording(c)
    parts = split3(sample_webm)
    put_chunk(c, rid, 0, parts[0])
    put_chunk(c, rid, 2, parts[2])
    r = stop(c, rid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "MISSING_CHUNKS"
    assert r.json()["error"]["detail"]["missing"] == [1]
    assert fake.calls == []
    put_chunk(c, rid, 1, parts[1])
    assert stop(c, rid).status_code == 200


def test_cancel_discards_audio(make_client, sample_webm):
    c, s, fake = make_client()
    rid = new_recording(c)
    parts = split3(sample_webm)
    put_chunk(c, rid, 0, parts[0])
    put_chunk(c, rid, 1, parts[1])
    assert c.delete(f"/api/speech/recordings/{rid}", headers=HEADERS).status_code == 204
    assert c.delete(f"/api/speech/recordings/{rid}", headers=HEADERS).status_code == 204
    assert put_chunk(c, rid, 2, parts[2]).json()["error"]["code"] == "RECORDING_NOT_FOUND"
    assert stop(c, rid).json()["error"]["code"] == "RECORDING_NOT_FOUND"
    assert tmp_files(s) == [] and fake.calls == []


def test_cancel_of_unknown_id_succeeds(client):
    r = client.delete("/api/speech/recordings/nope", headers=HEADERS)
    assert r.status_code == 204


def test_unset_openai_key_is_speech_not_configured(make_client):
    c, _, _ = make_client(whisper_key="")
    r = c.post("/api/speech/recordings", json={"mime_type": "audio/webm"}, headers=HEADERS)
    assert r.status_code == 503 and r.json()["error"]["code"] == "SPEECH_NOT_CONFIGURED"


def test_daily_audio_budget_blocks_before_openai_call(make_client, sample_webm):
    c, s, fake = make_client(daily_audio_s=3)  # sample is 2 s: first fits, second would exceed
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    assert stop(c, rid).status_code == 200
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 429 and r.json()["error"]["code"] == "BUDGET_EXCEEDED"
    assert len(fake.calls) == 1
    assert tmp_files(s) == []


def test_hourly_transcription_limit(make_client, sample_webm):
    c, _, fake = make_client(hourly_transcriptions=1)
    for expected in (200, 429):
        rid = new_recording(c)
        upload_all(c, rid, sample_webm)
        assert stop(c, rid).status_code == expected
    assert len(fake.calls) == 1


def test_budget_survives_restart(make_client, sample_webm):
    c, s, _ = make_client(hourly_transcriptions=1)
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    assert stop(c, rid).status_code == 200
    from app.budget import _store
    _store.cache_clear()  # simulates a new process reading the persisted file
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    assert stop(c, rid).status_code == 429


def test_health_needs_no_token(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_unsupported_audio_type(client):
    r = client.post("/api/speech/recordings", json={"mime_type": "text/plain"}, headers=HEADERS)
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_MIME"


def test_oversized_chunk(make_client):
    c, _, _ = make_client(max_chunk_bytes=2048)
    rid = new_recording(c)
    r = put_chunk(c, rid, 0, b"x" * 5000)
    assert r.status_code == 413 and r.json()["error"]["code"] == "CHUNK_TOO_LARGE"
    assert put_chunk(c, rid, 0, b"x" * 100).status_code == 200


def test_too_many_chunks_and_too_many_bytes(make_client):
    c, s, _ = make_client(max_chunks=3, max_total_bytes=1500)
    rid = new_recording(c)
    r = put_chunk(c, rid, 3, b"x")
    assert r.status_code == 413 and r.json()["error"]["code"] == "TOO_MANY_CHUNKS"
    put_chunk(c, rid, 0, b"x" * 1000)
    r = put_chunk(c, rid, 1, b"x" * 1000)
    assert r.status_code == 413 and r.json()["error"]["code"] == "RECORDING_TOO_LARGE"
    assert tmp_files(s) == []
    assert put_chunk(c, rid, 2, b"x").json()["error"]["code"] == "RECORDING_NOT_FOUND"


def test_chunk_index_invalid(client):
    rid = new_recording(client)
    r = put_chunk(client, rid, -1, b"x")
    assert r.status_code == 400 and r.json()["error"]["code"] == "CHUNK_INDEX_INVALID"


def test_expected_chunks_above_max_is_rejected(make_client):
    c, _, _ = make_client(max_chunks=5)
    rid = new_recording(c)
    r = stop(c, rid, n=1_000_000)
    assert r.status_code == 400 and r.json()["error"]["code"] == "CHUNK_INDEX_INVALID"


def test_too_many_concurrent_recordings(make_client):
    c, _, _ = make_client(max_active_recordings=2)
    a = new_recording(c)
    new_recording(c)
    r = c.post("/api/speech/recordings", json={"mime_type": "audio/webm"}, headers=HEADERS)
    assert r.status_code == 429 and r.json()["error"]["code"] == "TOO_MANY_RECORDINGS"
    c.delete(f"/api/speech/recordings/{a}", headers=HEADERS)
    new_recording(c)


def test_recording_busy_while_finalizing(make_client, sample_webm):
    c, s, _ = make_client()
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    recordings._store.get(rid).status = "finalizing"  # a stop is in flight
    r = stop(c, rid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RECORDING_BUSY"
    assert put_chunk(c, rid, 0, b"x").json()["error"]["code"] == "RECORDING_BUSY"


def test_over_long_recording(make_client, sample_webm):
    c, s, fake = make_client(max_duration_s=1)
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid, duration=900)  # client claims short; measured duration is 2 s
    assert r.status_code == 413 and r.json()["error"]["code"] == "RECORDING_TOO_LONG"
    assert fake.calls == [] and tmp_files(s) == []


def test_undecodable_audio(make_client):
    c, s, fake = make_client()
    rid = new_recording(c)
    for i in range(3):
        put_chunk(c, rid, i, bytes(range(256)) * 4)
    r = stop(c, rid)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_AUDIO"
    assert fake.calls == [] and tmp_files(s) == []


def test_vocabulary_defaults_and_per_request_override(make_client, sample_webm):
    c, s, fake = make_client()

    def run(**extra):
        rid = new_recording(c)
        upload_all(c, rid, sample_webm)
        assert stop(c, rid, **extra).status_code == 200
        return fake.calls[-1]["vocab"]

    v = run()
    assert (v.prompt, v.keywords, v.languages) == ("P0", ["k0"], ["en"])
    v = run(keywords=["k1", "k2"])
    assert (v.prompt, v.keywords, v.languages) == ("P0", ["k1", "k2"], ["en"])
    v = run(languages=[], prompt="")
    assert (v.prompt, v.keywords, v.languages) == ("", ["k0"], [])


def _body_text(req: httpx.Request) -> bytes:
    return req.read()


def test_fallback_model_mapping(make_client, sample_webm):
    c, s, _ = make_client()
    seen = []

    def handler(req):
        body = _body_text(req)
        seen.append(body)
        if b"gpt-transcribe" in body:
            return httpx.Response(400, json={"error": {"message": "unknown model"}})
        return httpx.Response(200, json={"text": "ok"})

    mock_transcriber(s, handler)
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid, keywords=["k1"])
    assert r.status_code == 200
    assert r.json()["model_used"] == "gpt-4o-transcribe" and r.json()["fallback_used"] is True
    fb = seen[1]
    assert b'name="keywords"' not in fb and b"k1" in fb and b'name="prompt"' in fb


def test_upstream_failure_retains_audio_for_retry(make_client, sample_webm):
    c, s, _ = make_client()
    state = {"fail": True}

    def handler(req):
        return httpx.Response(500) if state["fail"] else httpx.Response(200, json={"text": "later"})

    mock_transcriber(s, handler)
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 502 and r.json()["error"]["code"] == "TRANSCRIPTION_FAILED"
    assert tmp_files(s) != []
    state["fail"] = False
    r = stop(c, rid)
    assert r.status_code == 200 and r.json()["transcript"] == "later"
    assert tmp_files(s) == []


def test_upstream_timeout(make_client, sample_webm):
    c, s, _ = make_client()

    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    mock_transcriber(s, handler)
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 504 and r.json()["error"]["code"] == "TRANSCRIPTION_TIMEOUT"
    assert tmp_files(s) != []


def test_silence_yields_empty_successful_transcript(make_client, sample_webm):
    c, s, _ = make_client()
    mock_transcriber(s, lambda req: httpx.Response(200, json={"text": ""}))
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 200 and r.json()["transcript"] == ""


def test_idle_recordings_are_reaped(make_client):
    c, s, _ = make_client(idle_ttl_s=10)
    rid = new_recording(c)
    put_chunk(c, rid, 0, b"abc")
    assert recordings._store.reap_idle(time.time() + 11) == 1
    assert tmp_files(s) == []
    assert put_chunk(c, rid, 1, b"abc").json()["error"]["code"] == "RECORDING_NOT_FOUND"


def test_startup_sweep(make_client):
    c, s, _ = make_client()
    rid = new_recording(c)
    put_chunk(c, rid, 0, b"abc")
    assert tmp_files(s) != []
    recordings.RecordingStore(s)
    assert tmp_files(s) == []


def test_secrets_never_leak(make_client, sample_webm, caplog):
    c, s, _ = make_client()
    caplog.set_level(logging.DEBUG)
    outputs = []
    mock_transcriber(s, lambda req: httpx.Response(200, json={"text": "SECRET TRANSCRIPT"}))
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    outputs.append(stop(c, rid).text)
    mock_transcriber(s, lambda req: httpx.Response(500, text=f"boom {OPENAI_KEY}"))
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    outputs.append(stop(c, rid).text)
    c.post("/api/speech/recordings", json={"mime_type": "audio/webm"})
    blob = "\n".join(outputs) + caplog.text
    assert OPENAI_KEY not in blob
    assert "SECRET TRANSCRIPT" not in caplog.text


def test_object_style_languages_are_normalized(make_client, sample_webm):
    c, s, _ = make_client()
    mock_transcriber(s, lambda req: httpx.Response(200, json={"text": "hi", "languages": [{"code": "en"}]}))
    rid = new_recording(c)
    upload_all(c, rid, sample_webm)
    r = stop(c, rid)
    assert r.status_code == 200 and r.json()["languages"] == ["en"]
    assert tmp_files(s) == []
