

// Interval forecast columns. Keys/edges mirror the backend /stats forward
// bands (STATS_BUCKETS minus due_now); `maxIntervalMs` is the closed upper
// edge of each band. Last column has no upper edge.
export const FORECAST_COLUMNS: { key: string; label: string; maxIntervalMs: number | null }[] = [
  { key: 'within_10_min',  label: '≤10m', maxIntervalMs: 10 * 60_000 },
  { key: 'within_1_day',   label: '<1d',  maxIntervalMs: 24 * 60 * 60_000 },
  { key: 'within_7_days',  label: '<7d',  maxIntervalMs: 7 * 24 * 60 * 60_000 },
  { key: 'within_30_days', label: '<30d', maxIntervalMs: 30 * 24 * 60 * 60_000 },
  { key: 'within_90_days', label: '<3mo', maxIntervalMs: 90 * 24 * 60 * 60_000 },
  { key: 'beyond_90_days', label: '≥3mo', maxIntervalMs: null },
];

// Compact human interval for the review-screen diagnostics frame.
export function formatInterval(seconds: number | null): string {
  if (seconds == null) return 'new card';
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  const m = s / 60;
  if (m < 90) return `${Math.round(m)}m`;
  const h = m / 60;
  if (h < 36) return `${Math.round(h)}h`;
  const d = h / 24;
  if (d < 60) return `${Math.round(d)}d`;
  return `${Math.round(d / 30)}mo`;
}
