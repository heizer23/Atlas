import React, { useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import { FORECAST_COLUMNS } from '../format';
import type { Dataset, QueueStatRow } from '../types';

// ── Review Stats Panel ───────────────────────────────────────────────────────

// One compact Material 3 surface at the top of the review screen holding two
// labelled sections — CURRENT (immediate queue counts) and UPCOMING (a two-row
// forecast: `All` = every scheduled card, from GET /flashcards/stats; `Session`
// = cards rescheduled during this review session, tallied client-side from each
// review response). Visually secondary to the question card: flat
// surface-variant, no elevation. The section names sit rotated in a narrow left
// gutter beside their numbers, not above them, to keep the panel short. A
// /stats failure only blanks the `All` row — the session numbers still render.

export const statMetricLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--md-sys-color-on-surface-variant)',
};

// "CURRENT" / "UPCOMING" rotated to read bottom-to-top in the left gutter.
export function ForecastRow({ label, values }: { label: string; values: (number | null)[] }) {
  return (
    <>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)', paddingRight: 8 }}>
        {label}
      </span>
      {values.map((v, i) => (
        <span
          key={i}
          style={{
            fontSize: 14,
            textAlign: 'right',
            fontVariantNumeric: 'tabular-nums',
            color: v ? 'var(--md-sys-color-on-surface)' : 'var(--md-sys-color-outline)',
          }}
        >
          {v == null ? '·' : v}
        </span>
      ))}
    </>
  );
}

// ── Forecast grid (Sprint12_FSRSAndUXOverhaul) ──────────────────────────────
//
// Extracted from ReviewStatsPanel's inline "Upcoming" markup so the same
// grid (header row + one ForecastRow per `rows` entry) can be reused by the
// stats page's "Scheduled reviews (forecast)" zone. Deliberately decoupled
// from any session state — only `rows` (label + values, one entry per
// FORECAST_COLUMNS column) is accepted.
export function ForecastGrid({ rows }: { rows: { label: string; values: (number | null)[] }[] }) {
  // Mockup style: six equal columns, header above, count in a soft pill (grey dot when empty).
  // A row's own label (if any) sits in a left gutter; the review panel passes none.
  const hasLabels = rows.some(r => r.label);
  return (
    <div style={{ overflowX: 'auto' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `${hasLabels ? 'minmax(44px, auto) ' : ''}repeat(${FORECAST_COLUMNS.length}, minmax(40px, 1fr))`,
          rowGap: 6,
          columnGap: 4,
          alignItems: 'center',
          justifyItems: 'center',
          minWidth: 300,
        }}
      >
        {hasLabels && <span />}
        {FORECAST_COLUMNS.map(c => (
          <span key={c.key} style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)' }}>{c.label}</span>
        ))}
        {rows.map(row => (
          <React.Fragment key={row.label}>
            {hasLabels && <ForecastLabel label={row.label} />}
            {row.values.map((v, i) => <ForecastPill key={i} value={v} />)}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function ForecastLabel({ label }: { label: string }) {
  return <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)', justifySelf: 'start' }}>{label}</span>;
}

function ForecastPill({ value }: { value: number | null }) {
  const on = !!value;
  return (
    <span
      style={{
        minWidth: 30, textAlign: 'center', fontSize: 14, fontVariantNumeric: 'tabular-nums', lineHeight: '24px',
        padding: '0 8px', borderRadius: 12,
        background: on ? 'var(--md-sys-color-primary-container, #dbe6f7)' : 'transparent',
        color: on ? 'var(--md-sys-color-on-primary-container, #0b2a55)' : 'var(--md-sys-color-outline)',
      }}
    >
      {value == null ? '·' : value}
    </span>
  );
}

export interface TodayRow { recalls: number; unique_cards_seen: number; first_cards_seen: number }

export function ReviewStatsPanel({
  topic,
  essayId,
  sectionId,
  refreshToken,
  backlog,
  newRemaining,
}: {
  topic: string | null;
  essayId: string | null;
  sectionId: string | null;
  refreshToken: number;
  backlog: number;
  newRemaining: number;
}) {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [today, setToday] = useState<TodayRow | null>(null);

  useEffect(() => {
    (async () => {
      const qs = new URLSearchParams();
      if (topic) qs.set('topic', topic);
      if (essayId) qs.set('essay_id', essayId);
      if (sectionId) qs.set('section_id', sectionId);
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      const res = await apiFetch<Dataset<QueueStatRow>>(`/essaycards/flashcards/stats${suffix}`);
      if (isApiError(res)) {
        setStats(null);
      } else {
        setStats(Object.fromEntries(res.rows.map(r => [r.bucket, r.count])));
      }
      const todayRes = await apiFetch<Dataset<TodayRow>>(`/essaycards/review-stats/today${suffix}`);
      setToday(isApiError(todayRes) ? null : todayRes.rows[0] ?? null);
    })();
  }, [topic, essayId, sectionId, refreshToken]);

  // Recalls/Unique/First are backend-owned (GET /review-stats/today, UTC day);
  // Due/New are derived from the already-scoped due queue.
  const metrics: [string, string][] = [
    [String(backlog), 'Due'],
    [String(newRemaining), 'New'],
    [today ? String(today.recalls) : '·', 'Recalls'],
    [today ? String(today.unique_cards_seen) : '·', 'Unique'],
    [today ? String(today.first_cards_seen) : '·', 'First'],
  ];
  const allRow = FORECAST_COLUMNS.map(c => (stats ? stats[c.key] ?? 0 : null));

  return (
    <div
      style={{
        background: 'var(--md-sys-color-surface)',
        border: '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: 20,
        padding: '12px 8px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div data-testid="review-daily-metrics" style={{ display: 'flex' }}>
        {metrics.map(([value, label], i) => (
          <div
            key={label}
            style={{
              flex: 1, textAlign: 'center',
              borderLeft: i === 0 ? 'none' : '1px solid var(--md-sys-color-outline-variant)',
            }}
          >
            <div style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.1, color: 'var(--md-sys-color-on-surface)' }}>
              {value}
            </div>
            <div style={{ ...statMetricLabelStyle, marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{ borderTop: '1px solid var(--md-sys-color-outline-variant)' }} />

      <div data-testid="review-interval-row">
        <ForecastGrid rows={[{ label: '', values: allRow }]} />
      </div>
    </div>
  );
}
