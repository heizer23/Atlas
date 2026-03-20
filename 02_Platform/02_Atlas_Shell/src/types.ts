/**
 * File: 02_Platform/02_Atlas_Shell/src/types.ts
 * Component: atlas_shell
 *
 * Role: Exported public contract types: AppConfig and NavItem. These are the
 * stable integration contracts that all Atlas applications depend on.
 * Exported from @atlas/shell via src/index.ts.
 *
 * VERSIONING NOTE: AppConfig is the sole integration contract between
 * applications and the shell. Treat any change as a breaking change and
 * update the comment below with the change summary.
 *
 * Contract version: 1.0.0
 */

import type React from 'react';

/**
 * A single navigation destination entry.
 * The `order` field determines render sequence — sorted ascending before display.
 */
export interface NavItem {
  id: string;
  label: string;
  path: string;
  order: number;
}

/**
 * Registration contract for an Atlas application.
 * Applications call AppRegistry.register(config) with this shape from their
 * own shellConfig.ts. The shell renders exclusively from this contract and
 * carries no application-specific knowledge.
 */
export interface AppConfig {
  /** Stable unique identifier for the application. Must not change after registration. */
  appId: string;
  /** Human-readable application label shown in the launcher. */
  label: string;
  /** URL path prefix owned by this application (e.g. '/workout'). */
  basePath: string;
  /** Root component for the application. Accepts lazy or eager components. */
  component: React.ComponentType;
  /** Navigation items shown in the mobile bottom nav bar (max 5). */
  mobilePrimaryNav: NavItem[];
  /** Navigation items shown in the desktop/tablet sidebar. */
  desktopNav: NavItem[];
  /** Optional secondary navigation items surfaced in the mobile MoreMenu. */
  secondaryMenu?: NavItem[];
}
