// platform-ui/hooks/useRecorder.ts — headless recorder state machine for the Speech API.
// One MediaRecorder runs uninterrupted with a timeslice; each dataavailable blob is one chunk.
// Never throws: failures surface through `state` and `error`.

import { useCallback, useEffect, useRef, useState } from "react";
import { isApiError } from "../api/client";
import {
  cancelRecording, createRecording, stopRecording, uploadChunk,
} from "../api/speechClient";
import type { ClientMetrics, Limits, TranscriptResult, VocabularyOverride } from "../api/speechClient";

export type RecorderState =
  "idle" | "recording" | "paused" | "uploading" | "transcribing" | "error";

export interface RecorderOptions {
  onTranscript: (result: TranscriptResult & ClientMetrics) => void;
  vocabulary?: VocabularyOverride;
  onBusyChange?: (busy: boolean) => void;
}

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
const UPLOAD_ATTEMPTS = 3;
const AUTO_STOP_MARGIN_MS = 3000; // stop slightly before the server limit so timer lag cannot exceed it

interface Session {
  id: string;
  limits: Limits;
  chunks: Blob[];
  uploaded: Set<number>;
  durationMs: number;
  stopRequestedAt: number;
  finalUploadMs: number;
}

function codeOf(res: unknown): string { return (res as any)?.error?.code ?? ""; }
function messageOf(res: unknown): string { return (res as any)?.error?.message ?? "Unexpected error."; }
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

