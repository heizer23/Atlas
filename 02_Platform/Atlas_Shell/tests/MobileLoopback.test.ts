/**
 * File: 02_Platform/Atlas_Shell/tests/MobileLoopback.test.ts
 * Role: Loopback WebSocket transport tests against a fake WebSocket (web side only).
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { startLoopback } from '../platform-ui/mobile/loopback';
import { MobileBridge, type NativeGlobal } from '../platform-ui/mobile/MobileBridge';

class FakeWS {
  static instances: FakeWS[] = [];
  static failConstruct = false;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  sent: string[] = [];
  closed = false;
  constructor(public url: string) {
    if (FakeWS.failConstruct) throw new Error('blocked');
    FakeWS.instances.push(this);
  }
  send(s: string) { this.sent.push(s); }
  close() { this.closed = true; }
  // test helpers
  open() { this.onopen?.(); }
  recv(obj: object) { this.onmessage?.({ data: JSON.stringify(obj) }); }
  drop(code = 1006) { this.onclose?.({ code }); }
}

const WSImpl = FakeWS as unknown as typeof WebSocket;
const native = (): NativeGlobal => ({ endpoint: { port: 4321, token: 'tok_' + 'x'.repeat(30) }, port: null, onPort: null, log: [] });
let stop: (() => void) | undefined;

afterEach(() => { stop?.(); FakeWS.instances = []; FakeWS.failConstruct = false; vi.useRealTimers(); });

describe('startLoopback', () => {
  it('does nothing without an endpoint (desktop browser)', () => {
    const g: NativeGlobal = { port: null, onPort: null, log: [] };
    stop = startLoopback(g, { WebSocketImpl: WSImpl });
    expect(FakeWS.instances).toHaveLength(0);
    stop = startLoopback(undefined, { WebSocketImpl: WSImpl });
    expect(FakeWS.instances).toHaveLength(0);
  });

  it('connects to 127.0.0.1 on the given port and sends the token first', () => {
    const g = native();
    stop = startLoopback(g, { WebSocketImpl: WSImpl });
    const ws = FakeWS.instances[0];
    expect(ws.url).toBe('ws://127.0.0.1:4321/');
    ws.open();
    expect(JSON.parse(ws.sent[0])).toEqual({ v: 1, type: 'auth', token: g.endpoint!.token });
  });

  it('delivers a port only after the auth ack', () => {
    const g = native();
    const onPort = vi.fn();
    g.onPort = onPort;
    stop = startLoopback(g, { WebSocketImpl: WSImpl });
    const ws = FakeWS.instances[0];
    ws.open();
    expect(onPort).not.toHaveBeenCalled();
    ws.recv({ v: 1, type: 'auth', ok: true });
    expect(onPort).toHaveBeenCalledTimes(1);
  });

  it('closes on an unexpected first message and never delivers a port', () => {
    const g = native();
    const onPort = vi.fn();
    g.onPort = onPort;
    stop = startLoopback(g, { WebSocketImpl: WSImpl });
    const ws = FakeWS.instances[0];
    ws.open();
    ws.recv({ v: 1, type: 'response', id: 'r1', ok: true, result: {} });
    expect(ws.closed).toBe(true);
    expect(onPort).not.toHaveBeenCalled();
  });

  it('does not retry after a policy-violation (bad token) close', () => {
    vi.useFakeTimers();
    stop = startLoopback(native(), { WebSocketImpl: WSImpl, baseDelayMs: 10 });
    FakeWS.instances[0].open();
    FakeWS.instances[0].drop(1008);
    vi.advanceTimersByTime(60_000);
    expect(FakeWS.instances).toHaveLength(1);
  });

  it('reconnects with backoff after a drop and hands out a fresh port', () => {
    vi.useFakeTimers();
    const g = native();
    const ports: unknown[] = [];
    g.onPort = (p) => ports.push(p);
    stop = startLoopback(g, { WebSocketImpl: WSImpl, baseDelayMs: 100, maxDelayMs: 1000 });
    const first = FakeWS.instances[0];
    first.open(); first.recv({ v: 1, type: 'auth', ok: true });
    first.drop();
    vi.advanceTimersByTime(99);
    expect(FakeWS.instances).toHaveLength(1);
    vi.advanceTimersByTime(2);
    expect(FakeWS.instances).toHaveLength(2);
    FakeWS.instances[1].open(); FakeWS.instances[1].recv({ v: 1, type: 'auth', ok: true });
    expect(ports).toHaveLength(2);
    expect(ports[0]).not.toBe(ports[1]);
  });

  it('gives up if it never connects (stale endpoint)', () => {
    vi.useFakeTimers();
    stop = startLoopback(native(), { WebSocketImpl: WSImpl, baseDelayMs: 10, maxDelayMs: 20, maxInitialAttempts: 3 });
    for (let i = 0; i < 20; i++) {
      FakeWS.instances.at(-1)?.drop();
      vi.advanceTimersByTime(50);
    }
    expect(FakeWS.instances.length).toBeLessThanOrEqual(4);
  });

  it('survives a blocked WebSocket constructor', () => {
    vi.useFakeTimers();
    FakeWS.failConstruct = true;
    const g = native();
    expect(() => { stop = startLoopback(g, { WebSocketImpl: WSImpl }); }).not.toThrow();
    expect(g.log.some((l) => l.includes('cannot open socket'))).toBe(true);
  });

  it('works end-to-end with MobileBridge: handshake, close -> disconnected, reconnect -> connected', async () => {
    vi.useFakeTimers();
    const g = native();
    const bridge = new MobileBridge(g);
    stop = startLoopback(g, { WebSocketImpl: WSImpl, baseDelayMs: 100 });
    const answer = (ws: FakeWS) => {
      for (const raw of ws.sent) {
        const m = JSON.parse(raw);
        if (m.type === 'request' && m.method === 'hello') ws.recv({ v: 1, type: 'response', id: m.id, ok: true, result: { capabilities: {} } });
      }
    };
    const ws1 = FakeWS.instances[0];
    ws1.open(); ws1.recv({ v: 1, type: 'auth', ok: true });
    await vi.advanceTimersByTimeAsync(0);
    answer(ws1);
    await vi.advanceTimersByTimeAsync(0);
    expect(bridge.state).toBe('connected');

    ws1.drop();
    expect(bridge.state).toBe('disconnected');
    await vi.advanceTimersByTimeAsync(150);
    const ws2 = FakeWS.instances[1];
    ws2.open(); ws2.recv({ v: 1, type: 'auth', ok: true });
    await vi.advanceTimersByTimeAsync(0);
    answer(ws2);
    await vi.advanceTimersByTimeAsync(0);
    expect(bridge.state).toBe('connected');
    bridge.dispose();
  });
});
