/**
 * EssayCards — launcher summary provider (AppConfig.launcherSummary).
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

interface ActivityRow { date: string; recalls: number }

export async function essayCardsLauncherSummary(): Promise<LauncherSummary | null> {
  const [due, activity] = await Promise.all([
    apiFetch<Dataset<unknown>>('/essaycards/flashcards/due'),
    apiFetch<Dataset<ActivityRow>>('/essaycards/review-stats/activity'),
  ]);
  if (isApiError(due)) return null;

  const dueCount = due.meta.total;
  const summary: LauncherSummary = {
    line: `${dueCount} due ${dueCount === 1 ? 'review' : 'reviews'}`,
  };

  if (!isApiError(activity) && activity.rows.length > 0) {
    // Dataset is zero-filled, oldest first, UTC days; the last row is today.
    const days = activity.rows.slice(-WEEKS * 7);
    const last = days.length - 1;
    summary.meta = `${days[last].recalls} reviewed today`;
    const dots = days.map((d, i) => ({ filled: d.recalls > 0, today: i === last }));
    const groups = [];
    for (let i = 0; i < dots.length; i += 7) groups.push(dots.slice(i, i + 7));
    summary.dots = groups;
  }
  return summary;
}
