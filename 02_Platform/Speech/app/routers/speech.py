"""Recording endpoints (internal_flow steps 2-10). Router prefix /api/speech; no per-user auth (Atlas perimeter); spend capped by app.budget."""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Request, Response

from app import audio as audio_mod
from app.budget import Budget, get_budget
from app.config import SpeechSettings, get_settings
from app.errors import SpeechError
from app.models import (ChunkAck, CreateRecordingRequest, CreateRecordingResponse, Limits,
                        Metrics, StopRequest, TranscriptResult)
from app.recordings import RecordingStore, get_store
from app.transcriber import Transcriber, get_transcriber
from app.vocabulary import load_defaults, resolve

log = logging.getLogger("speech")
router = APIRouter(prefix="/api/speech")


@router.post("/recordings", status_code=201, response_model=CreateRecordingResponse)
def create_recording(body: CreateRecordingRequest, store: RecordingStore = Depends(get_store),
                     settings: SpeechSettings = Depends(get_settings)):
    if not settings.whisper_key:
        raise SpeechError("SPEECH_NOT_CONFIGURED", "OpenAI key is not configured.")
    st = store.create(body.mime_type)
    return CreateRecordingResponse(recording_id=st.recording_id, limits=Limits(
        chunk_timeslice_ms=settings.chunk_timeslice_ms, max_chunk_bytes=settings.max_chunk_bytes,
        max_total_bytes=settings.max_total_bytes, max_chunks=settings.max_chunks,
        max_duration_s=settings.max_duration_s))


@router.put("/recordings/{recording_id}/chunks/{index}", response_model=ChunkAck)
async def upload_chunk(recording_id: str, index: int, request: Request,
                       store: RecordingStore = Depends(get_store)):
    return await store.write_chunk(recording_id, index, request.stream(), request.headers.get("content-type"))


@router.post("/recordings/{recording_id}/stop", response_model=TranscriptResult)
async def stop_recording(recording_id: str, body: StopRequest,
                         store: RecordingStore = Depends(get_store),
                         settings: SpeechSettings = Depends(get_settings),
                         transcriber: Transcriber = Depends(get_transcriber),
                         budget: Budget = Depends(get_budget)):
    t0 = time.perf_counter()
    chunk_paths = store.begin_finalize(recording_id, body.expected_chunks, body.client_duration_ms)
    st = store.get(recording_id)
    retain = False
    try:
        assembled = await asyncio.to_thread(
            audio_mod.assemble, chunk_paths, st.mime_type, store.dir_for(recording_id), settings)
        budget.check(assembled.duration_ms / 1000)
        vocab = resolve(load_defaults(settings.vocabulary_path), body.prompt, body.keywords, body.languages)
        retain = True  # from here any failure (upstream or unexpected) keeps the audio so stop can be retried
        outcome = await transcriber.transcribe(assembled, vocab)
        budget.record(assembled.duration_ms / 1000)
        metrics = Metrics(
            audio_duration_ms=assembled.duration_ms, client_duration_ms=body.client_duration_ms,
            duration_delta_ms=assembled.duration_ms - body.client_duration_ms,
            chunk_count=len(chunk_paths), total_bytes=st.total_bytes, upload_ms=st.upload_ms,
            assemble_ms=assembled.assemble_ms, api_ms=outcome.api_ms,
            server_total_ms=int((time.perf_counter() - t0) * 1000))
        log.info("transcribed id=%s model=%s fallback=%s metrics=%s", recording_id, outcome.model_used,
                 outcome.fallback_used, metrics.model_dump_json())  # never the transcript text
        result = TranscriptResult(recording_id=recording_id, transcript=outcome.text,
                                  model_used=outcome.model_used, fallback_used=outcome.fallback_used,
                                  languages=outcome.languages, metrics=metrics)
        retain = False
        return result
    finally:
        store.end_finalize(recording_id, retain=retain)


@router.delete("/recordings/{recording_id}", status_code=204)
def cancel_recording(recording_id: str, store: RecordingStore = Depends(get_store)):
    store.cancel(recording_id)
    return Response(status_code=204)
