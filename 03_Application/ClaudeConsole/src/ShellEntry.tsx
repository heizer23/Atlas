/**
 * ClaudeConsole ShellEntry — Sprint 01
 *
 * Single view: a chat window driving one headless Claude Code session.
 * REST reads/mutations go through the shared apiFetch client. The chat
 * socket uses the native WebSocket API directly — apiFetch is REST-only,
 * so this is an intentional, singular exception to "no raw fetch," not a
 * pattern to spread elsewhere. See backend/ws.py for the server side.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface SessionRow extends Row {
  id: string;
  permission_mode: string;
  status: string;
  created_at: string;
}

interface MessageRow extends Row {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_detail: string | null;
  created_at: string;
}

interface AppDataset<T> {
  meta: { object_type: string; total: number };
  rows: T[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PERMISSION_MODES = ['plan', 'acceptEdits', 'bypassPermissions'] as const;

const PERMISSION_LABELS: Record<string, string> = {
  plan:               'Plan (no side effects)',
  acceptEdits:        'Accept Edits (default)',
  bypassPermissions:  'Bypass Permissions (no safety checks)',
};

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/claudeconsole/ws`;
}

// Browser-native dictation (Web Speech API) — no backend involved. Chrome's
// implementation only exposes the vendor-prefixed constructor.
function getSpeechRecognitionCtor(): any {
  return (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition ?? null;
}

function extractText(event: any): string | null {
  if (typeof event?.text === 'string') return event.text;
  const content = event?.message?.content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    const parts = content.filter((c: any) => c?.type === 'text').map((c: any) => c.text ?? '');
    if (parts.length) return parts.join('');
  }
  return null;
}

// Events that carry no chat-relevant content of their own (session bookkeeping,
// rate-limit telemetry, the turn-complete marker) — never rendered as a bubble.
const SILENT_EVENT_TYPES = new Set(['system', 'rate_limit_event', 'result']);

function parseEvent(row: MessageRow): any | null {
  if (!row.tool_detail) return null;
  try { return JSON.parse(row.tool_detail); } catch { return null; }
}

function summarizeToolUse(block: any): string {
  const name = block.name ?? 'Tool';
  const input = block.input ?? {};
  if (typeof input.command === 'string') return `${name}: ${input.command}`;
  if (typeof input.file_path === 'string') return `${name}: ${input.file_path}`;
  if (typeof input.pattern === 'string') return `${name}: ${input.pattern}`;
  const keys = Object.keys(input);
  return keys.length ? `${name}(${keys[0]}: ${JSON.stringify(input[keys[0]]).slice(0, 60)})` : name;
}

function toolResultText(block: any): string {
  const content = block.content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.filter((c: any) => c?.type === 'text').map((c: any) => c.text ?? '').join('\n');
  }
  return JSON.stringify(content, null, 2);
}

// A single stream-json event can hold several distinct pieces (a tool call
// alongside text, in principle) — this expands one message row into zero or
// more render entries instead of assuming a 1:1 row-to-bubble mapping.
type RenderEntry =
  | { kind: 'bubble'; key: string; role: 'user' | 'assistant'; content: string }
  | { kind: 'tool_call'; key: string; summary: string; input: any }
  | { kind: 'tool_result'; key: string; isError: boolean; text: string };

function toRenderEntries(row: MessageRow): RenderEntry[] {
  const event = parseEvent(row);
  const etype = event?.type;
  if (etype && SILENT_EVENT_TYPES.has(etype)) return [];

  const content = event?.message?.content;
  if (Array.isArray(content)) {
    const entries: RenderEntry[] = [];
    content.forEach((block: any, i: number) => {
      if (block?.type === 'text' && block.text) {
        entries.push({ kind: 'bubble', key: `${row.id}-${i}`, role: row.role === 'user' ? 'user' : 'assistant', content: block.text });
      } else if (block?.type === 'tool_use') {
        entries.push({ kind: 'tool_call', key: `${row.id}-${i}`, summary: summarizeToolUse(block), input: block.input ?? {} });
      } else if (block?.type === 'tool_result') {
        entries.push({ kind: 'tool_result', key: `${row.id}-${i}`, isError: block.is_error === true, text: toolResultText(block) });
      }
      // 'thinking' blocks are intentionally not rendered — internal reasoning, not chat content.
    });
    if (entries.length) return entries;
  }

  // Rows with no parseable raw event (fixtures, or events extractText already
  // handled) fall back to the persisted plain-text content.
  if (row.content) {
    return [{ kind: 'bubble', key: row.id, role: row.role === 'user' ? 'user' : 'assistant', content: row.content }];
  }
  return [];
}

// ── Start-session panel ───────────────────────────────────────────────────────

function StartSessionPanel({ onStarted }: { onStarted: () => void }) {
  const [mode, setMode]           = useState<string>('acceptEdits');
  const [confirming, setConfirming] = useState(false);
  const [starting, setStarting]   = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const doStart = async () => {
    setStarting(true);
    setError(null);
    const res = await apiFetch('/claudeconsole/session', {
      method: 'POST',
      body: JSON.stringify({ permission_mode: mode }),
    });
    setStarting(false);
    if (isApiError(res)) {
      setError((res as ApiError).error.message);
      return;
    }
    onStarted();
  };

  const handleStartClick = () => {
    if (mode === 'bypassPermissions' && !confirming) {
      setConfirming(true);
      return;
    }
    doStart();
  };

  return (
    <div style={{ padding: 24, maxWidth: 480 }}>
      <h2 style={{ marginTop: 0 }}>Start a Console session</h2>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, fontWeight: 500, marginBottom: 16 }}>
        Permission mode
        <select
          value={mode}
          onChange={e => { setMode(e.target.value); setConfirming(false); }}
          style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #ccc', fontSize: 14 }}
        >
          {PERMISSION_MODES.map(m => <option key={m} value={m}>{PERMISSION_LABELS[m]}</option>)}
        </select>
      </label>

      {confirming && (
        <div style={{
          padding: 12, borderRadius: 8, marginBottom: 16,
          background: '#fef2f2', border: '1px solid var(--md-sys-color-error)', fontSize: 13,
        }}>
          <strong>Bypass Permissions</strong> skips all of Claude Code's safety checks for this
          session — every tool call runs without approval. Click Start again to confirm.
        </div>
      )}

      {error && <ErrorCard message={error} />}

      <button
        onClick={handleStartClick}
        disabled={starting}
        style={{
          padding: '8px 16px', borderRadius: 6, border: 'none',
          background: 'var(--md-sys-color-primary)', color: '#fff', cursor: 'pointer', fontSize: 14,
        }}
      >
        {starting ? 'Starting…' : confirming ? 'Confirm Start' : 'Start Session'}
      </button>
    </div>
  );
}

// ── Chat bubble ───────────────────────────────────────────────────────────────

function MessageBubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  const isUser = role === 'user';
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
      <div style={{
        maxWidth:     '75%',
        padding:      '8px 12px',
        borderRadius: 12,
        background:   isUser ? 'var(--md-sys-color-primary-container)' : 'var(--md-sys-color-surface-variant)',
        color:        isUser ? 'var(--md-sys-color-on-primary-container, inherit)' : 'var(--md-sys-color-on-surface-variant)',
        fontSize:     14,
        whiteSpace:   'pre-wrap',
      }}>
        {content}
      </div>
    </div>
  );
}

const detailCardStyle: React.CSSProperties = {
  fontSize: 12, margin: '4px 0 10px', maxWidth: '85%',
};

const detailBodyStyle: React.CSSProperties = {
  whiteSpace: 'pre-wrap', fontSize: 11, background: 'var(--md-sys-color-surface-variant)',
  color: 'var(--md-sys-color-on-surface-variant)', padding: 8, borderRadius: 6, marginTop: 4,
  maxHeight: 240, overflowY: 'auto',
};

function ToolCallCard({ summary, input }: { summary: string; input: any }) {
  const short = summary.length > 100 ? summary.slice(0, 100) + '…' : summary;
  return (
    <details style={detailCardStyle}>
      <summary style={{ cursor: 'pointer', opacity: 0.75 }}>🔧 {short}</summary>
      <pre style={detailBodyStyle}>{JSON.stringify(input, null, 2)}</pre>
    </details>
  );
}

function ToolResultCard({ isError, text }: { isError: boolean; text: string }) {
  return (
    <details style={detailCardStyle}>
      <summary style={{ cursor: 'pointer', opacity: 0.75, color: isError ? 'var(--md-sys-color-error)' : undefined }}>
        {isError ? '⚠️ Tool error' : '✓ Tool result'}
      </summary>
      <pre style={detailBodyStyle}>{text}</pre>
    </details>
  );
}

function ChatEntry({ entry }: { entry: RenderEntry }) {
  if (entry.kind === 'bubble') return <MessageBubble role={entry.role} content={entry.content} />;
  if (entry.kind === 'tool_call') return <ToolCallCard summary={entry.summary} input={entry.input} />;
  return <ToolResultCard isError={entry.isError} text={entry.text} />;
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function ClaudeConsoleApp() {
  const [session, setSession]         = useState<SessionRow | null>(null);
  const [loadingSession, setLoading]  = useState(true);
  const [messages, setMessages]       = useState<MessageRow[]>([]);
  const [liveMessages, setLiveMessages] = useState<MessageRow[]>([]);
  const [turnActive, setTurnActive]   = useState(false);
  const [input, setInput]             = useState('');
  const [wsError, setWsError]         = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [listening, setListening]     = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const wsRef         = useRef<WebSocket | null>(null);
  const scrollRef     = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const dictationBaseRef = useRef('');  // input text as it stood when dictation started
  const listeningRef = useRef(false);   // mirrors `listening` for use inside recognition callbacks

  const speechCtor = getSpeechRecognitionCtor();
  const speechApiPresent = !!speechCtor;
  const secureContext = window.isSecureContext;
  const speechSupported = speechApiPresent && secureContext;
  const speechDisabledReason = !secureContext
    ? 'Voice input needs HTTPS (or localhost) — this page is loaded over plain HTTP.'
    : !speechApiPresent
      ? 'Voice input is not supported in this browser.'
      : null;

  const loadSession = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch('/claudeconsole/session');
    setLoading(false);
    if (isApiError(res)) return;
    const rows = (res as AppDataset<SessionRow>).rows;
    setSession(rows[0] ?? null);
  }, []);

  const loadMessages = useCallback(async () => {
    const res = await apiFetch('/claudeconsole/session/messages');
    if (isApiError(res)) return;
    setMessages((res as AppDataset<MessageRow>).rows ?? []);
    setLiveMessages([]);
  }, []);

  useEffect(() => { loadSession(); }, [loadSession]);
  useEffect(() => { if (session) loadMessages(); }, [session, loadMessages]);

  // One WebSocket connection per active session, with auto-reconnect.
  // Any unexpected close (container restart, network blip, a server-side
  // crash) previously left wsRef.current null forever with no visible
  // sign — Send would just silently no-op. Now it retries on a short delay
  // and surfaces connection state so that's never silent again.
  useEffect(() => {
    if (!session) return;
    let stopped = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);

      ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.type === 'error') {
          setWsError(data.message ?? data.code);
          if (data.code !== 'ALREADY_CONNECTED') setTurnActive(false);
          return;
        }
        const text = extractText(data);
        setLiveMessages(prev => [...prev, {
          id:          `live-${prev.length}-${Date.now()}`,
          role:        data.type === 'user' ? 'user' : 'assistant',
          content:     text,
          tool_detail: JSON.stringify(data),
          created_at:  new Date().toISOString(),
        }]);
        if (data.type === 'result') {
          setTurnActive(false);
          // Reload from the DB-backed Dataset once the turn is done — this is
          // the authoritative transcript; liveMessages was a best-effort
          // real-time preview built on an unverified event schema.
          loadMessages();
        }
      };

      ws.onclose = (evt) => {
        wsRef.current = null;
        setWsConnected(false);
        if (stopped) return;
        // 4409 = another tab already owns this session's single connection;
        // retrying would just loop against the same rejection.
        if (evt.code === 4409) return;
        setTurnActive(false);
        retryTimer = setTimeout(connect, 2000);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [session, loadMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, liveMessages]);

  // Stop any live dictation on unmount so the mic doesn't stay hot.
  useEffect(() => () => {
    listeningRef.current = false;
    recognitionRef.current?.stop();
  }, []);

  const stopListening = useCallback(() => {
    listeningRef.current = false;
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setListening(false);
  }, []);

  // `continuous: true` on mobile Chrome is unreliable — it silently restarts
  // internal recognition segments and, on Android in particular, replays
  // already-finalized text as "new" final results, producing duplicated
  // words/phrases. This runs one single-utterance (continuous: false)
  // session at a time and chains a fresh one on `onend` for as long as the
  // user hasn't tapped stop — same effect (dictate across pauses) without
  // relying on the browser's buggy continuous mode.
  const runSegment = useCallback((speechCtorRef: any) => {
    const recognition = new speechCtorRef();
    recognition.lang = navigator.language || 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onresult = (event: any) => {
      let finalChunk = '';
      let interimChunk = '';
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) finalChunk += result[0].transcript;
        else interimChunk += result[0].transcript;
      }
      if (finalChunk) {
        dictationBaseRef.current = `${dictationBaseRef.current} ${finalChunk}`.trim();
      }
      setInput(`${dictationBaseRef.current} ${interimChunk}`.trim());
    };
    recognition.onerror = (event: any) => {
      // 'no-speech' just means this segment's silence timeout was hit —
      // onend follows and, since we're still "listening", starts a fresh
      // segment. Not a real failure.
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      setSpeechError(
        event.error === 'not-allowed' || event.error === 'permission-denied'
          ? 'Microphone permission denied.'
          : `Voice input error: ${event.error}`
      );
      listeningRef.current = false;
      setListening(false);
    };
    recognition.onend = () => {
      if (listeningRef.current) runSegment(speechCtorRef);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, []);

  const startListening = useCallback(() => {
    if (!speechCtor || listeningRef.current) return;
    dictationBaseRef.current = input.trim();
    setSpeechError(null);
    listeningRef.current = true;
    setListening(true);
    runSegment(speechCtor);
  }, [speechCtor, input, runSegment]);

  const handleSend = () => {
    const prompt = input.trim();
    if (!prompt || !wsRef.current || !wsConnected || turnActive) return;
    if (listening) stopListening();
    wsRef.current.send(JSON.stringify({ prompt }));
    setInput('');
    setTurnActive(true);
    setWsError(null);
  };

  const handleInterrupt = async () => {
    await apiFetch('/claudeconsole/session/interrupt', { method: 'POST' });
    setTurnActive(false);
  };

  const handleNewSession = () => {
    if (!confirm('Start a new session? The current one will end (history stays browsable via its own record, just not resumable).')) return;
    wsRef.current?.close();
    setSession(null);
    setMessages([]);
    setLiveMessages([]);
    setTurnActive(false);
  };

  if (loadingSession) return <div style={{ padding: 16 }}><Skeleton /></div>;

  if (!session) {
    return <StartSessionPanel onStarted={loadSession} />;
  }

  const allMessages = [...messages, ...liveMessages];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>
          Session mode: <strong>{PERMISSION_LABELS[session.permission_mode] ?? session.permission_mode}</strong>
        </div>
        <button
          onClick={handleNewSession}
          style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #ccc', background: 'transparent', cursor: 'pointer', fontSize: 12 }}
        >
          New Session
        </button>
      </div>

      <div
        ref={scrollRef}
        style={{
          flex: 1, overflowY: 'auto', border: '1px solid #e0e0e0', borderRadius: 8,
          padding: 12, marginBottom: 8, background: 'var(--md-sys-color-surface)',
        }}
      >
        {allMessages.length === 0 && <div style={{ color: '#888', fontSize: 14 }}>No messages yet — say hello.</div>}
        {allMessages.flatMap(toRenderEntries).map(entry => <ChatEntry key={entry.key} entry={entry} />)}
      </div>

      {wsError && <div style={{ color: 'var(--md-sys-color-error)', fontSize: 13, marginBottom: 8 }}>{wsError}</div>}
      {speechError && <div style={{ color: 'var(--md-sys-color-error)', fontSize: 13, marginBottom: 8 }}>{speechError}</div>}
      {!wsConnected && (
        <div style={{ color: 'var(--md-sys-color-error)', fontSize: 13, marginBottom: 8 }}>
          Disconnected — reconnecting…
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          placeholder={!wsConnected ? 'Reconnecting…' : listening ? 'Listening…' : 'Message Claude Code…'}
          disabled={turnActive || !wsConnected}
          style={{ flex: 1, padding: '8px 12px', borderRadius: 6, border: '1px solid #ccc', fontSize: 14 }}
        />
        <button
          onClick={listening ? stopListening : startListening}
          disabled={!speechSupported || turnActive}
          title={speechDisabledReason ?? (listening ? 'Stop dictation' : 'Start dictation')}
          style={{
            padding: '8px 12px', borderRadius: 6, border: '1px solid #ccc', fontSize: 16, cursor: 'pointer',
            background: listening ? 'var(--md-sys-color-error)' : 'transparent',
            color: listening ? '#fff' : 'inherit',
            opacity: speechSupported ? 1 : 0.4,
          }}
        >
          🎤
        </button>
        {turnActive ? (
          <button
            onClick={handleInterrupt}
            style={{ padding: '8px 16px', borderRadius: 6, border: 'none', background: 'var(--md-sys-color-error)', color: '#fff', cursor: 'pointer', fontSize: 14 }}
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || !wsConnected}
            style={{ padding: '8px 16px', borderRadius: 6, border: 'none', background: 'var(--md-sys-color-primary)', color: '#fff', cursor: 'pointer', fontSize: 14 }}
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
