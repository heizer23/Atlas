/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/loopback.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: WebSocket transport to the AtlasPhone native app on 127.0.0.1.
 * Security: the server only accepts the Atlas origin plus a per-launch secret
 * token, sent as the first message; the token never goes to any other host.
 * The transport reconnects with capped backoff while the page is open, and
 * gives up quietly if it never manages to connect (e.g. a stale endpoint
 * remembered from an earlier AtlasPhone run).
 */

import { PROTOCOL_VERSION } from './types';
import type { NativeGlobal, PortLike } from './MobileBridge';

export interface LoopbackOptions {
  /** WebSocket constructor (injectable for tests). */
  WebSocketImpl?: typeof WebSocket;
  /** Consecutive failures before the first successful connect after which we stop trying. */
  maxInitialAttempts?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

const MAX_INITIAL_ATTEMPTS = 6;

/** Starts the transport if AtlasPhone provided an endpoint. Returns a stop function. */
export function startLoopback(native: NativeGlobal | undefined, opts: LoopbackOptions = {}): () => void {
  const endpoint = native?.endpoint;
  if (!native || !endpoint) return () => undefined;

  const WS = opts.WebSocketImpl ?? WebSocket;
  const maxInitial = opts.maxInitialAttempts ?? MAX_INITIAL_ATTEMPTS;
  const base = opts.baseDelayMs ?? 500;
  const cap = opts.maxDelayMs ?? 5_000;

  let stopped = false;
  let everConnected = false;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let current: WebSocket | null = null;

  const log = (line: string) => {
    native.log.push(`${new Date().toISOString()} ${line}`);
    if (native.log.length > 50) native.log.shift();
  };

  const scheduleReconnect = () => {
    if (stopped) return;
    if (!everConnected && attempt >= maxInitial) { log('loopback: giving up (never connected)'); return; }
    const delay = Math.min(cap, base * 2 ** Math.min(attempt, 10));
    attempt++;
    timer = setTimeout(connect, delay);
  };

  const connect = () => {
    if (stopped) return;
    let port: (PortLike & { open: boolean }) | null = null;
    let ws: WebSocket;
    try {
      ws = new WS(`ws://127.0.0.1:${endpoint.port}/`);
    } catch (e) {
      log(`loopback: cannot open socket (${e instanceof Error ? e.message : String(e)})`);
      scheduleReconnect();
      return;
    }
    current = ws;
    log(`loopback: connecting to 127.0.0.1:${endpoint.port} (attempt ${attempt + 1})`);
    // A hung attempt (neither open nor error) usually means the browser is holding the request,
    // e.g. waiting for a local-network permission it cannot show.
    const pending = setTimeout(() => {
      if (ws.readyState === 0) log('loopback: still connecting after 4 s (browser may be blocking local access)');
    }, 4_000);

    ws.onopen = () => {
      clearTimeout(pending);
      log('loopback: socket open, authenticating');
      ws.send(JSON.stringify({ v: PROTOCOL_VERSION, type: 'auth', token: endpoint.token }));
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (port) { port.onmessage?.({ data: ev.data }); return; }
      // First message must be the auth acknowledgement.
      try {
        const msg = JSON.parse(String(ev.data));
        if (msg.type === 'auth' && msg.ok === true) {
          everConnected = true;
          attempt = 0;
          port = {
            open: true,
            onmessage: null,
            onclose: null,
            postMessage: (m: string) => ws.send(m),
            close: () => ws.close(),
          };
          log('loopback: authenticated');
          native.port = port;
          native.onPort?.(port);
          return;
        }
      } catch { /* fall through */ }
      log('loopback: unexpected first message, closing');
      ws.close();
    };

    ws.onerror = () => { log('loopback: socket error'); };

    ws.onclose = (ev: CloseEvent) => {
      clearTimeout(pending);
      if (current === ws) current = null;
      log(`loopback: closed (code ${ev.code})`);
      if (port) { port.open = false; port.onclose?.(); }
      // 1008 = policy violation: bad token. Retrying cannot help.
      if (ev.code === 1008) { log('loopback: rejected by native side, not retrying'); return; }
      scheduleReconnect();
    };
  };

  connect();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    current?.close();
  };
}
