/**
 * WorkoutTracker — launcher summary provider (AppConfig.launcherSummary).
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

const WEEKS = 4;

interface SessionRow { workout_date: string; split: string }
interface ActiveRow { split: string }

function localIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function relativeDay(iso: string, today: Date): string {
  const [y, m, d] = iso.split('-').map(Number);
  const days = Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
    - new Date(y, m - 1, d).getTime()) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

export async function workoutLauncherSummary(): Promise<LauncherSummary | null> {
  const [active, sessions] = await Promise.all([
    apiFetch<Dataset<ActiveRow>>('/workout/sessions/active'),
    apiFetch<Dataset<SessionRow>>('/workout/sessions?page_size=60'),
  ]);
  if (isApiError(sessions)) return null;

  const now = new Date();
  const worked = new Set(sessions.rows.map((r) => r.workout_date));
  const dots = [];
  for (let i = WEEKS * 7 - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    dots.push({ filled: worked.has(localIso(d)), today: i === 0 });
  }
  const groups = [];
  for (let i = 0; i < dots.length; i += 7) groups.push(dots.slice(i, i + 7));

  const running = !isApiError(active) && active.rows.length > 0 ? active.rows[0] : null;
  const latest = sessions.rows[0];
  if (running) return { line: 'Session in progress', meta: running.split, dots: groups };
  if (latest) return { line: `Last: ${latest.split}`, meta: relativeDay(latest.workout_date, now), dots: groups };
  return { line: 'No sessions yet', dots: groups };
}
