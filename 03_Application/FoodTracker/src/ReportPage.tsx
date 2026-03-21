/**
 * FoodTracker — ReportPage (Sprint 02)
 *
 * Route: /food/report
 *
 * Owns all page-level state:
 *   scope, period_key, mode, navStack, topMetric, bottomMetric,
 *   currentDataset, isLoading, error
 *
 * Fetches GET /api/food/report on mount and whenever scope/period_key/mode changes.
 * Metric changes within the current dataset do NOT trigger a new fetch.
 *
 * Drill navigation:
 *   Clicking a bar in aggregated mode pushes current state onto navStack
 *   and navigates to the drilled period. Drill is only available in aggregated mode.
 *   Drill targets: all_time→year, year→month, month→week.
 *   Week is the deepest scope.
 *
 * Back navigation:
 *   Pops from navStack and navigates to the previous scope/period_key/mode.
 *
 * Scope selector:
 *   Always navigates to the system-current period for the selected scope.
 *   Clears navStack.
 *
 * Mode selector:
 *   Hidden (not disabled) when scope=week (week supports daily only).
 */

import { useState, useEffect, useCallback } from 'react';
import {
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Dataset, ApiError } from '@platform-ui/api/types';

// ── Constants ─────────────────────────────────────────────────────────────────

// Metric options in display order as specified in the sprint definition
const METRICS: { key: string; label: string }[] = [
  { key: 'protein_g', label: 'Protein (g)' },
  { key: 'kcal',      label: 'Calories (kcal)' },
  { key: 'carbs_g',   label: 'Carbohydrates (g)' },
  { key: 'fat_g',     label: 'Fat (g)' },
  { key: 'fiber_g',   label: 'Fiber (g)' },
];

// Drill target scope for each current scope (aggregated mode only)
const DRILL_TARGET: Record<string, string> = {
  all_time: 'year',
  year:     'month',
  month:    'week',
};

// ── Types ─────────────────────────────────────────────────────────────────────

type Scope = 'all_time' | 'year' | 'month' | 'week';
type Mode  = 'aggregated' | 'daily';

