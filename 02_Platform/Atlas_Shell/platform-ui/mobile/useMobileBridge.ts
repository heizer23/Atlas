/**
 * File: 02_Platform/Atlas_Shell/platform-ui/mobile/useMobileBridge.ts
 * Component: atlas_shell (Mobile Bridge)
 *
 * Role: React hook exposing the bridge connection state and capabilities.
 */

import { useEffect, useState } from 'react';
import type { MobileBridge } from './MobileBridge';
import type { BridgeState, Capabilities } from './types';

export function useMobileBridge(bridge: MobileBridge): { state: BridgeState; available: boolean; capabilities: Capabilities } {
  const [state, setState] = useState<BridgeState>(bridge.state);
  const [capabilities, setCapabilities] = useState<Capabilities>(bridge.capabilities());
  useEffect(() => {
    setState(bridge.state);
    setCapabilities(bridge.capabilities());
    return bridge.on('bridge.state', ({ state: s }) => {
      setState(s);
      setCapabilities(bridge.capabilities());
    });
  }, [bridge]);
  return { state, available: state === 'connected', capabilities };
}
