/**
 * File: 02_Platform/Atlas_Shell/tests/MobileBridge.test.ts
 * Role: MobileBridge protocol/connection tests against a fake native port.
 * These verify the web side only; the real native side is exercised on the phone.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { MobileBridge, type NativeGlobal, type PortLike } from '../platform-ui/mobile/MobileBridge';
import { MobileError } from '../platform-ui/mobile/types';

class FakeNative implements PortLike {
  onmessage: PortLike['onmessage'] = null;
  sent: Array<{ id: string; method: string; params: Record<string, unknown> }> = [];
  autoReply = true;
  caps = { location: { available: true, permission: 'not_requested' } };
  postMessage(raw: string) {
    const req = JSON.parse(raw);
    this.sent.push(req);
    if (!this.autoReply) return;
    queueMicrotask(() => {
      if (req.method === 'hello' || req.method === 'capabilities') this.reply(req.id, { capabilities: this.caps });
      else if (req.method === 'ping') this.reply(req.id, {});
      else if (req.method === 'boom') this.fail(req.id, 'permission_denied', 'nope');
      else this.reply(req.id, { echo: req.params });
    });
  }
  reply(id: string, result: object) { this.push({ v: 1, type: 'response', id, ok: true, result }); }
  fail(id: string, code: string, message: string) { this.push({ v: 1, type: 'response', id, ok: false, error: { code, message } }); }
  event(name: string, data: object) { this.push({ v: 1, type: 'event', name, data }); }
  push(msg: object) { this.onmessage?.({ data: JSON.stringify(msg) }); }
}

const flush = () => new Promise((r) => setTimeout(r, 0));
let bridge: MobileBridge | undefined;
afterEach(() => { bridge?.dispose(); vi.useRealTimers(); });

function setup(native: FakeNative | null) {
  const g: NativeGlobal = { port: native, onPort: null, log: [] };
  bridge = new MobileBridge(g);
  return { g, bridge };
}

describe('MobileBridge', () => {
  it('stays unavailable without a native global (desktop browser)', async () => {
    bridge = new MobileBridge(undefined);
    expect(bridge.isAvailable()).toBe(false);
    expect(bridge.state).toBe('unavailable');
    await expect(bridge.request('ping')).rejects.toMatchObject({ code: 'unavailable' });
    expect(await bridge.whenAvailable(10)).toBe(false);
  });

  it('stays unavailable when no port is ever delivered', () => {
    const { bridge: b } = setup(null);
    expect(b.state).toBe('unavailable');
  });

  it('handshakes with hello and exposes capabilities', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    expect(native.sent[0].method).toBe('hello');
    expect(b.isAvailable()).toBe(true);
    expect(b.capabilities().location.available).toBe(true);
  });

  it('connects when the port arrives after construction', async () => {
    const native = new FakeNative();
    const { g, bridge: b } = setup(null);
    expect(b.state).toBe('unavailable');
    g.onPort!(native);
    await flush();
    expect(b.state).toBe('connected');
  });

  it('correlates responses by unique request id', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    const [a, c] = await Promise.all([b.request('x', { n: 1 }), b.request('x', { n: 2 })]);
    expect(a).toEqual({ echo: { n: 1 } });
    expect(c).toEqual({ echo: { n: 2 } });
    const ids = native.sent.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('rejects with the native error code', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    const err = await b.request('boom').catch((e) => e);
    expect(err).toBeInstanceOf(MobileError);
    expect(err.code).toBe('permission_denied');
  });

  it('times out unanswered requests', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    native.autoReply = false;
    await expect(b.request('slow', {}, 20)).rejects.toMatchObject({ code: 'timeout' });
  });

  it('delivers events to subscribers and supports unsubscribe', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    const got: unknown[] = [];
    const off = b.on('location.sample', (s) => got.push(s));
    native.event('location.sample', { sequence: 1 });
    off();
    native.event('location.sample', { sequence: 2 });
    expect(got).toEqual([{ sequence: 1 }]);
  });

  it('ignores malformed, wrong-version and unknown-id messages', async () => {
    const native = new FakeNative();
    const { bridge: b } = setup(native);
    await flush();
    const spy = vi.fn();
    b.on('x', spy);
    native.onmessage!({ data: 'not json' });
    native.onmessage!({ data: 42 });
    native.push({ v: 99, type: 'event', name: 'x', data: {} });
    native.reply('nope', {});
    expect(spy).not.toHaveBeenCalled();
    expect(b.state).toBe('connected');
  });

  it('goes disconnected on missed heartbeat and recovers', async () => {
    vi.useFakeTimers();
    const native = new FakeNative();
    const g: NativeGlobal = { port: native, onPort: null, log: [] };
    bridge = new MobileBridge(g, { heartbeatMs: 100, heartbeatTimeoutMs: 50 });
    await vi.advanceTimersByTimeAsync(0);
    expect(bridge.state).toBe('connected');
    native.autoReply = false;
    await vi.advanceTimersByTimeAsync(200);
    expect(bridge.state).toBe('disconnected');
    native.autoReply = true;
    await vi.advanceTimersByTimeAsync(200);
    expect(bridge.state).toBe('connected');
  });

  it('re-handshakes on a new port (page navigation / reconnect)', async () => {
    const first = new FakeNative();
    const { g, bridge: b } = setup(first);
    await flush();
    const second = new FakeNative();
    g.onPort!(second);
    await flush();
    expect(second.sent[0].method).toBe('hello');
    expect(first.onmessage).toBeNull();
    expect(b.state).toBe('connected');
  });
});
