/**
 * File: 02_Platform/Atlas_Shell/src/types.ts
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
 * Contract version: 1.1.0 (additive: launcherIcon, launcherTone, launcherSummary)
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
  /** Optional Material Symbols Rounded icon name for the launcher row (e.g. 'fitness_center'). Falls back to the letter bullet. */
  launcherIcon?: string;
  /** Optional launcher icon tint, chosen from the shell-owned palette. Defaults to 'blue'. */
  launcherTone?: LauncherTone;
  /**
   * Optional provider of the live status shown under the app label in the launcher.
   * The app owns the meaning; the shell only renders the returned structure.
   * Return null (or reject) to show the label alone. Called once per launcher mount.
   */
  launcherSummary?: () => Promise<LauncherSummary | null>;
}

export type LauncherTone = 'amber' | 'green' | 'grey' | 'violet' | 'rose' | 'blue' | 'teal';

/** One dot in a launcher activity strip. */
export interface LauncherDot {
  filled: boolean;
  /** Marks the current day; rendered with a ring. */
  today?: boolean;
}

/** Display-only status block rendered by the launcher row. */
export interface LauncherSummary {
  /** Primary status line, e.g. "18 due reviews". */
  line: string;
  /** Optional secondary text shown after the primary line, e.g. "42 reviewed today". */
  meta?: string;
  /** Optional activity strip: groups of dots (e.g. one group per week), oldest first. */
  dots?: LauncherDot[][];
  /** Optional short list under the status line (max 3 rendered). */
  items?: Array<{ label: string; when?: string }>;
  /** Optional trailing note under the list, e.g. "+ 2 more upcoming". */
  more?: string;
}
