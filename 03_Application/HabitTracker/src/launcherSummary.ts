/**
 * HabitTracker — launcher summary provider (AppConfig.launcherSummary).
 *
 * Read-only: derives the Atlas launcher status block from existing endpoints.
 * Returns null on any failure so the launcher falls back to the label alone.
 */

import { apiFetch, isApiError } from '@platform-ui/api/client';
import type { LauncherSummary } from '@atlas/shell';

interface Dataset<R> {
  meta: { total: number };
  rows: R[];
}

interface HabitEntry { checked: boolean }
interface ReviewRow { habits: HabitEntry[] }

function localIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export async function habitLauncherSummary(): Promise<LauncherSummary | null> {
  const res = await apiFetch<Dataset<ReviewRow>>(`/habittracker/reviews/${localIso(new Date())}`);
  if (isApiError(res) || res.rows.length === 0) return null;

  const habits = res.rows[0].habits;
  const checked = habits.filter((h) => h.checked).length;
  return {
    line: `${checked} / ${habits.length} today`,
    dots: [habits.map((h) => ({ filled: h.checked }))],
  };
}
