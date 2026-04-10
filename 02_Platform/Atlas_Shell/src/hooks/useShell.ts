/**
 * File: 02_Platform/Atlas_Shell/src/hooks/useShell.ts
 * Component: atlas_shell
 *
 * Role: React hook providing shell navigation state to components in the
 * ShellLayout provider tree. Throws a descriptive error if called outside
 * a ShellLayout.
 */

import { useContext } from 'react';
import { ShellContext } from '../shell/ShellContext';
import type { AppConfig } from '../types';

/**
 * Returns the current shell navigation state.
 * Must be called within a component rendered inside <ShellLayout>.
 *
 * @throws {Error} 'useShell must be used inside ShellLayout' if context is absent.
 */
export function useShell(): { activeApp: AppConfig | undefined; allApps: AppConfig[] } {
  const ctx = useContext(ShellContext);
  if (ctx === undefined) {
    throw new Error('useShell must be used inside ShellLayout');
  }
  return ctx;
}
