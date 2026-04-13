/**
 * SeriesListPage — list all numeric series with time-proportional SVG sparkline,
 * min/max values, and current (latest) value.
 *
 * Custom list component — NOT standard platform TableView.
 * sparkline_points is a JSON-encoded [{v: number, ts: number}] array; parsed here.
 * ts is Unix epoch milliseconds — used for time-proportional x-axis positioning.
 * Row click navigates to /series/:label_id (detail page).
 * '+' button navigates to /series/new (creation mode in SeriesDetailPage).
 *
 * Sprint03 changes:
 *   - Replaced recharts InlineSparkline with custom SVG component
 *   - sparkline_values → sparkline_points (time-proportional coordinates)
 *   - 4-column row layout: label | sparkline | min/max | current value
 *   - min_value and max_value columns added
 *
 * Source of truth: Sprint03_Chronos&UXpt2/10_architecture.json §internal_flow[7,8]
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Dataset } from '@platform-ui/api/types';

// ── Types ──────────────────────────────────────────────────────────────────────

interface SparkPoint {
  v: number;
  ts: number; // Unix epoch milliseconds
}

interface SeriesRow {
  id: string;
  label_name: string;
  latest_value: number | null;
  sparkline_points: string; // JSON-encoded SparkPoint[]
  min_value: number | null;
  max_value: number | null;
}

// ── Time-proportional SVG sparkline ───────────────────────────────────────────
// Architecture: Sprint03/10_architecture.json §internal_flow[7] (list_row_layout)
// Edge cases: 0 points → null; 1 point → centered dot; identical values → midline;
//             identical timestamps → centered x.

const SPARK_W = 100;
const SPARK_H = 28;

function InlineSparkline({
  points,
  minVal,
  maxVal,
}: {
  points: SparkPoint[];
  minVal: number | null;
  maxVal: number | null;
}) {
  if (points.length === 0) {
    return (
      <span style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: '0.8rem' }}>
        —
      </span>
    );
  }

  // Single point — render a centered dot
  if (points.length === 1) {
    return (
      <svg width="100%" height={SPARK_H} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} preserveAspectRatio="none">
        <circle cx={SPARK_W / 2} cy={SPARK_H / 2} r={2} style={{ fill: 'var(--md-sys-color-primary)' }} />
      </svg>
    );
  }

  const tsMin = Math.min(...points.map(p => p.ts));
  const tsMax = Math.max(...points.map(p => p.ts));
  const tsRange = tsMax - tsMin;

  const effectiveMin = minVal ?? Math.min(...points.map(p => p.v));
  const effectiveMax = maxVal ?? Math.max(...points.map(p => p.v));
  const valRange = effectiveMax - effectiveMin;

  const toX = (ts: number): number =>
    tsRange === 0 ? SPARK_W / 2 : (ts - tsMin) / tsRange * SPARK_W;

  const toY = (v: number): number =>
    valRange === 0 ? SPARK_H / 2 : (1 - (v - effectiveMin) / valRange) * SPARK_H;

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.ts).toFixed(2)} ${toY(p.v).toFixed(2)}`)
    .join(' ');

  return (
    <svg width="100%" height={SPARK_H} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} preserveAspectRatio="none">
      <path d={pathD} style={{ fill: 'none', stroke: 'var(--md-sys-color-primary)' }} strokeWidth="1.5" />
    </svg>
  );
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function SeriesListPage() {
  const navigate = useNavigate();

  const [rows, setRows]       = useState<SeriesRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await apiFetch<Dataset>('/series');
    if (isApiError(result)) {
      setError(result.error.message);
    } else {
      setRows(result.rows as SeriesRow[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function parseSparkPoints(raw: string): SparkPoint[] {
    try { return JSON.parse(raw) as SparkPoint[]; }
    catch { return []; }
  }

  function fmtValue(v: number | null): string {
    if (v === null || v === undefined) return '—';
    return v.toLocaleString();
  }

  return (
    <div style={{ padding: '1rem', maxWidth: '900px' }}>
      <style>{`
        .ns-row {
          display: grid;
          grid-template-columns: 140px 56px minmax(0, 1fr) 72px;
          align-items: center;
          gap: 0.75rem;
          padding: 0.6rem 1rem;
          margin-bottom: 0.4rem;
          background: var(--md-sys-color-surface);
          border-radius: 8px;
          cursor: pointer;
          border: 1px solid var(--md-sys-color-outline-variant);
          box-sizing: border-box;
        }
        @media (max-width: 540px) {
          .ns-row {
            grid-template-columns: 5.5rem 56px minmax(0, 1fr) 64px;
          }
        }
      `}</style>

      {/* Page header with + button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>Numeric Series</h2>
        <button
          onClick={() => navigate('/series/new')}
          style={{
            fontSize: '1.4rem',
            lineHeight: 1,
            padding: '0.2rem 0.6rem',
            borderRadius: '6px',
            cursor: 'pointer',
            background: 'var(--md-sys-color-primary, #7c6af5)',
            color: 'var(--md-sys-color-on-primary, #fff)',
            border: 'none',
          }}
          title="Add series"
        >
          +
        </button>
      </div>

      {/* List */}
      {loading && <Skeleton />}
      {error && (
        <ErrorCard error={{ error: { code: 'LOAD_ERROR', message: error, request_id: '' } }} />
      )}

      {!loading && !error && rows.length === 0 && (
        <p style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>No series yet. Use + to add one.</p>
      )}

      {!loading && !error && rows.map((row) => {
        const sparkPoints = parseSparkPoints(row.sparkline_points);
        return (
          <div
            key={row.id}
            onClick={() => navigate(`/series/${row.id}`)}
            className="ns-row"
          >
            {/* Column 1: label */}
            <span style={{ fontWeight: 500, color: 'var(--md-sys-color-on-surface)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.label_name}
            </span>

            {/* Column 2: min / max stacked (left of sparkline) */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '1px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--md-sys-color-on-surface-variant)', lineHeight: 1.2 }}>
                {fmtValue(row.max_value)}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--md-sys-color-on-surface-variant)', lineHeight: 1.2 }}>
                {fmtValue(row.min_value)}
              </span>
            </div>

            {/* Column 3: sparkline */}
            <div className="ns-spark" style={{ width: '100%', height: '28px' }}>
              <InlineSparkline
                points={sparkPoints}
                minVal={row.min_value}
                maxVal={row.max_value}
              />
            </div>

            {/* Column 4: current value */}
            <span style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--md-sys-color-on-surface-variant)' }}>
              {fmtValue(row.latest_value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
