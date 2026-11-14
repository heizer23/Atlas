// platform-ui/components/RecorderButton.tsx — mic control over useRecorder (server-side transcription).
// The component never inserts or submits anything: the consumer decides what onTranscript does.

import React, { useState } from "react";
import { useRecorder } from "../hooks/useRecorder";
import type { ClientMetrics, TranscriptResult, VocabularyOverride } from "../api/speechClient";

interface Props {
  onTranscript: (text: string, result: TranscriptResult & ClientMetrics) => void;
  vocabulary?: VocabularyOverride;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
}

const btn: React.CSSProperties = {
  padding: "8px 12px", borderRadius: 6, border: "1px solid #ccc", fontSize: 14, cursor: "pointer",
  background: "transparent", color: "inherit",
};
const small: React.CSSProperties = { fontSize: 12, color: "var(--md-sys-color-on-surface-variant)" };

function mmss(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function RecorderButton({ onTranscript, vocabulary, disabled, onBusyChange }: Props) {
  const [notice, setNotice] = useState<string | null>(null);

  const rec = useRecorder({
    vocabulary,
    onBusyChange,
    onTranscript: (result) => {
      console.info("[speech] metrics", result.metrics, {
        stop_to_transcript_ms: result.stop_to_transcript_ms, final_upload_ms: result.final_upload_ms,
      });
      if (!result.transcript.trim()) { setNotice("No speech detected."); return; }
      setNotice(null);
      onTranscript(result.transcript, result);
    },
  });

  const active = rec.state === "recording" || rec.state === "paused";
  const working = rec.state === "uploading" || rec.state === "transcribing";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <button
          onClick={() => { setNotice(null); void (active ? rec.stop() : rec.start()); }}
          disabled={disabled || working || !rec.supported}
          title={rec.unsupportedReason ?? (active ? "Stop and transcribe" : "Dictate (server transcription)")}
          style={{
            ...btn,
            background: active ? "var(--md-sys-color-error)" : "transparent",
            color: active ? "#fff" : "inherit",
            opacity: rec.supported ? 1 : 0.4,
          }}
        >
          {active ? "⏹" : "🎙️"}
        </button>
        {active && (
          <>
            <button onClick={rec.state === "paused" ? rec.resume : rec.pause} style={btn}
                    title={rec.state === "paused" ? "Resume" : "Pause"}>
              {rec.state === "paused" ? "▶" : "⏸"}
            </button>
            <button onClick={rec.cancel} style={btn} title="Cancel and discard">✕</button>
          </>
        )}
        {(active || working) && (
          <span style={small}>
            {working ? (rec.state === "uploading" ? "Uploading…" : "Transcribing…") : mmss(rec.elapsedMs)}
            {rec.state === "paused" ? " (paused)" : ""}
          </span>
        )}
        {working && <button onClick={rec.cancel} style={btn} title="Cancel">✕</button>}
      </div>

      {rec.error && (
        <div style={{ color: "var(--md-sys-color-error)", fontSize: 12 }}>
          {rec.error}
          {rec.canRetry && <button onClick={() => void rec.retry()} style={{ ...btn, marginLeft: 6, padding: "2px 8px", fontSize: 12 }}>Retry</button>}
          {rec.state === "error" && <button onClick={rec.cancel} style={{ ...btn, marginLeft: 6, padding: "2px 8px", fontSize: 12 }}>Dismiss</button>}
        </div>
      )}
      {notice && <div style={small}>{notice}</div>}
    </div>
  );
}
