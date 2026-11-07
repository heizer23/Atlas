/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/types.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: Wire protocol + public data contracts shared with the native AtlasPhone
 * Mobile Platform (Kotlin: net.linspad.atlasphone.mobile.bridge.BridgeProtocol).
 * Keep both sides in sync; bump PROTOCOL_VERSION on incompatible changes.
 */

export const PROTOCOL_VERSION = 1;

export type BridgeState =
  | 'unavailable'   // not running inside AtlasPhone (desktop browser, plain Chrome)
  | 'connecting'    // native channel announced, handshake pending
  | 'connected'     // handshake complete
  | 'disconnected'; // was connected, heartbeat lost / page re-attached; will reconnect

export type MobileErrorCode =
  | 'unavailable' | 'timeout' | 'disconnected'
  | 'unknown_method' | 'invalid_params' | 'not_ready' | 'internal_error'
  | 'permission_denied' | 'permission_blocked' | 'location_disabled' | 'bluetooth_disabled' | 'unsupported'
  | (string & {});

export class MobileError extends Error {
  readonly code: MobileErrorCode;
  constructor(code: MobileErrorCode, message: string) {
    super(message);
    this.name = 'MobileError';
    this.code = code;
  }
}

export type PermissionStatus = 'granted' | 'denied' | 'blocked' | 'not_requested';

export interface ModuleCapability {
  available: boolean;
  permission?: PermissionStatus;
  [key: string]: unknown;
}
export type Capabilities = Record<string, ModuleCapability>;

/** One location fix. Fields the provider did not supply are null, never fabricated. */
export interface LocationSample {
  type: 'location.sample';
  captureId: string | null;
  sequence: number;
  /** ISO-8601 UTC, millisecond precision, taken from the fix itself. */
  timestamp: string;
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
  speedMetersPerSecond: number | null;
  altitudeMeters: number | null;
  bearingDegrees: number | null;
}

export interface HeartRateSample {
  type: 'heartRate.sample';
  captureId: string | null;
  sequence: number;
  /** ISO-8601 UTC, time the notification arrived on the phone. */
  timestamp: string;
  bpm: number;
  /** RR intervals in milliseconds when the sensor sent them, else null. */
  rrIntervalsMs: number[] | null;
  source: 'bluetooth';
}

export type Sample = LocationSample | HeartRateSample;

export interface EventMap {
  'bridge.state': { state: BridgeState };
  'location.sample': LocationSample;
  'location.state': { state: string; code?: string; message?: string };
  'heartRate.sample': HeartRateSample;
  'heartRate.state': { state: string; deviceId?: string; attempt?: number; code?: string; message?: string };
  'heartRate.device': { deviceId: string; name: string | null; rssi: number };
  [name: string]: unknown;
}

/** web -> native */
export interface RequestMessage {
  v: number; type: 'request'; id: string; method: string; params: Record<string, unknown>;
}
/** native -> web */
export type IncomingMessage =
  | { v: number; type: 'response'; id: string; ok: true; result: Record<string, unknown> }
  | { v: number; type: 'response'; id: string; ok: false; error: { code: string; message: string } }
  | { v: number; type: 'event'; name: string; data: unknown };