interface NavEntry {
  scope:      Scope;
  period_key: string | null;
  mode:       Mode;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Returns the period_key for the system-current period of the given scope.
 * Uses browser Date — consistent with "server time for this slice" because
 * the user's local date and server date are expected to be the same calendar date.
 * scope=all_time → null (no period_key required).
 */
function _currentPeriodKey(scope: string): string | null {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm   = String(now.getMonth() + 1).padStart(2, '0');

  if (scope === 'all_time') return null;
  if (scope === 'year')     return String(yyyy);
  if (scope === 'month')    return `${yyyy}-${mm}`;
  if (scope === 'week') {
    // ISO week: compute the ISO year and week number
    // Algorithm: find the Thursday of the week; that determines the ISO year/week
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    // Set to Thursday of the current week (Mon=0 baseline)
    const dayOfWeek = (d.getDay() + 6) % 7; // Mon=0 … Sun=6
    d.setDate(d.getDate() - dayOfWeek + 3);  // move to Thursday
    const jan4     = new Date(d.getFullYear(), 0, 4); // Jan 4 is always in week 1
    const isoYear  = d.getFullYear();
    const weekNum  = Math.round(((d.getTime() - jan4.getTime()) / 86400000 + (((jan4.getDay() + 6) % 7) - 3)) / 7) + 1;
    return `${isoYear}-W${String(weekNum).padStart(2, '0')}`;
  }
  return null;
}

// ── ChartPanel ────────────────────────────────────────────────────────────────

interface ChartPanelProps {
  dataset:       Dataset;
  defaultMetric: string;
  onDrillDown:   (bucketId: string) => void;
  isDrillable:   boolean;
}

/**
 * Renders one chart panel with an independent metric selector and a BarChart.
 * Local state: selectedMetric (initialised from defaultMetric prop once).
 *
 * Bar click in aggregated mode calls onDrillDown with the bucket id.
 * The bucket id is stored in the Dataset row as `id`; the x-axis displays `bucket_label`.
 * recharts passes the active bar's full data entry to the onClick handler, so we
 * read the `id` field from the payload to get the bucket id.
 */
export function ChartPanel({ dataset, defaultMetric, onDrillDown, isDrillable }: ChartPanelProps) {
  const [selectedMetric, setSelectedMetric] = useState(defaultMetric);

  const metricLabel = METRICS.find(m => m.key === selectedMetric)?.label ?? selectedMetric;

  // Build chart data array from dataset rows
  const chartData = dataset.rows.map(row => ({
    id:           String(row['id'] ?? ''),
    bucket_label: String(row['bucket_label'] ?? ''),
    value:        Number(row[selectedMetric] ?? 0),
  }));

  function handleBarClick(data: { id?: string; bucket_label?: string } | null) {
    if (!isDrillable || !data) return;
    const bucketId = data.id;
    if (bucketId) {
      onDrillDown(bucketId);
    }
  }

  return (
    <div
      style={{
        background:   'var(--md-sys-color-surface)',
        border:       '1px solid var(--md-sys-color-outline)',
        borderRadius: '8px',
        padding:      'var(--space-md)',
        marginBottom: 'var(--space-md)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
        <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          Metric
        </label>
        <select
          className="type-body"
          value={selectedMetric}
          onChange={e => setSelectedMetric(e.target.value)}
          style={{
            padding:      '4px 8px',
            background:   'var(--md-sys-color-surface)',
            border:       '1px solid var(--md-sys-color-outline)',
            borderRadius: '4px',
            color:        'var(--md-sys-color-on-surface)',
            cursor:       'pointer',
          }}
        >
          {METRICS.map(m => (
            <option key={m.key} value={m.key}>{m.label}</option>
          ))}
        </select>
        {isDrillable && (
          <span className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', marginLeft: 'auto' }}>
            Click a bar to drill down
          </span>
        )}
      </div>

      <p className="type-title" style={{ margin: '0 0 var(--space-xs)', color: 'var(--md-sys-color-on-surface)' }}>
        {metricLabel}
      </p>

      <ResponsiveContainer width="100%" height={260}>
        <ReBarChart data={chartData} onClick={isDrillable ? (e) => handleBarClick(e?.activePayload?.[0]?.payload ?? null) : undefined}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
          <XAxis dataKey="bucket_label" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number) => [value.toFixed(1), metricLabel]}
            labelFormatter={(label) => `${label}`}
          />
          <Bar
            dataKey="value"
            fill="var(--atlas-chart-1)"
            cursor={isDrillable ? 'pointer' : 'default'}
          />
        </ReBarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── ReportPage ────────────────────────────────────────────────────────────────

/**
 * Top-level report page component.
 *
 * Page-level state:
 *   scope        — current scope (all_time | year | month | week)
 *   period_key   — current period identifier, null for all_time
 *   mode         — aggregated | daily
 *   navStack     — back-navigation history entries
 *   topMetric    — selected metric for the top chart (default: protein_g)
 *   bottomMetric — selected metric for the bottom chart (default: kcal)
 *   currentDataset — fetched Dataset, null while loading or before first fetch
 *   isLoading    — true during in-flight request
 *   error        — ApiError if the last request failed
 *
 * Fetch triggers: scope, period_key, mode changes.
 * Metric changes do NOT trigger a fetch.
 */
export default function ReportPage() {
  const [scope,          setScope]          = useState<Scope>('month');
  const [periodKey,      setPeriodKey]      = useState<string | null>(() => _currentPeriodKey('month'));
  const [mode,           setMode]           = useState<Mode>('daily');
  const [navStack,       setNavStack]       = useState<NavEntry[]>([]);
  const [currentDataset, setCurrentDataset] = useState<Dataset | null>(null);
  const [isLoading,      setIsLoading]      = useState(false);
  const [error,          setError]          = useState<ApiError | null>(null);

  // Fetch on scope/period_key/mode change.
  // topMetric and bottomMetric are intentionally NOT in this dependency list.
  const fetchReport = useCallback(async (s: Scope, pk: string | null, m: Mode) => {
    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams({ scope: s, mode: m });
    if (pk !== null) params.set('period_key', pk);

    const result = await apiFetch<Dataset>(`/food/report?${params.toString()}`);
    setIsLoading(false);

    if (isApiError(result)) {
      setError(result);
      setCurrentDataset(null);
    } else {
      setCurrentDataset(result as Dataset);
    }
  }, []);

  useEffect(() => {
    fetchReport(scope, periodKey, mode);
  }, [scope, periodKey, mode, fetchReport]);

  // ── Scope selector handler ─────────────────────────────────────────────────
  // Always navigates to system-current period for the chosen scope.
  // Clears navStack.
  function handleScopeChange(newScope: Scope) {
    const newPk   = _currentPeriodKey(newScope);
    const newMode: Mode = newScope === 'week' ? 'daily' : mode;
    setNavStack([]);
    setScope(newScope);
    setPeriodKey(newPk);
    setMode(newMode);
  }

  // ── Mode selector handler ──────────────────────────────────────────────────
  function handleModeChange(newMode: Mode) {
    setMode(newMode);
  }

  // ── Drill down handler ─────────────────────────────────────────────────────
  // Only available in aggregated mode. Pushes current state onto navStack.
  function handleDrillDown(bucketId: string) {
    if (mode !== 'aggregated') return;
    const targetScope = DRILL_TARGET[scope] as Scope | undefined;
    if (!targetScope) return;  // week is deepest; no further drill

    // Push current state for back navigation
    setNavStack(prev => [...prev, { scope, period_key: periodKey, mode }]);

    // Navigate to drilled scope+period
    const targetMode: Mode = targetScope === 'week' ? 'daily' : 'aggregated';
    setScope(targetScope);
    setPeriodKey(bucketId);
    setMode(targetMode);
  }

  // ── Back handler ───────────────────────────────────────────────────────────
  // Pops from navStack and restores previous scope/period/mode.
  function handleBack() {
    if (navStack.length === 0) return;
    const prev = navStack[navStack.length - 1];
    setNavStack(ns => ns.slice(0, -1));
    setScope(prev.scope);
    setPeriodKey(prev.period_key);
    setMode(prev.mode);
  }

  const isDrillable = mode === 'aggregated' && scope in DRILL_TARGET;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="type-display">Report</h1>
      </div>

      {/* Controls row */}
      <div
        style={{
          display:      'flex',
          flexWrap:     'wrap',
          gap:          'var(--space-sm)',
          alignItems:   'center',
          marginBottom: 'var(--space-md)',
        }}
      >
        {/* Back button */}
        {navStack.length > 0 && (
          <button
            className="btn-outlined"
            onClick={handleBack}
            disabled={isLoading}
          >
            ← Back
          </button>
        )}

        {/* Scope selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
            Scope
          </label>
          <select
            className="type-body"
            value={scope}
            onChange={e => handleScopeChange(e.target.value as Scope)}
            style={{
              padding:      '4px 8px',
              background:   'var(--md-sys-color-surface)',
              border:       '1px solid var(--md-sys-color-outline)',
              borderRadius: '4px',
              color:        'var(--md-sys-color-on-surface)',
              cursor:       'pointer',
            }}
          >
            <option value="all_time">All Time</option>
            <option value="year">Current Year</option>
            <option value="month">Current Month</option>
            <option value="week">Current Week</option>
          </select>
        </div>

        {/* Mode selector — hidden when scope=week */}
        {scope !== 'week' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Mode
            </label>
            <select
              className="type-body"
              value={mode}
              onChange={e => handleModeChange(e.target.value as Mode)}
              style={{
                padding:      '4px 8px',
                background:   'var(--md-sys-color-surface)',
                border:       '1px solid var(--md-sys-color-outline)',
                borderRadius: '4px',
                color:        'var(--md-sys-color-on-surface)',
                cursor:       'pointer',
              }}
            >
              <option value="daily">Daily</option>
              <option value="aggregated">Aggregated</option>
            </select>
          </div>
        )}

        {/* Period label from dataset */}
        {currentDataset && (
          <span
            className="type-label"
            style={{ color: 'var(--md-sys-color-on-surface-variant)', marginLeft: 'auto' }}
          >
            {currentDataset.meta.label}
          </span>
        )}
      </div>

      {/* Loading / error / charts */}
      {isLoading ? (
        <Skeleton />
      ) : error ? (
        <ErrorCard error={error} />
      ) : currentDataset ? (
        <>
          {/* Top chart — default metric: protein_g */}
          <ChartPanel
            dataset={currentDataset}
            defaultMetric="protein_g"
            onDrillDown={handleDrillDown}
            isDrillable={isDrillable}
          />

          {/* Bottom chart — default metric: kcal */}
          <ChartPanel
            dataset={currentDataset}
            defaultMetric="kcal"
            onDrillDown={handleDrillDown}
            isDrillable={isDrillable}
          />
        </>
      ) : null}
    </div>
  );
}
