/**
 * File: 02_Platform/Atlas_Shell/src/shell/ShellContext.ts
 * Component: atlas_shell
 *
 * Role: Shared React context for shell navigation state. Both ShellLayout
 * (provider) and useShell (consumer) import from this single source.
 * Do not import ShellContext from anywhere other than this file.
 */

import { createContext } from 'react';
import type { AppConfig } from '../types';

/**
 * The value shape carried by ShellContext.
 * activeApp is undefined when the current path matches no registered application.
 */
export interface ShellContextValue {
  /** The AppConfig whose basePath is a prefix of the current URL path, or undefined. */
  activeApp: AppConfig | undefined;
  /** Snapshot of all registered applications at the time ShellLayout rendered. */
  allApps: AppConfig[];
}

/**
 * React context for shell navigation state.
 * Default is undefined — useShell throws a descriptive error if consumed
 * outside a ShellLayout provider tree.
 */
export const ShellContext = createContext<ShellContextValue | undefined>(undefined);
