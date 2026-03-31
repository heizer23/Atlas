/**
 * SwimlaneRenderer — transposed year grid with per-source split cells.
 *
 * Receives 1..4 selected sources. Fetches events for each source in parallel.
 * Renders a single transposed grid (rows=weeks, columns=days Mon..Sun).
 *
 * Each day cell is split into N equal sub-cells — one per source:
 *   1 source  → full cell
 *   2 sources → left half | right half
 *   3 sources → left third | centre third | right third
 *   4 sources → top-left | top-right / bottom-left | bottom-right (2×2)
 *
 * A source's sub-cell always occupies the same positional slot regardless of
 * whether data exists for that date, so colours are spatially consistent.
 * Missing dates render as heat-0 in their slot.
 *
 * Inline implementation — no Platform dependency beyond ErrorCard and Skeleton.
 */

import { useState, useEffect } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { SourceListRow, CalendarEventRow } from './types';

// ── Public props contract ──────────────────────────────────────────────────────

export interface SwimlaneRendererProps {
  sources:    SourceListRow[];
  onDayClick: (row: CalendarEventRow) => void;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const HEAT_COLORS: Record<string, string> = {
  'heat-0': 'var(--md-sys-color-surface-variant)',
  'heat-1': '#c6e48b',
  'heat-2': '#7bc96f',
  'heat-3': '#239a3b',
  'heat-4': '#196127',
};

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOW_LABELS   = ['M','T','W','T','F','S','S'];

const CELL_GAP       = 2;   // px gap between cells
const DOW_LABEL_WIDTH = 16;  // px — fixed left column for day-of-week labels
const MAX_CELL        = 80;  // px — max cell size; prevents cells from growing too large on wide screens

// ── Private helpers ────────────────────────────────────────────────────────────

function buildEventMap(rows: CalendarEventRow[]): Map<string, CalendarEventRow> {
  const map = new Map<string, CalendarEventRow>();
  for (const row of rows) map.set(row.date, row);
  return map;
}

function getIntensityClass(value: number): string {
  if (value === 0)  return 'heat-0';
  if (value <= 25)  return 'heat-1';
  if (value <= 50)  return 'heat-2';
  if (value <= 75)  return 'heat-3';
  return                   'heat-4';
}

interface WeekRow {
  days:       (string | null)[];
  monthLabel: string | null;
}

function localDateStr(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function buildWeekGrid(year: number): WeekRow[] {
  const jan1 = new Date(year, 0, 1);
  const jan1DayOfWeek = (jan1.getDay() + 6) % 7;

  const cells: (string | null)[] = [];
  for (let i = 0; i < jan1DayOfWeek; i++) cells.push(null);

  const d = new Date(year, 0, 1);
  while (d.getFullYear() === year) {
    cells.push(localDateStr(d));
    d.setDate(d.getDate() + 1);
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const weekCount  = cells.length / 7;
  const seenMonths = new Set<number>();
  const rows: WeekRow[] = [];

  for (let w = 0; w < weekCount; w++) {
    const days = cells.slice(w * 7, w * 7 + 7);
    let monthLabel: string | null = null;
    for (const day of days) {
      if (!day) continue;
      const m = parseInt(day.slice(5, 7), 10) - 1;
      if (!seenMonths.has(m)) {
        seenMonths.add(m);
        monthLabel = MONTH_LABELS[m];
        break;
      }
    }
    rows.push({ days, monthLabel });
  }

  return rows;
}

// ── Source fetch state ─────────────────────────────────────────────────────────

interface SourceState {
  loading:  boolean;
  error:    ApiError | null;
  eventMap: Map<string, CalendarEventRow>;
}

// ── DayCell — single day cell with N split sub-cells ──────────────────────────

interface DayCellProps {
  dateStr:      string;
  sources:      SourceListRow[];
  sourceStates: SourceState[];
  onDayClick:   (row: CalendarEventRow) => void;
}

function DayCell({ dateStr, sources, sourceStates, onDayClick }: DayCellProps) {
  const n = sources.length;

  // Always N vertical stripes — one column per source, single row.
  // Never 2×2: that produces a checkerboard pattern across adjacent days.
  const innerGrid: React.CSSProperties = {
    gridTemplateColumns: `repeat(${n}, 1fr)`,
    gridTemplateRows:    '1fr',
  };

  return (
    <div
      style={{
        aspectRatio:  '1',
        borderRadius: 2,
        overflow:     'hidden',
        display:      'grid',
        ...innerGrid,
      }}
    >
      {sources.map((src, si) => {
        const state     = sourceStates[si];
        const row       = state.error ? undefined : state.eventMap.get(dateStr);
        const value     = row?.value ?? 0;
        const color     = HEAT_COLORS[getIntensityClass(value)];
        const clickable = value > 0 && row !== undefined && !state.error;

        return (
          <div
            key={si}
            title={`${src.source_label} — ${dateStr}${row ? `: ${row.label} (${value})` : ': no data'}`}
            onClick={() => { if (clickable && row) onDayClick(row); }}
            style={{
              background: color,
              cursor:     clickable ? 'pointer' : 'default',
            }}
            onMouseEnter={(e) => {
              if (clickable) (e.currentTarget as HTMLElement).style.outline = '1px solid var(--md-sys-color-primary)';
            }}
            onMouseLeave={(e) => {
              if (clickable) (e.currentTarget as HTMLElement).style.outline = '';
            }}
          />
        );
      })}
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function SwimlaneRenderer({ sources, onDayClick }: SwimlaneRendererProps) {
  const year = new Date().getFullYear();

  const [sourceStates, setSourceStates] = useState<SourceState[]>([]);

  useEffect(() => {
    if (sources.length === 0) {
      setSourceStates([]);
      return;
    }

    const initial: SourceState[] = sources.map(() => ({
      loading:  true,
      error:    null,
      eventMap: new Map(),
    }));
    setSourceStates(initial);

    const currentSources = sources;

    sources.forEach((src, i) => {
      const params = new URLSearchParams({
        application:  src.application,
        source_label: src.source_label,
        year:         String(year),
      });

      apiFetch<CalendarEventRow[]>(`/chronicle/calendar/events?${params}`).then((res) => {
        setSourceStates((prev) => {
          if (prev.length !== currentSources.length) return prev;
          const next = [...prev];
          if (isApiError(res)) {
            next[i] = { loading: false, error: res as ApiError, eventMap: new Map() };
          } else {
            next[i] = { loading: false, error: null, eventMap: buildEventMap(res as CalendarEventRow[]) };
          }
          return next;
        });
      });
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sources, year]);

  const allResolved =
    sourceStates.length === sources.length &&
    sourceStates.every((s) => !s.loading);

  if (!allResolved) return <Skeleton />;

  const weeks      = buildWeekGrid(year);
  const weekCount  = weeks.length;

  // Surface per-source errors above the grid
  const sourceErrors = sourceStates
    .map((s, i) => s.error ? { src: sources[i], error: s.error } : null)
    .filter((e): e is { src: SourceListRow; error: ApiError } => e !== null);

  // Transposed layout: columns = weeks (time flows left→right), rows = days of week (Mon–Sun).
  // Build flat cell list for CSS grid auto-placement:
  //   Row 0 : [corner] [month label per week…]
  //   Rows 1–7 : [dow label] [day cell per week…]
  const gridItems: React.ReactNode[] = [];

  // Month label row
  gridItems.push(<div key="corner" />);
  weeks.forEach((week, wi) => {
    gridItems.push(
      <div
        key={`month-${wi}`}
        style={{
          fontSize:   '0.6rem',
          color:      'var(--md-sys-color-on-surface-variant)',
          userSelect: 'none',
          overflow:   'hidden',
          whiteSpace: 'nowrap',
        }}
      >
        {week.monthLabel ?? ''}
      </div>
    );
  });

  // Day-of-week rows
  DOW_LABELS.forEach((lbl, dow) => {
    gridItems.push(
      <div
        key={`dow-${dow}`}
        style={{
          fontSize:   '0.6rem',
          color:      'var(--md-sys-color-on-surface-variant)',
          textAlign:  'center',
          userSelect: 'none',
          alignSelf:  'center',
        }}
      >
        {lbl}
      </div>
    );
    weeks.forEach((week, wi) => {
      const dateStr = week.days[dow];
      gridItems.push(
        dateStr ? (
          <DayCell
            key={`${wi}-${dow}`}
            dateStr={dateStr}
            sources={sources}
            sourceStates={sourceStates}
            onDayClick={onDayClick}
          />
        ) : (
          <div
            key={`${wi}-${dow}-empty`}
            style={{ aspectRatio: '1', background: 'transparent', borderRadius: 2 }}
          />
        )
      );
    });
  });

  return (
    <div style={{ width: '100%' }}>

      {/* Per-source error banners */}
      {sourceErrors.map(({ src, error }) => (
        <div key={`${src.application}::${src.source_label}`} style={{ marginBottom: 8 }}>
          <ErrorCard error={error} />
        </div>
      ))}

      {/* Transposed heatmap grid */}
      <div
        style={{
          display:             'grid',
          gridTemplateColumns: `${DOW_LABEL_WIDTH}px repeat(${weekCount}, minmax(0, ${MAX_CELL}px))`,
          gap:                 CELL_GAP,
        }}
      >
        {gridItems}
      </div>
    </div>
  );
}
