/**
 * File: 02_Platform/Atlas_Shell/src/index.ts
 * Component: atlas_shell
 *
 * Role: Public module entry point for the @atlas/shell alias. This is the
 * only import path applications should use when consuming shell types,
 * components, or the registry.
 *
 * Applications configure the alias in their vite.config.ts:
 *   '@atlas/shell': path.resolve(__dirname, '../../02_Platform/Atlas_Shell/src/index.ts')
 *
 * And in their tsconfig.json paths:
 *   "@atlas/shell": ["../../02_Platform/Atlas_Shell/src/index.ts"]
 */

// Contract types
export type { NavItem, AppConfig } from './types';

// Registry API
export { AppRegistry } from './registry/AppRegistry';

// Layout and routing components
export { ShellLayout } from './shell/ShellLayout';
export { Router } from './shell/Router';

// Hook
export { useShell } from './hooks/useShell';

// Launcher (exported for use in custom shell integrations)
export { AppLauncher } from './launcher/AppLauncher';
