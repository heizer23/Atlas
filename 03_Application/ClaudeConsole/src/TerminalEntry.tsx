/**
 * ClaudeConsole — Terminal screen: xterm.js attached to a host tmux session.
 *
 * Talks to the host bridge (01_System/ClaudeTerminal), NOT to the ClaudeConsole backend container.
 * The bridge is tailnet-only (`tailscale serve`), so this screen works only while Tailscale is on
 * and is deliberately cross-origin to the Cloudflare-served shell (wss:// to the ts.net name).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import RecorderButton from '@platform-ui/components/RecorderButton';

// Non-secret tailnet address of the host (see 01_System/ClaudeTerminal/README.md).
const TERM_HOST = 'atlas-server.taild14f3a.ts.net:8443';
const SESSIONS_URL = `https://${TERM_HOST}/claudeterm/sessions`;
const wsBase = `wss://${TERM_HOST}/claudeterm/ws`;

const SPEECH_VOCABULARY = {
  keywords: ['Claude Code', 'Atlas', 'ClaudeConsole', 'FastAPI', 'Docker', 'nginx', 'TypeScript', 'pytest', 'Postgres', 'tmux'],
};

interface TmuxSession { name: string; windows: number; attached: number }

// Escape sequences for the key bar. `scroll` = tmux prefix (C-b) + `[` + PageUp (enter copy mode and page back).
const KEYS: { label: string; seq: string }[] = [
  { label: 'Esc', seq: '\x1b' },
  { label: 'Tab', seq: '\t' },
  { label: '↑', seq: '\x1b[A' },
  { label: '↓', seq: '\x1b[B' },
  { label: '←', seq: '\x1b[D' },
  { label: '→', seq: '\x1b[C' },
  { label: '⏎', seq: '\r' },
  { label: '|', seq: '|' },
  { label: '~', seq: '~' },
  { label: '/', seq: '/' },
  { label: '-', seq: '-' },
  { label: 'Scroll', seq: '\x02[\x1b[5~' },
  { label: '^C', seq: '\x03' },
  { label: '^D', seq: '\x04' },
];

const keyBtn = (active = false): React.CSSProperties => ({
  flex: '0 0 auto', minWidth: 40, padding: '10px 10px', borderRadius: 6, border: '1px solid #555',
  background: active ? '#4a6fa5' : '#2b2b2b', color: '#eee', fontSize: 14, cursor: 'pointer',
  touchAction: 'manipulation',
});

export default function TerminalApp() {
  const [sessions, setSessions] = useState<TmuxSession[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [newName, setNewName] = useState('claude');
  const [active, setActive] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setListError(null);
    try {
      const r = await fetch(SESSIONS_URL);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSessions(await r.json());
    } catch {
      setSessions(null);
      setListError('Cannot reach the terminal host. Is Tailscale connected on this device?');
    }
  }, []);

  useEffect(() => { if (!active) loadSessions(); }, [active, loadSessions]);

  if (active) return <TerminalView session={active} onExit={() => setActive(null)} />;

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 480 }}>
      <h2 style={{ margin: 0 }}>Terminal</h2>
      {listError && (
        <div style={{ color: 'var(--md-sys-color-error)' }}>
          {listError} <button onClick={loadSessions}>Retry</button>
        </div>
      )}
      {sessions?.map(s => (
        <button key={s.name} onClick={() => setActive(s.name)} style={{ ...keyBtn(), padding: 14, textAlign: 'left' }}>
          {s.name} — {s.windows} window{s.windows === 1 ? '' : 's'}{s.attached ? `, ${s.attached} attached` : ''}
        </button>
      ))}
      {sessions && sessions.length === 0 && <div>No tmux sessions yet.</div>}
      {sessions && (
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 32))}
            style={{ flex: 1, padding: 10, borderRadius: 6, border: '1px solid #ccc' }}
          />
          <button disabled={!newName} onClick={() => setActive(newName)} style={keyBtn()}>New / join</button>
        </div>
      )}
    </div>
  );
}

function TerminalView({ session, onExit }: { session: string; onExit: () => void }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const ctrlRef = useRef(false);
  const [ctrl, setCtrl] = useState(false);
  const [status, setStatus] = useState<'connecting' | 'open' | 'closed'>('connecting');
  const [attempt, setAttempt] = useState(0);

  const send = useCallback((data: string) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data));
  }, []);

  const setCtrlState = (v: boolean) => { ctrlRef.current = v; setCtrl(v); };

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13, cursorBlink: true, scrollback: 2000, convertEol: false,
      theme: { background: '#111', foreground: '#ddd' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current!);
    fit.fit();
    termRef.current = term;

    const ws = new WebSocket(`${wsBase}?session=${encodeURIComponent(session)}&cols=${term.cols}&rows=${term.rows}`);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;
    ws.onopen = () => { setStatus('open'); term.focus(); };
    ws.onclose = () => setStatus('closed');
    ws.onmessage = e => { if (e.data instanceof ArrayBuffer) term.write(new Uint8Array(e.data)); };

    const dataSub = term.onData(d => {
      // Sticky Ctrl from the key bar: turn the next letter into its control code.
      if (ctrlRef.current && d.length === 1) {
        const c = d.toUpperCase().charCodeAt(0);
        if (c >= 64 && c <= 95) { send(String.fromCharCode(c - 64)); setCtrlState(false); return; }
      }
      send(d);
    });

    const pushSize = () => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    };
    const ro = new ResizeObserver(pushSize);
    ro.observe(hostRef.current!);
    ws.addEventListener('open', pushSize);

    // Touch drag -> mouse-wheel events for tmux (xterm.js has no touch scrolling; the page would scroll instead).
    // Finger down = scroll back (wheel up, button 64); finger up = wheel down (65). tmux enters copy-mode or forwards to the app.
    const host = hostRef.current!;
    let lastY: number | null = null;
    let acc = 0;
    const LINE_PX = 16;
    const onTouchStart = (e: TouchEvent) => { lastY = e.touches.length === 1 ? e.touches[0].clientY : null; acc = 0; };
    const onTouchMove = (e: TouchEvent) => {
      if (lastY === null || e.touches.length !== 1) return;
      e.preventDefault();
      const y = e.touches[0].clientY;
      acc += y - lastY;
      lastY = y;
      const steps = Math.trunc(Math.abs(acc) / LINE_PX);
      if (steps) {
        const btn = acc > 0 ? 64 : 65;
        send(`\x1b[<${btn};1;1M`.repeat(steps));
        acc -= Math.sign(acc) * steps * LINE_PX;
      }
    };
    const onTouchEnd = () => { lastY = null; };
    host.addEventListener('touchstart', onTouchStart, { passive: true });
    host.addEventListener('touchmove', onTouchMove, { passive: false });
    host.addEventListener('touchend', onTouchEnd);

    return () => {
      host.removeEventListener('touchstart', onTouchStart);
      host.removeEventListener('touchmove', onTouchMove);
      host.removeEventListener('touchend', onTouchEnd);
      ro.disconnect(); dataSub.dispose(); ws.close(); term.dispose();
    };
  }, [session, attempt, send]);

  // Keep the key-bar taps from stealing focus (and hiding the soft keyboard).
  const keep = (e: React.SyntheticEvent) => e.preventDefault();

  return (
    // dvh so the on-screen keyboard shrinks the terminal instead of covering it.
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - 130px)', minHeight: 240 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 8px' }}>
        <button onClick={onExit} style={keyBtn()}>←</button>
        <strong style={{ flex: 1 }}>{session}</strong>
        <span style={{ fontSize: 12 }}>{status}</span>
        {status === 'closed' && <button onClick={() => { setStatus('connecting'); setAttempt(a => a + 1); }} style={keyBtn()}>Reconnect</button>}
      </div>
      <div ref={hostRef} style={{ flex: 1, minHeight: 0, background: '#111', padding: 4, touchAction: 'none', overscrollBehavior: 'contain' }} />
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', padding: 6, background: '#1a1a1a' }}>
       <div style={{ display: 'flex', gap: 6, overflowX: 'auto', flex: 1, minWidth: 0 }}>
        <button
          style={keyBtn(ctrl)} onPointerDown={keep} onMouseDown={keep}
          onClick={() => { setCtrlState(!ctrlRef.current); termRef.current?.focus(); }}
        >Ctrl</button>
        {KEYS.map(k => (
          <button
            key={k.label} style={keyBtn()} onPointerDown={keep} onMouseDown={keep}
            onClick={() => { send(k.seq); termRef.current?.focus(); }}
          >{k.label}</button>
        ))}
       </div>
        <RecorderButton onTranscript={t => send(t)} vocabulary={SPEECH_VOCABULARY} />
      </div>
    </div>
  );
}
