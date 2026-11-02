/**
 * HabitTracker — launcher summary provider (AppConfig.launcherSummary).
 *
 * Three rows of dots (two days ago, yesterday, today), one filled dot per
 * habit done that day; no labels, no empty placeholders. Returns null on any
 * failure so the launcher falls back to the label alone.
 */

import { apiFetch, isApiError } from '@platform-ui/api/client';
import type { LauncherSummary } from '@atlas/shell';

interface HistoryDay { date: string; done: number }

function localIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export async function habitLauncherSummary(): Promise<LauncherSummary | null> {
  const res = await apiFetch<{ days: HistoryDay[] }>(`/habittracker/history?days=3&end=${localIso(new Date())}`);
  if (isApiError(res)) return null;

  const rows = res.days.map((d) => Array.from({ length: d.done }, () => ({ filled: true })));
  return { line: '', dots: rows, dotsStacked: true };
}
