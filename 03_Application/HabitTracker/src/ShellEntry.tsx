/**
 * HabitTracker ShellEntry — Sprint 01
 *
 * Views:
 *   /habittracker                     -> DailyReviewView (today)
 *   /habittracker/review/:date        -> DailyReviewView (explicit date)
 *   /habittracker/habits              -> HabitDefinitionsView
 *   /habittracker/reports             -> ReportsView
 *
 * Daily Review's debounced-draft-save / immediate-confirm / flush-on-unmount
 * behavior implements 10_architecture.json §internal_flow step 12 exactly.
 * Reports' grid/date-column drill-through implements step 13.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Dataset<T> {
  meta: { object_type: string; total: number };
  rows: T[];
}

type DayStatus = 'unreviewed' | 'draft' | 'confirmed';

interface ReviewHabitEntry {
  habit_id: string;
  name: string;
  description: string | null;
  display_order: number;
  checked: boolean;
}

interface ReviewRow extends Row {
  review_date: string;
  status: DayStatus;
  confirmed_at: string | null;
  habits: ReviewHabitEntry[];
}

interface HabitRow extends Row {
  id: string;
  name: string;
  description: string | null;
  default_checked: boolean;
  display_order: number;
  active_from: string;
  end_date: string | null;
}

type CellState = 'completed' | 'not_completed' | 'not_active' | 'unreviewed';

interface ReportCell {
  date: string;
  state: CellState;
}

interface ReportRow extends Row {
  habit_id: string;
  name: string;
  description: string | null;
  display_order: number;
  cells: ReportCell[];
  eligible_confirmed_days: number;
  completed_count: number;
  rate: number | null;
}

interface PeriodSummary {
  period: 'week' | 'month';
  anchor_date: string;
  period_start: string;
  period_end: string;
  dates: string[];
  confirmed_days: number;
  elapsed_days: number;
}

interface ReportsResponse extends Dataset<ReportRow> {
  period_summary: PeriodSummary;
}

const DRAFT_DEBOUNCE_MS = 400;

// ── Small shared pieces ────────────────────────────────────────────────────────

const pageStyle: React.CSSProperties = { padding: 16, maxWidth: 680, margin: '0 auto' };

const btnStyle: React.CSSProperties = {
  padding: '8px 14px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
  fontSize: 14,
};

const primaryBtnStyle: React.CSSProperties = {
  ...btnStyle,
  background: '#2a7a3b',
  color: '#fff',
  border: '1px solid #2a7a3b',
  fontWeight: 600,
};

function todayISO(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function DayStatusBadge({ status }: { status: DayStatus }) {
  const style: Record<DayStatus, React.CSSProperties> = {
    unreviewed: { background: '#eee', color: '#666' },
    draft: { background: '#fdf0cc', color: '#8a6300' },
    confirmed: { background: '#dcf3df', color: '#1d6b2f' },
  };
  const label: Record<DayStatus, string> = {
    unreviewed: 'Not reviewed yet',
    draft: 'Draft — not confirmed',
    confirmed: 'Confirmed',
  };
  return (
    <span
      style={{
        ...style[status],
        padding: '4px 10px',
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
        display: 'inline-block',
      }}
    >
      {label[status]}
    </span>
  );
}

// ── Daily Review View ────────────────────────────────────────────────────────

function DailyReviewView() {
  const { date: dateParam } = useParams<{ date?: string }>();
  const navigate = useNavigate();
  const date = dateParam ?? todayISO();

  const [review, setReview] = useState<ReviewRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const debounceRef = useRef<number | undefined>(undefined);
  const pendingResultsRef = useRef<{ habit_id: string; checked: boolean }[] | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await apiFetch<Dataset<ReviewRow>>(`/habittracker/reviews/${date}`);
    setLoading(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setReview(res.rows[0]);
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const save = useCallback(async (status: 'draft' | 'confirmed', habitResults: { habit_id: string; checked: boolean }[]) => {
    setSaving(true);
    const res = await apiFetch<Dataset<ReviewRow>>(`/habittracker/reviews/${date}`, {
      method: 'PUT',
      body: JSON.stringify({ status, habit_results: habitResults }),
    });
    setSaving(false);
    pendingResultsRef.current = null;
    if (!isApiError(res)) setReview(res.rows[0]);
  }, [date]);

  // Flush any pending debounced draft save immediately on navigation away /
  // unmount — no edit is ever silently lost (internal_flow step 12).
  useEffect(() => {
    return () => {
      window.clearTimeout(debounceRef.current);
      if (pendingResultsRef.current) {
        apiFetch(`/habittracker/reviews/${date}`, {
          method: 'PUT',
          body: JSON.stringify({ status: 'draft', habit_results: pendingResultsRef.current }),
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const toggleHabit = (habitId: string) => {
    if (!review) return;
    const nextHabits = review.habits.map(h => h.habit_id === habitId ? { ...h, checked: !h.checked } : h);
    setReview({ ...review, status: review.status === 'confirmed' ? 'draft' : review.status, habits: nextHabits });

    const habitResults = nextHabits.map(h => ({ habit_id: h.habit_id, checked: h.checked }));
    pendingResultsRef.current = habitResults;
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => { save('draft', habitResults); }, DRAFT_DEBOUNCE_MS);
  };

  const confirmDay = () => {
    if (!review) return;
    window.clearTimeout(debounceRef.current);
    const habitResults = review.habits.map(h => ({ habit_id: h.habit_id, checked: h.checked }));
    pendingResultsRef.current = null;
    save('confirmed', habitResults);
  };

  const changeDate = (nextDate: string) => {
    navigate(`/habittracker/review/${nextDate}`);
  };

  const shiftDate = (deltaDays: number) => {
    const d = new Date(`${date}T00:00:00`);
    d.setDate(d.getDate() + deltaDays);
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    changeDate(`${d.getFullYear()}-${mm}-${dd}`);
  };

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => shiftDate(-1)}>‹ Prev</button>
        <input
          type="date"
          value={date}
          onChange={e => changeDate(e.target.value)}
          style={{ padding: 8, borderRadius: 8, border: '1px solid #ccc', fontSize: 15 }}
        />
        <button style={btnStyle} onClick={() => shiftDate(1)}>Next ›</button>
      </div>

      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}

      {!loading && !error && review && (
        <>
          <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
            <DayStatusBadge status={review.status} />
            {saving && <span style={{ fontSize: 12, color: '#999' }}>Saving…</span>}
          </div>

          {review.habits.length === 0 && (
            <div style={{ color: '#888', fontSize: 14 }}>No habits are active on this date.</div>
          )}

          {review.habits.map(h => (
            <label
              key={h.habit_id}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: 12, borderRadius: 10, border: '1px solid #e0e0e0',
                marginBottom: 8, background: '#fff', cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={h.checked}
                onChange={() => toggleHabit(h.habit_id)}
                style={{ marginTop: 3, width: 18, height: 18 }}
              />
              <div>
                <div style={{ fontWeight: 600 }}>{h.name}</div>
                {h.description && <div style={{ fontSize: 13, color: '#777' }}>{h.description}</div>}
              </div>
            </label>
          ))}

          <button
            style={{ ...primaryBtnStyle, width: '100%', marginTop: 10, padding: '12px 14px', fontSize: 16 }}
            onClick={confirmDay}
            disabled={review.habits.length === 0}
          >
            Confirm day
          </button>
        </>
      )}
    </div>
  );
}

// ── Habit Definitions View ───────────────────────────────────────────────────

function HabitRowEditor({ habit, onSaved }: { habit: HabitRow; onSaved: (h: HabitRow) => void }) {
  const [name, setName] = useState(habit.name);
  const [description, setDescription] = useState(habit.description ?? '');
  const [defaultChecked, setDefaultChecked] = useState(habit.default_checked);
  const [activeFrom, setActiveFrom] = useState(habit.active_from);
  const [endDate, setEndDate] = useState(habit.end_date ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const archived = !!habit.end_date;

  const patch = async (body: Record<string, unknown>) => {
    setSaving(true);
    setError(null);
    const res = await apiFetch<HabitRow>(`/habittracker/habits/${habit.id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
    setSaving(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    onSaved(res);
  };

  const saveFields = () => {
    patch({
      name,
      description: description.trim() === '' ? null : description,
      default_checked: defaultChecked,
      active_from: activeFrom,
    });
  };

  const toggleArchive = () => {
    if (archived) {
      patch({ end_date: null });
      setEndDate('');
    } else {
      const today = todayISO();
      patch({ end_date: today });
      setEndDate(today);
    }
  };

  return (
    <div
      style={{
        padding: 14, borderRadius: 10, border: '1px solid #e0e0e0',
        marginBottom: 10, background: archived ? '#f7f7f7' : '#fff',
        opacity: archived ? 0.75 : 1,
      }}
    >
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Name"
               style={{ flex: '1 1 160px', padding: 6, borderRadius: 6, border: '1px solid #ccc' }} />
        <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)"
               style={{ flex: '2 1 220px', padding: 6, borderRadius: 6, border: '1px solid #ccc' }} />
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8, fontSize: 13 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={defaultChecked} onChange={e => setDefaultChecked(e.target.checked)} />
          Default checked
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Active from
          <input type="date" value={activeFrom} onChange={e => setActiveFrom(e.target.value)}
                 style={{ padding: 4, borderRadius: 6, border: '1px solid #ccc' }} />
        </label>
        {archived && <span style={{ color: '#999' }}>Archived (end date {endDate})</span>}
      </div>
      {error && <div style={{ color: '#b3261e', fontSize: 12, marginBottom: 8 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={btnStyle} onClick={saveFields} disabled={saving}>Save</button>
        <button style={btnStyle} onClick={toggleArchive} disabled={saving}>
          {archived ? 'Un-archive' : 'Archive'}
        </button>
      </div>
    </div>
  );
}

function AddHabitForm({ onCreated }: { onCreated: (h: HabitRow) => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [activeFrom, setActiveFrom] = useState(todayISO());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true);
    setError(null);
    const res = await apiFetch<HabitRow>('/habittracker/habits', {
      method: 'POST',
      body: JSON.stringify({
        name,
        description: description.trim() === '' ? undefined : description,
        default_checked: false,
        active_from: activeFrom,
      }),
    });
    setSaving(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setName('');
    setDescription('');
    onCreated(res);
  };

  return (
    <div style={{ padding: 14, borderRadius: 10, border: '1px dashed #bbb', marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Add a new habit</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Name"
               style={{ flex: '1 1 160px', padding: 6, borderRadius: 6, border: '1px solid #ccc' }} />
        <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)"
               style={{ flex: '2 1 220px', padding: 6, borderRadius: 6, border: '1px solid #ccc' }} />
        <input type="date" value={activeFrom} onChange={e => setActiveFrom(e.target.value)}
               style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc' }} />
      </div>
      {error && <div style={{ color: '#b3261e', fontSize: 12, marginBottom: 8 }}>{error}</div>}
      <button style={primaryBtnStyle} onClick={submit} disabled={saving || !name.trim()}>Add habit</button>
    </div>
  );
}

function HabitDefinitionsView() {
  const [habits, setHabits] = useState<HabitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reorderError, setReorderError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch<Dataset<HabitRow>>('/habittracker/habits');
    setLoading(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setHabits(res.rows);
  }, []);

  useEffect(() => { load(); }, [load]);

  const replaceHabit = (updated: HabitRow) => {
    setHabits(prev => prev.map(h => h.id === updated.id ? updated : h));
  };

  const addHabit = (created: HabitRow) => {
    setHabits(prev => [...prev, created]);
  };

  const move = async (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= habits.length) return;
    const next = [...habits];
    [next[index], next[target]] = [next[target], next[index]];
    setHabits(next);
    setReorderError(null);
    const res = await apiFetch('/habittracker/habits/reorder', {
      method: 'POST',
      body: JSON.stringify({ habit_ids: next.map(h => h.id) }),
    });
    if (isApiError(res)) { setReorderError(res.error.message); load(); }
  };

  return (
    <div style={pageStyle}>
      <h2 style={{ margin: '0 0 12px' }}>Habit Definitions</h2>
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {reorderError && <ErrorCard message={reorderError} />}

      {!loading && !error && (
        <>
          <AddHabitForm onCreated={addHabit} />
          {habits.map((h, i) => (
            <div key={h.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 14 }}>
                <button style={{ ...btnStyle, padding: '2px 8px' }} onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
                <button style={{ ...btnStyle, padding: '2px 8px' }} onClick={() => move(i, 1)} disabled={i === habits.length - 1}>↓</button>
              </div>
              <div style={{ flex: 1 }}>
                <HabitRowEditor habit={h} onSaved={replaceHabit} />
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ── Reports View ──────────────────────────────────────────────────────────────

const CELL_STYLE: Record<CellState, React.CSSProperties> = {
  completed:     { background: '#2a7a3b', border: '1px solid #2a7a3b' },
  not_completed: { background: '#d8a0a0', border: '1px solid #c77' },
  not_active:    { background: 'transparent', border: '1px dashed #ddd' },
  unreviewed:    { background: '#fff', border: '1px solid #ccc' },
};

function ReportGridCell({ cell, onClick }: { cell: ReportCell; onClick: () => void }) {
  return (
    <div
      title={`${cell.date}: ${cell.state}`}
      onClick={onClick}
      style={{
        ...CELL_STYLE[cell.state],
        width: 20, height: 20, borderRadius: 4, cursor: 'pointer', flex: '0 0 auto',
      }}
    />
  );
}

function monthAnchorShift(anchor: string, deltaMonths: number): string {
  const d = new Date(`${anchor}T00:00:00`);
  d.setMonth(d.getMonth() + deltaMonths);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function weekAnchorShift(anchor: string, deltaWeeks: number): string {
  const d = new Date(`${anchor}T00:00:00`);
  d.setDate(d.getDate() + deltaWeeks * 7);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function ReportsView() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<'week' | 'month'>('week');
  const [anchor, setAnchor] = useState(todayISO());
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await apiFetch<ReportsResponse>(`/habittracker/reports?period=${period}&anchor_date=${anchor}`);
    setLoading(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setData(res);
  }, [period, anchor]);

  useEffect(() => { load(); }, [load]);

  const shift = (delta: number) => {
    setAnchor(prev => (period === 'week' ? weekAnchorShift(prev, delta) : monthAnchorShift(prev, delta)));
  };

  const goToDate = (date: string) => navigate(`/habittracker/review/${date}`);

  return (
    <div style={pageStyle}>
      <h2 style={{ margin: '0 0 12px' }}>Reports</h2>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={period} onChange={e => setPeriod(e.target.value as 'week' | 'month')}
                style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc' }}>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
        <button style={btnStyle} onClick={() => shift(-1)}>‹ Prev</button>
        <button style={btnStyle} onClick={() => shift(1)}>Next ›</button>
      </div>

      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}

      {!loading && !error && data && (
        <>
          <div style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>
            {data.period_summary.period_start} – {data.period_summary.period_end} ·{' '}
            {data.period_summary.confirmed_days} / {data.period_summary.elapsed_days} days confirmed
          </div>

          {data.rows.length === 0 && (
            <div style={{ color: '#888', fontSize: 14 }}>No habits were active during this period.</div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <div style={{ display: 'flex', gap: 4, marginBottom: 6, paddingLeft: 140 }}>
              {data.period_summary.dates.map(d => (
                <div
                  key={d}
                  onClick={() => goToDate(d)}
                  title={d}
                  style={{ width: 20, fontSize: 10, color: '#888', textAlign: 'center', cursor: 'pointer' }}
                >
                  {d.slice(8, 10)}
                </div>
              ))}
            </div>
            {data.rows.map(row => (
              <div key={row.habit_id} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}>
                <div style={{ width: 140, fontSize: 13, flex: '0 0 auto', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {row.name}
                </div>
                {row.cells.map(cell => (
                  <ReportGridCell key={cell.date} cell={cell} onClick={() => goToDate(cell.date)} />
                ))}
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16 }}>
            {data.rows.map(row => (
              <div key={row.habit_id} style={{ fontSize: 13, color: '#555', marginBottom: 4 }}>
                <strong>{row.name}</strong>:{' '}
                {row.rate === null
                  ? `${row.eligible_confirmed_days} confirmed days`
                  : `${Math.round(row.rate * 100)}% (${row.completed_count} / ${row.eligible_confirmed_days} confirmed days)`}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function HabitTrackerApp() {
  return (
    <Routes>
      <Route path="/" element={<DailyReviewView />} />
      <Route path="/review/:date" element={<DailyReviewView />} />
      <Route path="/habits" element={<HabitDefinitionsView />} />
      <Route path="/reports" element={<ReportsView />} />
    </Routes>
  );
}
