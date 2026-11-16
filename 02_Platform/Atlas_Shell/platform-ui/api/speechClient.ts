// platform-ui/api/speechClient.ts — browser-side wrapper for the Speech platform API.
// Every call goes through apiFetch (which prefixes /api).
// Backend contract: 02_Platform/Speech/Sprint01_SpeechMVP/10_scaffolding.json (app/models.py).

import { apiFetch } from "./client";
import type { ApiError } from "./types";

export interface Limits {
  chunk_timeslice_ms: number;
  max_chunk_bytes:    number;
  max_total_bytes:    number;
  max_chunks:         number;
  max_duration_s:     number;
}
export interface CreateRecordingResponse { recording_id: string; limits: Limits }
export interface ChunkAck { recording_id: string; index: number; chunks_received: number; total_bytes: number }

export interface VocabularyOverride { prompt?: string; keywords?: string[]; languages?: string[] }
export interface StopPayload extends VocabularyOverride { expected_chunks: number; client_duration_ms: number }

export interface Metrics {
  audio_duration_ms: number; client_duration_ms: number; duration_delta_ms: number;
  chunk_count: number; total_bytes: number; upload_ms: number; assemble_ms: number;
  api_ms: number; server_total_ms: number;
}
export interface TranscriptResult {
  recording_id: string; transcript: string; model_used: string; fallback_used: boolean;
  languages: string[] | null; metrics: Metrics;
}
export interface ClientMetrics { stop_to_transcript_ms: number; final_upload_ms: number }

// ── API ────────────────────────────────────────────────────────────────────

export function createRecording(mimeType: string): Promise<CreateRecordingResponse | ApiError> {
  return apiFetch<CreateRecordingResponse>("/speech/recordings", {
    method: "POST", body: JSON.stringify({ mime_type: mimeType }),
  });
}

export function uploadChunk(recordingId: string, index: number, blob: Blob, signal?: AbortSignal): Promise<ChunkAck | ApiError> {
  return apiFetch<ChunkAck>(`/speech/recordings/${recordingId}/chunks/${index}`, {
    method: "PUT", headers: { "Content-Type": blob.type || "application/octet-stream" },
    body: blob, signal,
  });
}

export function stopRecording(recordingId: string, payload: StopPayload, signal?: AbortSignal): Promise<TranscriptResult | ApiError> {
  return apiFetch<TranscriptResult>(`/speech/recordings/${recordingId}/stop`, {
    method: "POST", body: JSON.stringify(payload), signal,
  });
}

// Best effort: the backend answers 204 (empty body); the result is ignored on purpose.
export async function cancelRecording(recordingId: string): Promise<void> {
  try {
    await apiFetch(`/speech/recordings/${recordingId}`, { method: "DELETE" });
  } catch { /* ignore */ }
}
