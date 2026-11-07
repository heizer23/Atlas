/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/index.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: Public entry point — `import { mobile } from '@platform-ui/mobile'`.
 * One shared bridge per page; safe to import on desktop (stays 'unavailable').
 */

import { MobileBridge, type NativeGlobal } from './MobileBridge';

declare global {
  interface Window { __atlasNative?: NativeGlobal }
}

export const mobile = new MobileBridge(typeof window === 'undefined' ? undefined : window.__atlasNative);

export { MobileBridge } from './MobileBridge';
export type { PortLike, NativeGlobal, BridgeOptions } from './MobileBridge';
export * from './types';
export { useMobileBridge } from './useMobileBridge';
