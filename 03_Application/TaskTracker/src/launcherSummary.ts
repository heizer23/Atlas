/**
 * TaskTracker — launcher summary provider (AppConfig.launcherSummary).
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

interface AgendaRow {
  title: string;
  agenda_date: string;
  agenda_bucket: 'overdue' | 'today' | 'upcoming';
}

function whenLabel(row: AgendaRow): string {
  if (row.agenda_bucket === 'overdue') return 'Overdue';
  if (row.agenda_bucket === 'today') return 'Today';
  const [y, m, d] = row.agenda_date.split('-').map(Number);
  const now = new Date();
  const diff = Math.round((new Date(y, m - 1, d).getTime()
    - new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) / 86_400_000);
  if (diff === 1) return 'Tomorrow';
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'short' });
}

export async function taskLauncherSummary(): Promise<LauncherSummary | null> {
  const res = await apiFetch<Dataset<AgendaRow>>('/tasks/agenda');
  if (isApiError(res)) return null;

  const rows = res.rows;
  const due = rows.filter((r) => r.agenda_bucket !== 'upcoming').length;
  const upcoming = rows.length - due;
  const shown = rows.slice(0, 3);
  const remaining = rows.length - shown.length;

  return {
    line: `${due} due`,
    meta: `${upcoming} upcoming`,
    items: shown.map((r) => ({ label: r.title, when: whenLabel(r) })),
    more: remaining > 0 ? `+ ${remaining} more` : undefined,
  };
}
