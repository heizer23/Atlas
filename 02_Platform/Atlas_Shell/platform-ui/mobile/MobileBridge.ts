/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/MobileBridge.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: Web end of the AtlasPhone native bridge. Domain-free: carries typed
 * requests/events and manages the connection; interpretation of the data
 * belongs to the consuming Atlas application.
 *
 * Transport: an authenticated WebSocket to the AtlasPhone app on 127.0.0.1
 * (see loopback.ts). Chrome refuses the TWA postMessage channel, so the bridge
 * talks to a loopback server instead. Outside AtlasPhone no endpoint exists and
 * the bridge stays 'unavailable'.
 */

import {
  BridgeState, Capabilities, EventMap, IncomingMessage, MobileError, PROTOCOL_VERSION,
} from './types';

/** The slice of MessagePort the bridge needs (also what tests fake). */
export interface PortLike {
  postMessage(message: string): void;
  onmessage: ((ev: { data: unknown }) => void) | null;
  /** Transport closed (page keeps running); the bridge goes 'disconnected' until a new port arrives. */
  onclose?: (() => void) | null;
  close?(): void;
}

/** Shape of the global written by the inline capture script in index.html. */
export interface NativeGlobal {
  /** Loopback endpoint handed over by AtlasPhone ({port, token}); null outside AtlasPhone. */
  endpoint?: { port: number; token: string } | null;
  port: PortLike | null;
  /** Called with each port the transport delivers (first connect and every reconnect). */
  onPort: ((port: PortLike) => void) | null;
  /** Last channel-related diagnostics, shown on the test screen. */
  log: string[];
}

export interface BridgeOptions {
  requestTimeoutMs?: number;
  heartbeatMs?: number;
  heartbeatTimeoutMs?: number;
}

type Handler<T> = (payload: T) => void;

const DEFAULTS: Required<BridgeOptions> = {
  requestTimeoutMs: 10_000,
  heartbeatMs: 5_000,
  heartbeatTimeoutMs: 3_000,
};

