/**
 * FoodTracker — ReportPage (Sprint 06)
 *
 * Route: /food/report
 *
 * Sprint 06 changes from Sprint 05:
 * - NutMetric extended with 'alcohol'.
 * - ALCOHOL_BARS constant added.
 * - YearComboPanel handles metric==='alcohol' (ALCOHOL_BARS, avgKey='alcohol_g_avg').
 * - View selector extended with 'Alcohol (g)' option.
 * - DataTable extended with alcohol branch.
 * - showAvgLine = scope !== 'all_time' (avg line now shown for week and month).
 * - StackedBarPanel used only for all_time scope.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  Line,
  Legend,
} from 'recharts';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Dataset, ApiError } from '@platform-ui/api/types';

// ── Constants ─────────────────────────────────────────────────────────────────

type Scope    = 'all_time' | 'year' | 'month' | 'week';
type Mode     = 'aggregated' | 'daily';
type NutMetric = 'kcal' | 'protein' | 'alcohol';

// Meal-type bar series — same order for all charts
const KCAL_BARS: { key: string; label: string; color: string }[] = [
  { key: 'kcal_breakfast', label: 'Breakfast', color: 'var(--atlas-chart-1)' },
  { key: 'kcal_lunch',     label: 'Lunch',     color: 'var(--atlas-chart-2)' },
  { key: 'kcal_dinner',    label: 'Dinner',    color: 'var(--atlas-chart-3)' },
  { key: 'kcal_snack',     label: 'Snacks',    color: 'var(--atlas-chart-4)' },
  { key: 'kcal_alcohol',   label: 'Drink',     color: 'var(--atlas-chart-5)' },
];

const PROTEIN_BARS: { key: string; label: string; color: string }[] = [
  { key: 'protein_breakfast', label: 'Breakfast', color: 'var(--atlas-chart-1)' },
  { key: 'protein_lunch',     label: 'Lunch',     color: 'var(--atlas-chart-2)' },
  { key: 'protein_dinner',    label: 'Dinner',    color: 'var(--atlas-chart-3)' },
  { key: 'protein_snack',     label: 'Snacks',    color: 'var(--atlas-chart-4)' },
];

const ALCOHOL_BARS: { key: string; label: string; color: string }[] = [
  { key: 'alcohol_g_total', label: 'Alcohol (g)', color: 'var(--atlas-chart-5)' },
];

// ── Scoped style for outline removal ─────────────────────────────────────────

const REPORT_OUTLINE_STYLE = `
.report-table-area *:focus {
  outline: none;
}
.report-table-area button:focus-visible,
.report-table-area select:focus-visible,
.report-table-area input:focus-visible {
  outline: 2px solid var(--md-sys-color-primary);
}
.recharts-wrapper,
.recharts-wrapper *,
.recharts-surface {
  outline: none !important;
}
`;

// ── StackedBarPanel ───────────────────────────────────────────────────────────

interface StackedBarPanelProps {
  dataset:     Dataset;
  metric:      NutMetric;
  onBarClick?: (date: string) => void;
}

function StackedBarPanel({ dataset, metric, onBarClick }: StackedBarPanelProps) {
  const bars = metric === 'kcal' ? KCAL_BARS : metric === 'protein' ? PROTEIN_BARS : ALCOHOL_BARS;
  const totalKey = metric === 'kcal' ? 'kcal_total' : metric === 'protein' ? 'protein_total' : 'alcohol_g_total';
  const unit     = metric === 'kcal' ? 'kcal' : 'g';

  const chartData = dataset.rows.map((row) => {
    const entry: Record<string, unknown> = {
      _id:          String(row['id'] ?? ''),
      bucket_label: String(row['bucket_label'] ?? ''),
    };
    for (const bar of bars) {
      entry[bar.key] = Number(row[bar.key] ?? 0);
    }
    entry[totalKey] = Number(row[totalKey] ?? 0);
    return entry;
  });

  function handleBarClick(dataPoint: Record<string, unknown>) {
    const id = String(dataPoint._id ?? '');
    if (onBarClick && /^\d{4}-\d{2}-\d{2}$/.test(id)) {
      onBarClick(id);
    }
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ReBarChart data={chartData} barSize={20}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
        <XAxis dataKey="bucket_label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(value: number, name: string) => [`${value.toFixed(1)} ${unit}`, name]} />
        <Legend />
        {bars.map((bar) => (
          <Bar
            key={bar.key}
            dataKey={bar.key}
            name={bar.label}
            stackId="a"
            fill={bar.color}
            style={{ cursor: onBarClick ? 'pointer' : 'default' }}
            onClick={handleBarClick}
          />
        ))}
      </ReBarChart>
    </ResponsiveContainer>
  );
}

// ── YearComboPanel ────────────────────────────────────────────────────────────

interface YearComboPanelProps {
  dataset:     Dataset;
  metric:      NutMetric;
  onBarClick?: (date: string) => void;
}

function YearComboPanel({ dataset, metric, onBarClick }: YearComboPanelProps) {
  const bars    = metric === 'kcal' ? KCAL_BARS : metric === 'protein' ? PROTEIN_BARS : ALCOHOL_BARS;
  const avgKey  = metric === 'kcal' ? 'kcal_avg' : metric === 'protein' ? 'protein_avg' : 'alcohol_g_avg';
  const unit    = metric === 'kcal' ? 'kcal' : 'g';

  const chartData = dataset.rows.map((row) => {
    const entry: Record<string, unknown> = {
      _id:          String(row['id'] ?? ''),
      bucket_label: String(row['bucket_label'] ?? ''),
    };
    for (const bar of bars) {
      entry[bar.key] = Number(row[bar.key] ?? 0);
    }
    entry[avgKey] = Number(row[avgKey] ?? 0);
    return entry;
  });

  function handleBarClick(dataPoint: Record<string, unknown>) {
    const id = String(dataPoint._id ?? '');
    if (onBarClick && /^\d{4}-\d{2}-\d{2}$/.test(id)) {
      onBarClick(id);
    }
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} barSize={14}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
        <XAxis dataKey="bucket_label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(value: number, name: string) => [`${value.toFixed(1)} ${unit}`, name]} />
        <Legend />
        {bars.map((bar) => (
          <Bar
            key={bar.key}
            dataKey={bar.key}
            name={bar.label}
            stackId="a"
            fill={bar.color}
            style={{ cursor: onBarClick ? 'pointer' : 'default' }}
            onClick={handleBarClick}
          />
        ))}
        <Line
          type="monotone"
          dataKey={avgKey}
          name="Daily avg"
          stroke="var(--md-sys-color-error)"
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── DataTable ─────────────────────────────────────────────────────────────────

interface DataTableProps {
  dataset: Dataset;
  metric:  NutMetric;
}

function DataTable({ dataset, metric }: DataTableProps) {
  // Build column list based on metric; for alcohol, include avg column only if present in first row
  const hasAlcoholAvg = dataset.rows.length > 0 && 'alcohol_g_avg' in dataset.rows[0];

  const cols =
    metric === 'kcal'
      ? [
          { key: 'bucket_label',   label: 'Date' },
          { key: 'kcal_breakfast', label: 'Breakfast' },
          { key: 'kcal_lunch',     label: 'Lunch' },
          { key: 'kcal_dinner',    label: 'Dinner' },
          { key: 'kcal_snack',     label: 'Snacks' },
          { key: 'kcal_alcohol',   label: 'Drink' },
          { key: 'kcal_total',     label: 'Total' },
        ]
      : metric === 'protein'
      ? [
          { key: 'bucket_label',      label: 'Date' },
          { key: 'protein_breakfast', label: 'Breakfast' },
          { key: 'protein_lunch',     label: 'Lunch' },
          { key: 'protein_dinner',    label: 'Dinner' },
          { key: 'protein_snack',     label: 'Snacks' },
          { key: 'protein_total',     label: 'Total' },
        ]
      : [
          { key: 'bucket_label',   label: 'Date' },
          { key: 'alcohol_g_total', label: 'Alcohol (g)' },
          ...(hasAlcoholAvg ? [{ key: 'alcohol_g_avg', label: 'Avg/day' }] : []),
        ];

  const unit = metric === 'kcal' ? 'kcal' : 'g';

  return (
    <div
      className="report-table-area"
      style={{ overflowX: 'auto', marginTop: 'var(--space-md)' }}
    >
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem' }}>
        <thead>
          <tr>
            {cols.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: '6px 10px',
                  textAlign: 'left',
                  borderBottom: '2px solid var(--md-sys-color-outline)',
                  color: 'var(--md-sys-color-on-surface-variant)',
                  whiteSpace: 'nowrap',
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataset.rows.map((row, i) => (
            <tr
              key={String(row['id'] ?? i)}
              style={{ borderBottom: '1px solid var(--md-sys-color-outline-variant)' }}
            >
              {cols.map((col) => {
                const raw = row[col.key];
                const isNum = col.key !== 'bucket_label';
                const val = isNum ? `${Number(raw ?? 0).toFixed(1)} ${unit}` : String(raw ?? '');
                return (
                  <td
                    key={col.key}
                    style={{
                      padding: '5px 10px',
                      whiteSpace: 'nowrap',
                      color: 'var(--md-sys-color-on-surface)',
                    }}
                  >
                    {val}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── ReportPage ────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const navigate = useNavigate();
  const [scope,          setScope]          = useState<Scope>('week');
  const [mode,           setMode]           = useState<Mode>('daily');
  const [metric,         setMetric]         = useState<NutMetric>('kcal');
  const [currentDataset, setCurrentDataset] = useState<Dataset | null>(null);
  const [reportedDays,   setReportedDays]   = useState<number>(0);
  const [isLoading,      setIsLoading]      = useState(false);
  const [error,          setError]          = useState<ApiError | null>(null);

  const fetchReport = useCallback(async (s: Scope, m: Mode) => {
    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams({ scope: s, mode: m });
    const result = await apiFetch<Dataset & { meta: { reported_days?: number } }>(`/food/report?${params.toString()}`);
    setIsLoading(false);

    if (isApiError(result)) {
      setError(result);
      setCurrentDataset(null);
    } else {
      const ds = result as Dataset & { meta: { reported_days?: number } };
      setCurrentDataset(ds);
      setReportedDays(ds.meta.reported_days ?? 0);
    }
  }, []);

  useEffect(() => {
    fetchReport(scope, mode);
  }, [scope, mode, fetchReport]);

  function handleScopeChange(newScope: Scope) {
    // week only supports daily; reset mode to daily when switching to week
    const newMode: Mode = newScope === 'week' ? 'daily' : mode;
    setScope(newScope);
    setMode(newMode);
  }

  function handleModeChange(newMode: Mode) {
    setMode(newMode);
  }

  const showAvgLine = scope !== 'all_time';

  function handleBarClick(date: string) {
    navigate(`/food/day?date=${date}`);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Scoped style to suppress click outlines on table interaction */}
      <style>{REPORT_OUTLINE_STYLE}</style>

      <div className="page">
        {/* Controls row — all 3 dropdowns equal width, label above */}
        <div
          style={{
            display:      'flex',
            gap:          'var(--space-sm)',
            marginBottom: 'var(--space-md)',
            width:        '100%',
          }}
        >
          {/* Scope */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
            <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Scope
            </label>
            <select
              className="type-body"
              value={scope}
              onChange={(e) => handleScopeChange(e.target.value as Scope)}
              style={{
                width:        '100%',
                padding:      '8px 12px',
                background:   'var(--md-sys-color-surface)',
                border:       '1px solid var(--md-sys-color-outline)',
                borderRadius: 'var(--radius-input, 4px)',
                color:        'var(--md-sys-color-on-surface)',
                cursor:       'pointer',
              }}
            >
              <option value="all_time">All Time</option>
              <option value="year">Last 365 Days</option>
              <option value="month">Last 30 Days</option>
              <option value="week">Last 7 Days</option>
            </select>
          </div>

          {/* Mode — always visible, disabled when scope=week */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
            <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Mode
            </label>
            <select
              className="type-body"
              value={mode}
              disabled={scope === 'week'}
              onChange={(e) => handleModeChange(e.target.value as Mode)}
              style={{
                width:        '100%',
                padding:      '8px 12px',
                background:   'var(--md-sys-color-surface)',
                border:       '1px solid var(--md-sys-color-outline)',
                borderRadius: 'var(--radius-input, 4px)',
                color:        'var(--md-sys-color-on-surface)',
                cursor:       scope === 'week' ? 'not-allowed' : 'pointer',
                opacity:      scope === 'week' ? 0.5 : 1,
              }}
            >
              <option value="daily">Daily</option>
              <option value="aggregated">Aggregated</option>
            </select>
          </div>

          {/* View */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
            <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              View
            </label>
            <select
              className="type-body"
              value={metric}
              onChange={(e) => setMetric(e.target.value as NutMetric)}
              style={{
                width:        '100%',
                padding:      '8px 12px',
                background:   'var(--md-sys-color-surface)',
                border:       '1px solid var(--md-sys-color-outline)',
                borderRadius: 'var(--radius-input, 4px)',
                color:        'var(--md-sys-color-on-surface)',
                cursor:       'pointer',
              }}
            >
              <option value="kcal">Calories (kcal)</option>
              <option value="protein">Protein (g)</option>
              <option value="alcohol">Alcohol (g)</option>
            </select>
          </div>
        </div>

        {/* Chart */}
        <div
          style={{
            background:   'var(--md-sys-color-surface)',
            border:       '1px solid var(--md-sys-color-outline)',
            borderRadius: '8px',
            padding:      'var(--space-md)',
            marginBottom: 'var(--space-md)',
          }}
        >
          {isLoading ? (
            <Skeleton />
          ) : error ? (
            <ErrorCard error={error} />
          ) : currentDataset ? (
            showAvgLine ? (
              <YearComboPanel dataset={currentDataset} metric={metric} onBarClick={handleBarClick} />
            ) : (
              <StackedBarPanel dataset={currentDataset} metric={metric} onBarClick={handleBarClick} />
            )
          ) : null}
        </div>

        {/* Data table */}
        {!isLoading && !error && currentDataset && (
          <DataTable dataset={currentDataset} metric={metric} />
        )}
      </div>
    </>
  );
}
