import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import BarChart from '@platform-ui/components/BarChart';
import type { ApiError, Dataset as PlatformDataset } from '@platform-ui/api/types';
import { ForecastGrid } from '../components/ReviewStatsPanel';
import { FORECAST_COLUMNS } from '../format';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { ActivityDayRow, Dataset, EssayRow, EssayState, QueueStatRow, ReviewStatsSummaryRow } from '../types';

// ── Review stats (Sprint11_ReviewStats, reworked Sprint12_FSRSAndUXOverhaul) ─
//
// "How did I do" — three rolling-window (day/week/month) cards over
// GET /review-stats/summary. Same apiFetch<Dataset<T>>/isApiError/ErrorCard/
// Skeleton convention. The Sprint10 experiment dashboard that used to sit
// alongside this (GET /experiment/summary, the Classic-vs-FSRS comparison)
// is retired along with the dual-scheduler mechanism — see CLAUDE.md "FSRS
// scheduling".

export const REVIEW_STATS_WINDOW_LABELS: Record<ReviewStatsSummaryRow['period'], string> = {
  day: 'Day',
  week: 'Week',
  month: 'Month',
};

export function ReviewStatsCard({ row }: { row: ReviewStatsSummaryRow }) {
  const figure = (label: string, value: string) => (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>{label}</div>
      <div style={{ fontSize: 20, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
  return (
    <div
      style={{
        background: 'var(--md-sys-color-surface-variant)',
        borderRadius: 12,
        padding: 16,
        flex: '1 1 200px',
        minWidth: 180,
      }}
    >
      <h3 style={{ margin: '0 0 8px' }}>{REVIEW_STATS_WINDOW_LABELS[row.period]}</h3>
      {figure('Cards Seen', String(row.reviews))}
      {figure('Unique Cards Seen', String(row.unique_cards))}
      {figure('New Cards Seen', String(row.new_count))}
      {figure('Recall Rate', row.recall_rate == null ? 'No reviews yet' : `${Math.round(row.recall_rate * 100)}%`)}
      {figure('Orals Taken', String(row.orals_count))}
      {figure('Guided Orals Taken', String(row.guided_orals_count))}
      {figure('Unguided Orals Taken', String(row.unguided_orals_count))}
      <table style={{ width: '100%', marginTop: 12, borderCollapse: 'collapse' }}>
        <tbody>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 14 }}>Again</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.again_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Hard</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.hard_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Good</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.good_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Easy</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.easy_count}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export const statsZoneHeadingStyle: React.CSSProperties = {
  margin: '32px 0 4px',
  fontSize: 16,
  fontWeight: 600,
};

export const statsZoneSubtextStyle: React.CSSProperties = {
  color: 'var(--md-sys-color-on-surface-variant)',
  fontSize: 14,
  margin: '0 0 12px',
};

// Essay traffic-light states, in ladder order — the x-axis of the "Essay
// learning progress" histogram (Sprint14; replaces the 0-4 learning levels).
export const ESSAY_STATE_ORDER: EssayState[] = ['grey', 'yellow', 'green', 'blue', 'violet'];

// Study activity: one stacked column per UTC day (Repeat / Unique / First),
// total height = recalls, recall-rate percentage above each column. Local,
// CSS-only (platform-ui BarChart has no per-bar label slot — see
// Sprint13 10_architecture.json internal_flow step 11). Segment formulas:
// repeat = recalls - unique; unique = unique - first; first = first.
export const ACTIVITY_COLORS = {
  repeat: 'var(--md-sys-color-outline)',
  unique: 'var(--md-sys-color-tertiary, #b5651d)',
  first: 'var(--md-sys-color-primary)',
};

export function DailyActivityChart({ rows }: { rows: ActivityDayRow[] }) {
  // 30 columns overflow narrow screens; open scrolled to the newest day (rows are oldest-first).
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
  }, [rows]);
  const maxRecalls = Math.max(1, ...rows.map(r => r.recalls));
  const barArea = 120;
  const seg = (n: number, color: string, label: string) =>
    n > 0 ? <div title={`${label}: ${n}`} style={{ height: (n / maxRecalls) * barArea, background: color }} /> : null;
  return (
    <div data-testid="daily-activity-chart">
      <div ref={scrollRef} style={{ overflowX: 'auto' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', minWidth: rows.length * 30 }}>
          {rows.map(r => (
            <div
              key={r.date}
              data-testid="activity-column"
              style={{ width: 26, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}
            >
              <div
                data-testid="activity-rate"
                style={{ fontSize: 9, height: 14, color: 'var(--md-sys-color-on-surface-variant)', whiteSpace: 'nowrap' }}
              >
                {r.recall_rate == null ? '—' : `${Math.round(r.recall_rate * 100)}%`}
              </div>
              <div style={{ width: '100%', height: barArea, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                {seg(r.recalls - r.unique_cards_seen, ACTIVITY_COLORS.repeat, 'Repeat')}
                {seg(r.unique_cards_seen - r.first_cards_seen, ACTIVITY_COLORS.unique, 'Unique')}
                {seg(r.first_cards_seen, ACTIVITY_COLORS.first, 'First')}
              </div>
              <div style={{ fontSize: 9, color: 'var(--md-sys-color-on-surface-variant)' }}>{r.date.slice(8)}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ fontSize: 12, marginTop: 8, display: 'flex', gap: 12 }}>
        <span><span style={{ color: ACTIVITY_COLORS.repeat }}>■</span> Repeat</span>
        <span>·</span>
        <span><span style={{ color: ACTIVITY_COLORS.unique }}>■</span> Unique</span>
        <span>·</span>
        <span><span style={{ color: ACTIVITY_COLORS.first }}>■</span> First</span>
      </div>
    </div>
  );
}

export function ReviewStatsView() {
  const navigate = useNavigate();
  const [summaryRows, setSummaryRows] = useState<ReviewStatsSummaryRow[]>([]);
  const [activityRows, setActivityRows] = useState<ActivityDayRow[] | null>(null);
  const [period, setPeriod] = useState<ReviewStatsSummaryRow['period']>('day');
  const [intervalsDataset, setIntervalsDataset] = useState<PlatformDataset | null>(null);
  const [forecastRow, setForecastRow] = useState<(number | null)[] | null>(null);
  const [essays, setEssays] = useState<EssayRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [summaryRes, activityRes, intervalsRes, forecastRes, essaysRes] = await Promise.all([
        apiFetch<Dataset<ReviewStatsSummaryRow>>('/essaycards/review-stats/summary'),
        apiFetch<Dataset<ActivityDayRow>>('/essaycards/review-stats/activity'),
        apiFetch<PlatformDataset>('/essaycards/review-stats/intervals'),
        apiFetch<Dataset<QueueStatRow>>('/essaycards/flashcards/stats'),
        apiFetch<Dataset<EssayRow>>('/essaycards/essays'),
      ]);
      setLoading(false);

      if (isApiError(summaryRes)) {
        setError(summaryRes);
        return;
      }
      setError(null);
      setSummaryRows(summaryRes.rows);
      setActivityRows(isApiError(activityRes) ? null : activityRes.rows);
      setIntervalsDataset(isApiError(intervalsRes) ? null : intervalsRes);
      if (!isApiError(forecastRes)) {
        const byBucket = Object.fromEntries(forecastRes.rows.map(r => [r.bucket, r.count]));
        setForecastRow(FORECAST_COLUMNS.map(c => byBucket[c.key] ?? 0));
      }
      if (!isApiError(essaysRes)) setEssays(essaysRes.rows);
    })();
  }, []);

  const levelHistogramDataset: PlatformDataset = {
    meta: { object_type: 'essay_state_bucket', label: 'Essay Learning Progress', total: ESSAY_STATE_ORDER.length, page: 1, page_size: ESSAY_STATE_ORDER.length, row_actions: [] },
    schema: [
      { key: 'level', label: 'State', type: 'string', sortable: false, filterable: false },
      { key: 'count', label: 'Essays', type: 'number', sortable: false, filterable: false },
    ],
    rows: ESSAY_STATE_ORDER.map(state => ({
      id: state,
      level: state[0].toUpperCase() + state.slice(1),
      count: essays.filter(e => e.essay_state === state).length,
    })),
  };

  return (
    <div style={pageStyle}>
      <h2 className="type-headline" style={{ margin: 0 }}>Stats</h2>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}

      {!loading && !error && (
        <>
          <h3 style={statsZoneHeadingStyle}>Study activity</h3>
          <p style={statsZoneSubtextStyle}>
            Recalls per day over the last 30 days, with the recall rate above each day.
          </p>
          {activityRows
            ? <DailyActivityChart rows={activityRows} />
            : <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>Activity data unavailable.</div>}

          <h3 style={statsZoneHeadingStyle}>Scheduled reviews (forecast)</h3>
          <p style={statsZoneSubtextStyle}>
            When your scheduled cards are predicted to come due next.
          </p>
          <div
            style={{
              background: 'var(--md-sys-color-surface-variant)',
              borderRadius: 'var(--radius-card, 12px)',
              padding: 12,
            }}
          >
            <ForecastGrid rows={[{ label: 'All', values: forecastRow ?? FORECAST_COLUMNS.map(() => null) }]} />
          </div>

          <h3 style={statsZoneHeadingStyle}>Observed recall</h3>
          <p style={statsZoneSubtextStyle}>
            What actually happened over the last day, week or month.
          </p>
          <div role="group" aria-label="Observed recall period" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            {(['day', 'week', 'month'] as const).map(p => (
              <button
                key={p}
                type="button"
                aria-pressed={period === p}
                onClick={() => setPeriod(p)}
                style={period === p ? primaryBtnStyle : btnStyle}
              >
                {REVIEW_STATS_WINDOW_LABELS[p]}
              </button>
            ))}
          </div>
          {summaryRows.find(r => r.period === period) && (
            <ReviewStatsCard row={summaryRows.find(r => r.period === period)!} />
          )}

          <h3 style={statsZoneHeadingStyle}>Scheduled intervals</h3>
          <p style={statsZoneSubtextStyle}>How long your cards are currently scheduled for.</p>
          {intervalsDataset
            ? <BarChart dataset={intervalsDataset} mapping={{ x: 'label', y: 'count', aggregation: 'sum' }} />
            : <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>Interval data unavailable.</div>}

          <h3 style={statsZoneHeadingStyle}>Essay learning progress</h3>
          <p style={statsZoneSubtextStyle}>Essays at each progress state (colours as in the essay list legend).</p>
          <BarChart dataset={levelHistogramDataset} mapping={{ x: 'level', y: 'count', aggregation: 'sum' }} />
        </>
      )}
    </div>
  );
}