interface Pending {
  resolve: (value: Record<string, unknown>) => void;
  reject: (err: MobileError) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class MobileBridge {
  private opts: Required<BridgeOptions>;
  private port: PortLike | null = null;
  private _state: BridgeState = 'unavailable';
  private _capabilities: Capabilities = {};
  private pending = new Map<string, Pending>();
  private handlers = new Map<string, Set<Handler<unknown>>>();
  private nextId = 1;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private handshakeToken = 0;

  constructor(native: NativeGlobal | undefined, opts: BridgeOptions = {}) {
    this.opts = { ...DEFAULTS, ...opts };
    if (!native) return;
    native.onPort = (port) => this.attach(port);
    if (native.port) this.attach(native.port);
  }

  // ── Introspection ──────────────────────────────────────────────────────────

  /** True when running inside AtlasPhone and the native side has answered the handshake. */
  isAvailable(): boolean {
    return this._state === 'connected';
  }

  get state(): BridgeState {
    return this._state;
  }

  /** Capabilities from the last handshake ({} until connected). */
  capabilities(): Capabilities {
    return this._capabilities;
  }

  /** Re-query live capabilities (permission states change at runtime). */
  async refreshCapabilities(): Promise<Capabilities> {
    const res = await this.request('capabilities');
    this._capabilities = (res.capabilities ?? {}) as Capabilities;
    return this._capabilities;
  }

  /** Resolves true once connected, false if not connected within timeoutMs. */
  whenAvailable(timeoutMs = 3_000): Promise<boolean> {
    if (this._state === 'connected') return Promise.resolve(true);
    return new Promise((resolve) => {
      const off = this.on('bridge.state', ({ state }) => {
        if (state === 'connected') { clearTimeout(t); off(); resolve(true); }
      });
      const t = setTimeout(() => { off(); resolve(false); }, timeoutMs);
    });
  }

  // ── Requests ───────────────────────────────────────────────────────────────

  /** Send a command; resolves with the result or rejects with MobileError. */
  request(method: string, params: Record<string, unknown> = {}, timeoutMs?: number): Promise<Record<string, unknown>> {
    if (!this.port) return Promise.reject(new MobileError('unavailable', 'Native bridge is not available'));
    const port = this.port;
    const id = `r${this.nextId++}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new MobileError('timeout', `No answer to ${method}`));
      }, timeoutMs ?? this.opts.requestTimeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      try {
        port.postMessage(JSON.stringify({ v: PROTOCOL_VERSION, type: 'request', id, method, params }));
      } catch (e) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(new MobileError('disconnected', e instanceof Error ? e.message : 'postMessage failed'));
      }
    });
  }

  // ── Events ─────────────────────────────────────────────────────────────────

  /** Subscribe to a native event. Returns an unsubscribe function. */
  on<K extends keyof EventMap & string>(name: K, handler: Handler<EventMap[K]>): () => void {
    let set = this.handlers.get(name);
    if (!set) { set = new Set(); this.handlers.set(name, set); }
    set.add(handler as Handler<unknown>);
    return () => { set!.delete(handler as Handler<unknown>); };
  }

  // ── Connection management ──────────────────────────────────────────────────

  private attach(port: PortLike): void {
    if (this.port && this.port !== port) {
      this.port.onmessage = null;
      this.port.onclose = null;
      this.port.close?.();
    }
    this.port = port;
    port.onmessage = (ev) => this.onMessage(ev.data);
    port.onclose = () => {
      if (this.port !== port) return;
      this.stopHeartbeat();
      this.handshakeToken++;
      this.failAllPending(new MobileError('disconnected', 'Native connection closed'));
      this.setState('disconnected');
    };
    this.setState('connecting');
    void this.handshake();
  }

  private async handshake(): Promise<void> {
    const token = ++this.handshakeToken;
    try {
      const res = await this.request('hello', { client: 'atlas-web', protocol: PROTOCOL_VERSION });
      if (token !== this.handshakeToken) return;
      this._capabilities = (res.capabilities ?? {}) as Capabilities;
      this.setState('connected');
      this.startHeartbeat();
    } catch {
      if (token !== this.handshakeToken) return;
      this.stopHeartbeat();
      this.setState('disconnected');
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeat = setInterval(async () => {
      try {
        await this.request('ping', {}, this.opts.heartbeatTimeoutMs);
        if (this._state === 'disconnected') { this.setState('connected'); }
      } catch {
        if (this._state === 'connected') this.setState('disconnected');
      }
    }, this.opts.heartbeatMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = null;
  }

  /** Stop timers and drop the port (used by tests and on page teardown). */
  dispose(): void {
    this.stopHeartbeat();
    if (this.port) { this.port.onmessage = null; this.port.onclose = null; }
    this.port = null;
    this.failAllPending(new MobileError('disconnected', 'Bridge disposed'));
    this.setState('unavailable');
  }

  private setState(state: BridgeState): void {
    if (state === this._state) return;
    this._state = state;
    this.emit('bridge.state', { state });
  }

  private failAllPending(err: MobileError): void {
    for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(err); }
    this.pending.clear();
  }

  // ── Incoming ───────────────────────────────────────────────────────────────

  private onMessage(data: unknown): void {
    if (typeof data !== 'string') return;
    let msg: IncomingMessage;
    try { msg = JSON.parse(data) as IncomingMessage; } catch { return; }
    if (!msg || msg.v !== PROTOCOL_VERSION) return;

    if (msg.type === 'response') {
      const p = this.pending.get(msg.id);
      if (!p) return;
      clearTimeout(p.timer);
      this.pending.delete(msg.id);
      if (msg.ok) p.resolve(msg.result ?? {});
      else p.reject(new MobileError(msg.error.code, msg.error.message));
    } else if (msg.type === 'event') {
      this.emit(msg.name, msg.data);
      // A live event proves the channel works even if a heartbeat was missed.
      if (this._state === 'disconnected') this.setState('connected');
    }
  }

  private emit(name: string, payload: unknown): void {
    this.handlers.get(name)?.forEach((h) => {
      try { h(payload); } catch (e) { console.error(`[mobile] handler for ${name} threw`, e); }
    });
  }
}
