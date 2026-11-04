/**
 * HabitTracker ShellEntry — Sprint 01
 *
 * Views:
 *   /habittracker                     -> TodayView (one-tap logging + 28-day dots)
 *   /habittracker/review/:date        -> DailyReviewView (explicit date)
 *   /habittracker/habits              -> HabitDefinitionsView (cards, 28-day dots)
 *   /habittracker/habits/:id          -> HabitDetailView (editor)
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
  kind: HabitKind;
  unit: string | null;
  increment: number;
  source: string | null;
  display_order: number;
  active_from: string;
  end_date: string | null;
}

type HabitKind = 'binary' | 'quantity';

interface TodayHabit {
  habit_id: string;
  name: string;
  kind: HabitKind;
  linked: boolean;
  unit: string | null;
  increment: number;
  total: number;
  done: boolean;
}

interface HistoryDay { date: string; done: number; tracked: number }

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

// ── Today View (one-tap logging) ─────────────────────────────────────────────

const HEAT_DAYS = 28;

function HeatmapStrip({ days, selected, onSelect }: { days: HistoryDay[]; selected: string; onSelect: (d: string) => void }) {
  return (
    <div
      style={{ display: 'grid', gridTemplateColumns: "repeat(7, 1fr)", gap: 8, width: '100%', marginBottom: 18 }}
      aria-label="Last 28 days"
    >
      {days.map(d => {
        const ratio = d.tracked > 0 ? d.done / d.tracked : 0;
        return (
          <button
            key={d.date}
            title={`${d.date}: ${d.done} / ${d.tracked}`}
            aria-label={`Open ${d.date}`}
            onClick={() => onSelect(d.date)}
            style={{
              aspectRatio: '1 / 1', borderRadius: '50%', padding: 0, border: 'none', cursor: 'pointer', minWidth: 0,
              background: ratio > 0 ? `rgba(42, 122, 59, ${0.25 + 0.75 * ratio})` : '#e6e6e6',
              outline: d.date === selected ? '2px solid #14161A' : 'none', outlineOffset: 1,
            }}
          />
        );
      })}
    </div>
  );
}

function TodayView() {
  const navigate = useNavigate();
  const { date: dateParam } = useParams<{ date?: string }>();
  const realToday = todayISO();
  const date = dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam) ? dateParam : realToday;
  const [habits, setHabits] = useState<TodayHabit[]>([]);
  const [history, setHistory] = useState<HistoryDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    const res = await apiFetch<{ days: HistoryDay[] }>(`/habittracker/history?days=${HEAT_DAYS}&end=${realToday}`);
    if (!isApiError(res)) setHistory(res.days);
  }, [realToday]);

  useEffect(() => {
    (async () => {
      const res = await apiFetch<{ habits: TodayHabit[] }>(`/habittracker/today?date=${date}`);
      setLoading(false);
      if (isApiError(res)) { setError(res.error.message); return; }
      setHabits(res.habits);
    })();
    loadHistory();
  }, [date, loadHistory]);

  // Server returns the new day total; replace it locally so rapid taps stay consistent.
  const applyTotal = (habitId: string, total: number) =>
    setHabits(prev => prev.map(h => (h.habit_id === habitId ? { ...h, total, done: total > 0 } : h)));

  const log = async (h: TodayHabit) => {
    // Binary tap on a done habit undoes it; quantity taps always add.
    const undo = h.kind === 'binary' && h.done;
    const res = await apiFetch<{ total: number }>(
      undo ? `/habittracker/habits/${h.habit_id}/entries/last?date=${date}` : `/habittracker/habits/${h.habit_id}/entries`,
      undo ? { method: 'DELETE' } : { method: 'POST', body: JSON.stringify({ date }) },
    );
    if (isApiError(res)) { setError(res.error.message); return; }
    applyTotal(h.habit_id, res.total);
    loadHistory();
  };

  const undoLast = async (h: TodayHabit) => {
    const res = await apiFetch<{ total: number }>(
      `/habittracker/habits/${h.habit_id}/entries/last?date=${date}`, { method: 'DELETE' });
    if (isApiError(res)) { setError(res.error.message); return; }
    applyTotal(h.habit_id, res.total);
    loadHistory();
  };

  const tapStyle = (done: boolean): React.CSSProperties => ({
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
    padding: '14px 16px', borderRadius: 10, cursor: 'pointer', fontSize: 16, textAlign: 'left',
    border: `1px solid ${done ? '#2a7a3b' : '#e0e0e0'}`,
    background: done ? '#dcf3df' : '#fff', color: '#14161A',
  });

  return (
    <div style={pageStyle}>
      {history.length > 0 && (
        <HeatmapStrip days={history} selected={date}
                      onSelect={d => navigate(d === realToday ? '/habittracker' : `/habittracker/day/${d}`)} />
      )}
      {date !== realToday && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <strong>{new Date(date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</strong>
          <button style={btnStyle} onClick={() => navigate('/habittracker')}>Back to today</button>
        </div>
      )}
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {!loading && habits.length === 0 && !error && (
        <div style={{ color: '#888', fontSize: 14 }}>No active habits. Add one under Habits.</div>
      )}
      {habits.map(h => (
        <div key={h.habit_id} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <button style={{ ...tapStyle(h.done), cursor: h.linked ? 'default' : 'pointer' }}
                  onClick={() => { if (!h.linked) log(h); }}>
            <span style={{ fontWeight: 600 }}>{h.name}</span>
            {h.kind === 'binary' || h.linked ? (
              <span style={{ fontSize: 20 }}>{h.done ? '✓' : '○'}</span>
            ) : (
              <span style={{ color: '#555' }}>
                {h.total} {h.unit ?? ''} <strong style={{ color: '#2a7a3b' }}>+{h.increment}</strong>
              </span>
            )}
          </button>
          {h.kind === 'quantity' && (
            <button
              style={{ ...btnStyle, padding: '0 14px' }}
              onClick={() => undoLast(h)}
              disabled={h.total === 0}
              aria-label={`Undo last ${h.name}`}
            >
              ↩
            </button>
          )}
        </div>
      ))}
      <button
        style={{ ...btnStyle, border: 'none', background: 'none', color: '#777', fontSize: 13, marginTop: 8 }}
        onClick={() => navigate(`/habittracker/review/${date}`)}
      >
        Evening review for today ›
      </button>
    </div>
  );
}

// ── Habit Definitions View ───────────────────────────────────────────────────

function KindFields({ kind, unit, increment, onKind, onUnit, onIncrement }: {
  kind: HabitKind; unit: string; increment: string;
  onKind: (k: HabitKind) => void; onUnit: (u: string) => void; onIncrement: (i: string) => void;
}) {
  const inputStyle = { padding: 4, borderRadius: 6, border: '1px solid #ccc' };
  return (
    <>
      <select value={kind} onChange={e => onKind(e.target.value as HabitKind)} style={inputStyle}>
        <option value="binary">Done / not done</option>
        <option value="quantity">Counted</option>
      </select>
      {kind === 'quantity' && (
        <>
          <input value={unit} onChange={e => onUnit(e.target.value)} placeholder="unit (reps, min)"
                 style={{ ...inputStyle, width: 110 }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            +<input type="number" min={1} value={increment} onChange={e => onIncrement(e.target.value)}
                    style={{ ...inputStyle, width: 60 }} />per tap
          </label>
        </>
      )}
    </>
  );
}

function HabitRowEditor({ habit, onSaved }: { habit: HabitRow; onSaved: (h: HabitRow) => void }) {
  const [name, setName] = useState(habit.name);
  const [description, setDescription] = useState(habit.description ?? '');
  const [defaultChecked, setDefaultChecked] = useState(habit.default_checked);
  const [activeFrom, setActiveFrom] = useState(habit.active_from);
  const [endDate, setEndDate] = useState(habit.end_date ?? '');
  const [kind, setKind] = useState<HabitKind>(habit.kind);
  const [unit, setUnit] = useState(habit.unit ?? '');
  const [increment, setIncrement] = useState(String(habit.increment));
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
      ...(habit.source ? {} : {
        kind,
        unit: kind === 'quantity' ? unit : null,
        increment: kind === 'quantity' ? Number(increment) || 1 : 1,
      }),
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
        {habit.source ? <span style={{ color: '#777' }}>Tracked automatically from EssayCards</span> : (
          <KindFields kind={kind} unit={unit} increment={increment}
                      onKind={setKind} onUnit={setUnit} onIncrement={setIncrement} />
        )}
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
  const [kind, setKind] = useState<HabitKind>('binary');
  const [unit, setUnit] = useState('');
  const [increment, setIncrement] = useState('1');
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
        kind,
        unit,
        increment: Number(increment) || 1,
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
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8, fontSize: 13 }}>
        <KindFields kind={kind} unit={unit} increment={increment}
                    onKind={setKind} onUnit={setUnit} onIncrement={setIncrement} />
      </div>
      {error && <div style={{ color: '#b3261e', fontSize: 12, marginBottom: 8 }}>{error}</div>}
      <button style={primaryBtnStyle} onClick={submit} disabled={saving || !name.trim()}>Add habit</button>
    </div>
  );
}

const CARD_DAYS = 28;

/** One dot per day in a single full-width line (oldest first). null = outside the habit's active window. */
function StreakDots({ cells }: { cells: (number | null)[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cells.length}, 1fr)`, gap: 3, width: '100%' }} aria-hidden="true">
      {cells.map((c, i) => (
        <span
          key={i}
          style={{
            aspectRatio: '1 / 1', borderRadius: '50%',
            background: c === 1 ? '#2a7a3b' : c === 0 ? '#e3e3e3' : 'transparent',
            outline: i === cells.length - 1 ? '2px solid #14161A' : 'none', outlineOffset: 1,
          }}
        />
      ))}
    </div>
  );
}

function useHabitHistory(): Record<string, (number | null)[]> {
  const [hist, setHist] = useState<Record<string, (number | null)[]>>({});
  useEffect(() => {
    (async () => {
      const res = await apiFetch<{ habits: Record<string, (number | null)[]> }>(
        `/habittracker/habit-history?days=${CARD_DAYS}&end=${todayISO()}`);
      if (!isApiError(res)) setHist(res.habits);
    })();
  }, []);
  return hist;
}

function HabitCard({ habit, cells, onClick, archived }: {
  habit: HabitRow; cells: (number | null)[]; onClick: () => void; archived?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'stretch', textAlign: 'left',
        padding: 14, borderRadius: 12, border: '1px solid #e0e0e0', background: '#fff',
        color: '#14161A', cursor: 'pointer', opacity: archived ? 0.6 : 1,
      }}
    >
      <span style={{ fontWeight: 600, fontSize: 15 }}>{habit.name}</span>
      <StreakDots cells={cells.length ? cells : Array(CARD_DAYS).fill(null)} />
    </button>
  );
}

function HabitDefinitionsView() {
  const navigate = useNavigate();
  const hist = useHabitHistory();
  const [habits, setHabits] = useState<HabitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reorderError, setReorderError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [ordering, setOrdering] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch<Dataset<HabitRow>>('/habittracker/habits');
    setLoading(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setHabits(res.rows);
  }, []);

  useEffect(() => { load(); }, [load]);

  const today = todayISO();
  const isArchived = (h: HabitRow) => !!h.end_date && h.end_date < today;
  const active = habits.filter(h => !isArchived(h));
  const archived = habits.filter(isArchived);

  const move = async (id: string, delta: number) => {
    const index = active.findIndex(h => h.id === id);
    const target = index + delta;
    if (target < 0 || target >= active.length) return;
    const nextActive = [...active];
    [nextActive[index], nextActive[target]] = [nextActive[target], nextActive[index]];
    const next = [...nextActive, ...archived];
    setHabits(next);
    setReorderError(null);
    const res = await apiFetch('/habittracker/habits/reorder', {
      method: 'POST',
      body: JSON.stringify({ habit_ids: next.map(h => h.id) }),
    });
    if (isApiError(res)) { setReorderError(res.error.message); load(); }
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid', gridTemplateColumns: '1fr', gap: 10,
  };

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Habits</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={btnStyle} onClick={() => setOrdering(o => !o)}>{ordering ? 'Done' : 'Edit order'}</button>
          <button style={btnStyle} onClick={() => setAdding(a => !a)}>{adding ? 'Cancel' : '+ Add habit'}</button>
        </div>
      </div>
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {reorderError && <ErrorCard message={reorderError} />}

      {!loading && !error && (
        <>
          {adding && (
            <AddHabitForm onCreated={h => { setHabits(prev => [...prev.filter(x => !isArchived(x)), h, ...prev.filter(isArchived)]); setAdding(false); }} />
          )}
          <div style={gridStyle}>
            {active.map((h, i) => (
              <div key={h.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <HabitCard habit={h} cells={hist[h.id] ?? []} onClick={() => navigate(`/habittracker/habits/${h.id}`)} />
                {ordering && (
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                    <button style={{ ...btnStyle, padding: '2px 12px' }} onClick={() => move(h.id, -1)} disabled={i === 0}>↑</button>
                    <button style={{ ...btnStyle, padding: '2px 12px' }} onClick={() => move(h.id, 1)} disabled={i === active.length - 1}>↓</button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {archived.length > 0 && (
            <>
              <button
                style={{ ...btnStyle, border: 'none', background: 'none', color: '#777', fontSize: 13, margin: '16px 0 8px' }}
                onClick={() => setShowArchived(v => !v)}
              >
                {showArchived ? '▾' : '▸'} Archived ({archived.length})
              </button>
              {showArchived && (
                <div style={gridStyle}>
                  {archived.map(h => (
                    <HabitCard key={h.id} habit={h} archived cells={hist[h.id] ?? []}
                               onClick={() => navigate(`/habittracker/habits/${h.id}`)} />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function HabitDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const hist = useHabitHistory();
  const [habit, setHabit] = useState<HabitRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await apiFetch<Dataset<HabitRow>>('/habittracker/habits');
      setLoading(false);
      if (isApiError(res)) { setError(res.error.message); return; }
      const h = res.rows.find(r => r.id === id);
      if (h) setHabit(h); else setError('Habit not found');
    })();
  }, [id]);

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, border: 'none', background: 'none', color: '#777', padding: 0, marginBottom: 8 }}
              onClick={() => navigate('/habittracker/habits')}>‹ Habits</button>
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {habit && (
        <>
          <div style={{ margin: '4px 0 16px' }}>
            <StreakDots cells={hist[habit.id] ?? Array(CARD_DAYS).fill(null)} />
          </div>
          <HabitRowEditor habit={habit} onSaved={setHabit} />
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
      <Route path="/" element={<TodayView />} />
      <Route path="/day/:date" element={<TodayView />} />
      <Route path="/review/:date" element={<DailyReviewView />} />
      <Route path="/habits" element={<HabitDefinitionsView />} />
      <Route path="/habits/:id" element={<HabitDetailView />} />
      <Route path="/reports" element={<ReportsView />} />
    </Routes>
  );
}
