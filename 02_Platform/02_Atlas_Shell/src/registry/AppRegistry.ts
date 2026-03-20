/**
 * File: 02_Platform/02_Atlas_Shell/src/registry/AppRegistry.ts
 * Component: atlas_shell
 *
 * Role: Module-level registry. Exported as a plain const object (not a class).
 * Internal state is a module-private _apps: AppConfig[] array — never exposed
 * directly. Has no React dependency — pure TypeScript.
 *
 * Failure modes handled here:
 *   SHELL_INVALID_APP_CONFIG  — console.error + skip, does not throw
 *   SHELL_DUPLICATE_APP_ID    — console.error + skip, does not throw
 */

import type { AppConfig } from '../types';

// Module-private registry state. Never exported or exposed via reference.
let _apps: AppConfig[] = [];

/**
 * Validate that `config` conforms to the AppConfig interface.
 * Returns the validated AppConfig on success; returns null on any violation.
 * Never throws — caller handles null by logging and skipping.
 * Note: component accepts both function components and React.lazy objects.
 */
function validateAppConfig(config: unknown): AppConfig | null {
  if (config === null || typeof config !== 'object') return null;

  const c = config as Record<string, unknown>;

  if (typeof c['appId'] !== 'string' || c['appId'].trim() === '') return null;
  if (typeof c['label'] !== 'string' || c['label'].trim() === '') return null;
  if (typeof c['basePath'] !== 'string' || c['basePath'].trim() === '') return null;
  // Accept function components and React.lazy objects (typeof === 'object')
  if (typeof c['component'] !== 'function' && (typeof c['component'] !== 'object' || c['component'] === null)) return null;
  if (!Array.isArray(c['mobilePrimaryNav'])) return null;
  if (!Array.isArray(c['desktopNav'])) return null;
  if (
    c['secondaryMenu'] !== undefined &&
    c['secondaryMenu'] !== null &&
    !Array.isArray(c['secondaryMenu'])
  ) return null;

  return config as AppConfig;
}

/**
 * AppRegistry — the runtime registry of all registered Atlas applications.
 *
 * Plain exported const object; not a class. All state is private to this module.
 * Applications call AppRegistry.register(config) from their own shellConfig.ts.
 */
export const AppRegistry = {
  /**
   * Validate and store an AppConfig.
   * Skips with console.error on schema violation (SHELL_INVALID_APP_CONFIG)
   * or duplicate appId (SHELL_DUPLICATE_APP_ID). Does not throw.
   */
  register(config: AppConfig): void {
    const validated = validateAppConfig(config);
    if (validated === null) {
      console.error(
        'SHELL_INVALID_APP_CONFIG: Registration skipped — config failed schema validation.',
        config,
      );
      return;
    }

    const duplicate = _apps.some((a) => a.appId === validated.appId);
    if (duplicate) {
      console.error(
        `SHELL_DUPLICATE_APP_ID: Registration skipped — appId "${validated.appId}" is already registered.`,
        config,
      );
      return;
    }

    _apps.push(validated);
  },

  /**
   * Return all successfully registered AppConfig objects in registration order.
   * Returns a shallow copy to prevent external mutation of the internal array.
   */
  getAll(): AppConfig[] {
    return _apps.slice();
  },

  /**
   * Return the AppConfig whose basePath is a prefix of the given path.
   * Returns undefined if no registered app matches.
   */
  getByPath(path: string): AppConfig | undefined {
    return _apps.find((app) => path === app.basePath || path.startsWith(app.basePath + '/'));
  },

  /**
   * Reset the registry to empty state.
   * Intended for use in tests only — do not call in production code.
   */
  clear(): void {
    _apps = [];
  },
} as const;