export function useRecorder(options: RecorderOptions) {
  const [state, setState] = useState<RecorderState>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);

  const optsRef = useRef(options);
  optsRef.current = options;
  const stateRef = useRef<RecorderState>("idle");
  const sessionRef = useRef<Session | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const chainRef = useRef<Promise<void>>(Promise.resolve());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const segStartRef = useRef(0);   // when the current un-paused segment began
  const accumRef = useRef(0);      // recorded ms before the current segment (excludes pauses)

  const supportReason =
    !window.isSecureContext ? "Server dictation needs HTTPS (or localhost)."
    : !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined"
      ? "Audio recording is not supported in this browser."
    : null;

  const setSt = useCallback((s: RecorderState) => { stateRef.current = s; setState(s); }, []);
  const fail = useCallback((msg: string, retry = false) => { setError(msg); setCanRetry(retry); setSt("error"); }, [setSt]);

  const stopTimer = () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };
  const currentMs = () => accumRef.current + (segStartRef.current ? Date.now() - segStartRef.current : 0);
  const releaseMic = () => { streamRef.current?.getTracks().forEach(t => t.stop()); streamRef.current = null; };

  // Upload every chunk not yet acknowledged, sequentially, 3 attempts each. Returns the first failure.
  const uploadPending = useCallback(async (): Promise<unknown | null> => {
    const s = sessionRef.current;
    if (!s) return null;
    for (let i = 0; i < s.chunks.length; i++) {
      if (s.uploaded.has(i)) continue;
      let last: unknown = null;
      for (let attempt = 0; attempt < UPLOAD_ATTEMPTS; attempt++) {
        const res = await uploadChunk(s.id, i, s.chunks[i], abortRef.current?.signal);
        if (!isApiError(res)) { s.uploaded.add(i); last = null; break; }
        last = res;
        const c = codeOf(res);
        if (c === "UNAUTHORIZED" || c === "RECORDING_NOT_FOUND" || c === "CHUNK_CONFLICT") break;
        await sleep(500 * 3 ** attempt);
      }
      if (last) return last;
    }
    return null;
  }, []);

  const discardSession = useCallback((deleteOnServer: boolean) => {
    const s = sessionRef.current;
    sessionRef.current = null;
    if (s && deleteOnServer) void cancelRecording(s.id);
  }, []);

  // Everything after the recorder has stopped: drain uploads, ask the server for the transcript.
  const finalize = useCallback(async () => {
    const s = sessionRef.current;
    if (!s) return;
    setError(null); setCanRetry(false);
    abortRef.current = new AbortController();
    setSt("uploading");
    const t0 = s.stopRequestedAt;
    await chainRef.current;
    const upErr = await uploadPending();
    s.finalUploadMs = Date.now() - t0;
    const handle = (res: unknown): boolean => {
      const c = codeOf(res);
      if (c === "RECORDING_NOT_FOUND") { discardSession(false); fail("Recording expired on the server; please record again."); return true; }
      return false;
    };
    if (upErr) { if (!handle(upErr)) fail(messageOf(upErr), true); return; }

    setSt("transcribing");
    const payload = { expected_chunks: s.chunks.length, client_duration_ms: s.durationMs, ...optsRef.current.vocabulary };
    let res = await stopRecording(s.id, payload, abortRef.current.signal);
    if (isApiError(res) && codeOf(res) === "MISSING_CHUNKS") {
      const missing: number[] = (res as any).error?.detail?.missing ?? [];
      missing.forEach(i => s.uploaded.delete(i));
      const err2 = await uploadPending();
      if (err2) { if (!handle(err2)) fail(messageOf(err2), true); return; }
      res = await stopRecording(s.id, payload, abortRef.current.signal);
    }
    if (isApiError(res)) {
      if (handle(res)) return;
      const c = codeOf(res);
      // Audio is retained server-side only after upstream failures and for gaps; everything else ended the recording.
      const retained = c === "TRANSCRIPTION_FAILED" || c === "TRANSCRIPTION_TIMEOUT" || c === "NETWORK_ERROR" || c === "MISSING_CHUNKS";
      if (!retained) discardSession(false);
      fail(messageOf(res), retained);
      return;
    }
    const result = res as TranscriptResult;
    const stopToTranscript = Date.now() - t0;
    discardSession(false);
    setSt("idle");
    optsRef.current.onTranscript({ ...result, stop_to_transcript_ms: stopToTranscript, final_upload_ms: s.finalUploadMs });
  }, [discardSession, fail, setSt, uploadPending]);

  const start = useCallback(async () => {
    if (stateRef.current !== "idle" && stateRef.current !== "error") return;
    setError(null); setCanRetry(false);
    if (supportReason) { fail(supportReason); return; }
    const mime = MIME_CANDIDATES.find(m => MediaRecorder.isTypeSupported(m));
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      fail("Microphone permission denied."); return;
    }
    streamRef.current = stream;
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    } catch {
      releaseMic(); fail("Audio recording is not supported in this browser."); return;
    }
    const created = await createRecording(recorder.mimeType || mime || "audio/webm");
    if (isApiError(created)) {
      releaseMic();
      fail(messageOf(created));
      return;
    }
    const session: Session = {
      id: created.recording_id, limits: created.limits, chunks: [], uploaded: new Set(),
      durationMs: 0, stopRequestedAt: 0, finalUploadMs: 0,
    };
    sessionRef.current = session;
    abortRef.current = new AbortController();
    chainRef.current = Promise.resolve();

    recorder.ondataavailable = (e: BlobEvent) => {
      if (!e.data || e.data.size === 0) return;
      session.chunks.push(e.data);
      chainRef.current = chainRef.current.then(async () => { await uploadPending(); });
    };
    recorderRef.current = recorder;
    accumRef.current = 0;
    segStartRef.current = Date.now();
    recorder.start(session.limits.chunk_timeslice_ms); // once; never stopped to cut chunks
    setElapsedMs(0);
    setSt("recording");
    timerRef.current = setInterval(() => {
      const ms = currentMs();
      setElapsedMs(ms);
      if (ms >= session.limits.max_duration_s * 1000 - AUTO_STOP_MARGIN_MS) void stopRef.current();
    }, 250);
  }, [fail, setSt, supportReason, uploadPending]);

  const pause = useCallback(() => {
    const r = recorderRef.current;
    if (!r || stateRef.current !== "recording") return;
    r.requestData();
    r.pause();
    accumRef.current = currentMs();
    segStartRef.current = 0;
    setElapsedMs(accumRef.current);
    setSt("paused");
  }, [setSt]);

  const resume = useCallback(() => {
    const r = recorderRef.current;
    if (!r || stateRef.current !== "paused") return;
    r.resume();
    segStartRef.current = Date.now();
    setSt("recording");
  }, [setSt]);

  const stop = useCallback(async () => {
    const r = recorderRef.current;
    const s = sessionRef.current;
    if (!r || !s || (stateRef.current !== "recording" && stateRef.current !== "paused")) return;
    s.stopRequestedAt = Date.now();
    s.durationMs = Math.round(currentMs());
    stopTimer();
    segStartRef.current = 0;
    setSt("uploading");
    await new Promise<void>(resolve => {
      r.onstop = () => resolve();   // fires after the final dataavailable
      try { r.stop(); } catch { resolve(); }
    });
    recorderRef.current = null;
    releaseMic();
    await finalize();
  }, [finalize, setSt]);
  const stopRef = useRef(stop);
  stopRef.current = stop;

  const retry = useCallback(async () => {
    if (sessionRef.current && !recorderRef.current) await finalize();
    else await start();
  }, [finalize, start]);

  const cancel = useCallback(() => {
    stopTimer();
    const r = recorderRef.current;
    if (r) { r.ondataavailable = null; r.onstop = null; try { if (r.state !== "inactive") r.stop(); } catch { /* ignore */ } }
    recorderRef.current = null;
    releaseMic();
    abortRef.current?.abort();
    discardSession(true);
    accumRef.current = 0; segStartRef.current = 0;
    setElapsedMs(0); setError(null); setCanRetry(false);
    setSt("idle");
  }, [discardSession, setSt]);

  // Unmount cancels.
  const cancelRef = useRef(cancel);
  cancelRef.current = cancel;
  useEffect(() => () => { if (stateRef.current !== "idle") cancelRef.current(); }, []);

  const busy = state !== "idle" && state !== "error";
  useEffect(() => { optsRef.current.onBusyChange?.(busy); }, [busy]);

  return {
    state, elapsedMs, error, canRetry,
    supported: supportReason === null, unsupportedReason: supportReason,
    start, pause, resume, stop, cancel, retry,
  };
}
