/**
 * HeatmapRenderer — inline calendar heatmap for a single (application, source_label).
 *
 * Fetches events from GET /api/chronicle/calendar/events for the current year.
 * Renders a 52-column x 7-row grid (week columns, Mon-Sun rows).
 * Missing days render as value=0 (lightest shade, no click interaction).
 * Days with value > 0 are clickable — calls onDayClick with the CalendarEventRow.
 *
 * Intensity levels:
 *   0        → heat-0 (no data)
 *   1–25     → heat-1
 *   26–50    → heat-2
 *   51–75    → heat-3
 *   76–100   → heat-4
 *
 * Inline implementation — no Platform dependency. Extraction deferred.
 */

import { useState, useEffect } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { CalendarEventRow } from './types';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Props {
  application:  string;
  source_label: string;
  onDayClick:   (row: CalendarEventRow) => void;
}

// ── Intensity helpers ──────────────────────────────────────────────────────────

function intensityClass(value: number): string {
  if (value === 0)          return 'heat-0';
  if (value <= 25)          return 'heat-1';
  if (value <= 50)          return 'heat-2';
  if (value <= 75)          return 'heat-3';
  return                           'heat-4';
}

const HEAT_COLORS: Record<string, string> = {
  'heat-0': 'var(--md-sys-color-surface-variant)',
  'heat-1': '#c6e48b',
  'heat-2': '#7bc96f',
  'heat-3': '#239a3b',
  'heat-4': '#196127',
};

// ── Calendar grid builder ──────────────────────────────────────────────────────

/**
 * Builds a 2D array [week][dayOfWeek] of ISO date strings for the given year.
 * dayOfWeek: 0=Monday, 6=Sunday.
 * Cells before Jan 1 and after Dec 31 are null (padding).
 */
function buildYearGrid(year: number): (string | null)[][] {
  const jan1 = new Date(year, 0, 1);
  // getDay(): 0=Sun, 1=Mon ... 6=Sat → convert to Mon=0 ... Sun=6
  const jan1DayOfWeek = (jan1.getDay() + 6) % 7;

  // Total cells = 53 weeks x 7 days (enough to cover any year)
  const cells: (string | null)[] = [];
  // Pad start
  for (let i = 0; i < jan1DayOfWeek; i++) cells.push(null);
  // Fill year days
  const d = new Date(year, 0, 1);
  while (d.getFullYear() === year) {
    cells.push(d.toISOString().slice(0, 10));
    d.setDate(d.getDate() + 1);
  }
  // Pad end to full weeks
  while (cells.length % 7 !== 0) cells.push(null);

  // Reshape into weeks
  const weeks: (string | null)[][] = [];
  for (let w = 0; w < cells.length / 7; w++) {
    weeks.push(cells.slice(w * 7, w * 7 + 7));
  }
  return weeks;
}

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOW_LABELS   = ['Mon','','Wed','','Fri','','Sun'];

// ── Component ──────────────────────────────────────────────────────────────────

export default function HeatmapRenderer({ application, source_label, onDayClick }: Props) {
  const year = new Date().getFullYear();

  const [eventMap, setEventMap] = useState<Map<string, CalendarEventRow>>(new Map());
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<ApiError | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      application,
      source_label,
      year: String(year),
    });

    apiFetch<CalendarEventRow[]>(`/chronicle/calendar/events?${params}`).then((res) => {
      if (isApiError(res)) {
        setError(res);
      } else {
        const map = new Map<string, CalendarEventRow>();
        for (const row of res as CalendarEventRow[]) {
          map.set(row.date, row);
        }
        setEventMap(map);
      }
      setLoading(false);
    });
  }, [application, source_label, year]);

  if (loading) return <Skeleton />;
  if (error)   return <ErrorCard error={error} />;

  const weeks = buildYearGrid(year);

  // Build month label positions (week index of first occurrence of each month)
  const monthWeekIndex: Record<number, number> = {};
  weeks.forEach((week, wi) => {
    for (const cell of week) {
      if (!cell) continue;
      const m = parseInt(cell.slice(5, 7), 10) - 1;
      if (!(m in monthWeekIndex)) {
        monthWeekIndex[m] = wi;
      }
    }
  });

  const cellSize = 12;
  const cellGap  = 2;
  const unit     = cellSize + cellGap;

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'inline-block', paddingBottom: 'var(--space-sm)' }}>
        {/* Month labels row */}
        <div style={{ display: 'flex', marginLeft: 28, marginBottom: 4 }}>
          {weeks.map((_, wi) => {
            const monthIdx = Object.entries(monthWeekIndex).find(([, idx]) => idx === wi);
            return (
              <div
                key={wi}
                style={{
                  width:     cellSize,
                  marginRight: cellGap,
                  fontSize: '0.65rem',
                  color: 'var(--md-sys-color-on-surface-variant)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                }}
              >
                {monthIdx ? MONTH_LABELS[parseInt(monthIdx[0], 10)] : ''}
              </div>
            );
          })}
        </div>

        {/* Grid rows (days of week) */}
        <div style={{ display: 'flex' }}>
          {/* Day-of-week labels */}
          <div style={{ marginRight: 4, display: 'flex', flexDirection: 'column', gap: cellGap }}>
            {DOW_LABELS.map((lbl, i) => (
              <div
                key={i}
                style={{
                  height:   cellSize,
                  fontSize: '0.6rem',
                  color: 'var(--md-sys-color-on-surface-variant)',
                  lineHeight: `${cellSize}px`,
                  textAlign: 'right',
                  width: 24,
                }}
              >
                {lbl}
              </div>
            ))}
          </div>

          {/* Week columns */}
          <div style={{ display: 'flex', gap: cellGap }}>
            {weeks.map((week, wi) => (
              <div key={wi} style={{ display: 'flex', flexDirection: 'column', gap: cellGap }}>
                {week.map((dateStr, di) => {
                  if (!dateStr) {
                    return (
                      <div
                        key={di}
                        style={{ width: cellSize, height: cellSize, borderRadius: 2, background: 'transparent' }}
                      />
                    );
                  }
                  const row   = eventMap.get(dateStr);
                  const value = row?.value ?? 0;
                  const cls   = intensityClass(value);
                  const color = HEAT_COLORS[cls];
                  const clickable = value > 0 && row !== undefined;

                  return (
                    <div
                      key={di}
                      title={`${dateStr}${row ? `: ${row.label} (${value})` : ': no data'}`}
                      onClick={() => { if (clickable && row) onDayClick(row); }}
                      style={{
                        width:        cellSize,
                        height:       cellSize,
                        borderRadius: 2,
                        background:   color,
                        cursor:       clickable ? 'pointer' : 'default',
                        boxSizing:    'border-box',
                        border:       clickable ? '1px solid transparent' : 'none',
                      }}
                      onMouseEnter={(e) => {
                        if (clickable) (e.currentTarget as HTMLElement).style.border = '1px solid var(--md-sys-color-primary)';
                      }}
                      onMouseLeave={(e) => {
                        if (clickable) (e.currentTarget as HTMLElement).style.border = '1px solid transparent';
                      }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
