/**
 * File: 02_Platform/Atlas_Shell/src/shell/recency.ts
 * Component: atlas_shell
 *
 * Role: Per-device "last opened" ordering for the launcher. Stored in
 * localStorage under 'atlas.shell.recency' as { [appId]: epochMs }. This is
 * an ephemeral per-device convenience (R-CON-BP-03 allowed operational state):
 * if it is missing, blocked, or cleared, the launcher falls back to registry
 * order and nothing else changes.
 */

const KEY = 'atlas.shell.recency';

function read(): Record<string, number> {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, number>) : {};
  } catch {
    return {};
  }
}

export function markOpened(appId: string): void {
  try {
    const data = read();
    data[appId] = Date.now();
    window.localStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    /* storage unavailable — ordering falls back to registry order */
  }
}

/** Returns apps ordered most-recently-opened first; never-opened keep registry order after them. */
export function sortByRecency<T extends { appId: string }>(apps: T[]): T[] {
  const data = read();
  return apps
    .map((app, index) => ({ app, index, at: typeof data[app.appId] === 'number' ? data[app.appId] : 0 }))
    .sort((a, b) => b.at - a.at || a.index - b.index)
    .map((entry) => entry.app);
}
