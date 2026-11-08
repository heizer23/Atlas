/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/index.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: Public entry point — `import { mobile } from '@platform-ui/mobile'`.
 * One shared bridge per page; safe to import on desktop (stays 'unavailable').
 */

import { MobileBridge, type NativeGlobal } from './MobileBridge';
import { startLoopback } from './loopback';

declare global {
  interface Window { __atlasNative?: NativeGlobal }
}

const native = typeof window === 'undefined' ? undefined : window.__atlasNative;
export const mobile = new MobileBridge(native);
startLoopback(native);

export { MobileBridge } from './MobileBridge';
export type { PortLike, NativeGlobal, BridgeOptions } from './MobileBridge';
export { startLoopback } from './loopback';
export * from './types';
export { useMobileBridge } from './useMobileBridge';
