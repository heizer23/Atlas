/**
 * File: 02_Platform/Atlas_Shell/src/mobile/MobileTestScreen.tsx
 * Component: atlas_shell (Mobile Platform diagnostics)
 *
 * Role: Minimal technical screen exercising the REAL native bridge — no simulated
 * data. Shows bridge/connection state, capabilities and a raw event log.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { mobile, useMobileBridge } from '@platform-ui/mobile';

const box: React.CSSProperties = { border: '1px solid #8884', borderRadius: 8, padding: 12, margin: '12px 0' };
const btn: React.CSSProperties = { padding: '8px 14px', marginRight: 8, marginTop: 6, fontSize: 15 };
const pre: React.CSSProperties = { fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 };

export default function MobileTestScreen(): JSX.Element {
  const { state, capabilities } = useMobileBridge(mobile);
  const [log, setLog] = useState<string[]>([]);
  const logRef = useRef<string[]>([]);

  const note = useCallback((line: string) => {
    logRef.current = [`${new Date().toISOString().slice(11, 23)} ${line}`, ...logRef.current].slice(0, 80);
    setLog(logRef.current);
  }, []);

  // The transport log is written outside React, so poll it.
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => mobile.on('bridge.state', ({ state: s }) => note(`bridge.state -> ${s}`)), [note]);

  const ping = async () => {
    const t0 = performance.now();
    try {
      await mobile.request('ping');
      note(`ping ok ${Math.round(performance.now() - t0)} ms`);
    } catch (e) {
      note(`ping failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const refresh = async () => {
    try {
      await mobile.refreshCapabilities();
      note('capabilities refreshed');
    } catch (e) {
      note(`capabilities failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const channelLog = window.__atlasNative?.log ?? [];

  return (
    <div style={{ padding: 16, maxWidth: 640, margin: '0 auto' }}>
      <h2>Mobile Platform</h2>

      <div style={box}>
        <h3 style={{ marginTop: 0 }}>Device status</h3>
        <div>Native bridge: <b>{state}</b></div>
        <div>Bridge endpoint from AtlasPhone: {String(!!window.__atlasNative?.endpoint)}
          {window.__atlasNative?.endpoint ? ` (port ${window.__atlasNative.endpoint.port})` : ''}</div>
        <div>Page: {window.location.origin} · secure context: {String(window.isSecureContext)}</div>
        <div>Capabilities: {Object.keys(capabilities).length === 0 ? '—' : Object.keys(capabilities).join(', ')}</div>
        <button style={btn} onClick={ping} disabled={state !== 'connected'}>Ping</button>
        <button style={btn} onClick={refresh} disabled={state !== 'connected'}>Refresh capabilities</button>
        <pre style={{ ...pre, marginTop: 8 }}>{JSON.stringify(capabilities, null, 1)}</pre>
      </div>

      <div style={box}>
        <h3 style={{ marginTop: 0 }}>Connection diagnostics</h3>
        <pre style={pre}>{channelLog.length ? channelLog.join('\n') : 'no loopback activity (no endpoint from AtlasPhone)'}</pre>
      </div>

      <div style={box}>
        <h3 style={{ marginTop: 0 }}>Event log</h3>
        <pre style={pre}>{log.join('\n') || '—'}</pre>
      </div>
    </div>
  );
}
