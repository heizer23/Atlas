"""Request/response records (typed-record contract; no Dataset)."""

from typing import Optional
from pydantic import BaseModel, Field


class CreateRecordingRequest(BaseModel):
    mime_type: str


class Limits(BaseModel):
    chunk_timeslice_ms: int
    max_chunk_bytes: int
    max_total_bytes: int
    max_chunks: int
    max_duration_s: int


class CreateRecordingResponse(BaseModel):
    recording_id: str
    limits: Limits


class ChunkAck(BaseModel):
    recording_id: str
    index: int
    chunks_received: int
    total_bytes: int


class StopRequest(BaseModel):
    expected_chunks: int = Field(ge=1)
    client_duration_ms: int = Field(ge=0)
    prompt: Optional[str] = None
    keywords: Optional[list[str]] = None
    languages: Optional[list[str]] = None


class Metrics(BaseModel):
    audio_duration_ms: int
    client_duration_ms: int
    duration_delta_ms: int
    chunk_count: int
    total_bytes: int
    upload_ms: int
    assemble_ms: int
    api_ms: int
    server_total_ms: int


class TranscriptResult(BaseModel):
    recording_id: str
    transcript: str
    model_used: str
    fallback_used: bool
    languages: Optional[list[str]] = None
    metrics: Metrics
