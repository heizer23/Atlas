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
import HabitSymbol, { SYMBOL_LAYERS, type SymbolLayer, type SymbolLevels } from './HabitSymbol';

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
  category_id: string | null;
  priority: number | null;
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
  category_id: string | null;
  priority: number | null;
}

interface CategoryInfo { id: string; name: string; kind: string; symbol_layer?: SymbolLayer | null; level?: number | null }
interface PriorityInfo { level: number; label: string; description?: string | null }

/** One day of the overview: level per symbol layer. */
interface SymbolDay { date: string; levels: SymbolLevels }

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

const PIP_ON = '#2a7a3b';
const PIP_OFF = '#dcdcdc';

/** Three small dots; `filled` of them are lit. Used for habit priority and category level. */
function Pips({ filled, label }: { filled: number; label: string }) {
  return (
    <span role="img" aria-label={label} title={label} style={{ display: 'inline-flex', gap: 3 }}>
      {[1, 2, 3].map(i => (
        <span key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: i <= filled ? PIP_ON : PIP_OFF }} />
      ))}
    </span>
  );
}

function priorityLabel(priority: number | null, priorities: PriorityInfo[]): string {
  if (!priority) return 'No priority';
  const p = priorities.find(x => x.level === priority);
  return `Level ${priority}${p ? ` — ${p.label}` : ''}`;
}

function useCategories(): { categories: CategoryInfo[]; priorities: PriorityInfo[] } {
  const [state, setState] = useState<{ categories: CategoryInfo[]; priorities: PriorityInfo[] }>({ categories: [], priorities: [] });
  useEffect(() => {
    (async () => {
      const res = await apiFetch<{ rows: CategoryInfo[]; priorities: PriorityInfo[] }>('/habittracker/categories');
      if (!isApiError(res)) setState({ categories: res.rows, priorities: res.priorities });
    })();
  }, []);
  return state;
}

/** Filter chips: "All" plus one per category; several can be on at once. Empty selection = all. */
function CategoryFilter({ categories, value, onChange }: {
  categories: CategoryInfo[]; value: string[]; onChange: (ids: string[]) => void;
}) {
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter(v => v !== id) : [...value, id]);
  if (categories.length === 0) return null;
  const chip = (active: boolean): React.CSSProperties => ({
    padding: '5px 12px', borderRadius: 999, fontSize: 13, cursor: 'pointer',
    border: `1px solid ${active ? '#14161A' : '#d6d6d6'}`,
    background: active ? '#14161A' : '#fff', color: active ? '#fff' : '#14161A',
  });
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
      <button style={chip(value.length === 0)} onClick={() => onChange([])}>All</button>
      {categories.map(c => (
        <button key={c.id} style={chip(value.includes(c.id))} onClick={() => toggle(c.id)}>{c.name}</button>
      ))}
    </div>
  );
}

/** Group items by category in category display order; uncategorised items last under "Other". */
function groupByCategory<T extends { category_id: string | null }>(
  items: T[], categories: CategoryInfo[], filter: string[],
): { category: CategoryInfo | null; items: T[] }[] {
  const groups = categories.map(c => ({ category: c as CategoryInfo | null, items: items.filter(i => i.category_id === c.id) }));
  const known = new Set(categories.map(c => c.id));
  groups.push({ category: null, items: items.filter(i => !i.category_id || !known.has(i.category_id)) });
  return groups.filter(g => g.items.length > 0 && (filter.length === 0 || (g.category !== null && filter.includes(g.category.id))));
}

function GroupHeader({ name, level, showLevel }: { name: string; level?: number | null; showLevel?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '16px 0 8px' }}>
      <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', color: '#555' }}>{name}</span>
      {showLevel && level !== undefined && level !== null && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#555' }}>
          {level === 0 ? 'none yet' : `Level ${level}`}
          <Pips filled={level} label={`${name} level ${level} of 3 today`} />
        </span>
      )}
    </div>
  );
}

function CategoryPriorityFields({ categories, priorities, categoryId, priority, onCategory, onPriority }: {
  categories: CategoryInfo[]; priorities: PriorityInfo[];
  categoryId: string; priority: string; onCategory: (v: string) => void; onPriority: (v: string) => void;
}) {
  const inputStyle = { padding: 4, borderRadius: 6, border: '1px solid #ccc' };
  return (
    <>
      <select value={categoryId} onChange={e => onCategory(e.target.value)} style={inputStyle} aria-label="Category">
        <option value="">No category</option>
        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <select value={priority} onChange={e => onPriority(e.target.value)} style={inputStyle} aria-label="Priority">
        <option value="">No priority</option>
        {priorities.map(p => <option key={p.level} value={p.level}>{`${p.level} — ${p.label}`}</option>)}
      </select>
    </>
  );
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

/** Layers to draw for the current category selection (empty selection = all four). */
function visibleLayers(categories: CategoryInfo[], filter: string[]): SymbolLayer[] {
  if (filter.length === 0) return SYMBOL_LAYERS;
  return categories.filter(c => filter.includes(c.id) && c.symbol_layer).map(c => c.symbol_layer as SymbolLayer);
}

/** Dark panel, 7 columns, oldest first. Cell size/spacing is independent of which layers are visible. */
function HeatmapStrip({ days, selected, visible, onSelect }: {
  days: SymbolDay[]; selected: string; visible: SymbolLayer[]; onSelect: (d: string) => void;
}) {
  return (
    <div
      style={{
        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px 6px', width: '100%',
        boxSizing: 'border-box', padding: '14px 10px', marginBottom: 18, borderRadius: 14, background: '#171B22',
      }}
      aria-label="Last 28 days"
    >
      {days.map(d => (
        <button
          key={d.date}
          aria-label={`Open ${d.date}`}
          onClick={() => onSelect(d.date)}
          style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, minWidth: 0, padding: 0,
            border: 'none', background: 'none', cursor: 'pointer',
          }}
        >
          <div style={{ width: '100%', aspectRatio: '1 / 1', borderRadius: '50%', boxSizing: 'border-box',
                        boxShadow: d.date === selected ? '0 0 0 2px #E8E4DA' : 'none' }}>
            <HabitSymbol levels={d.levels} visible={visible} size="100%"
                         title={`${d.date}: ${visible.map(l => `${l} ${d.levels[l] ?? 0}`).join(', ')}`} />
          </div>
          <span style={{ fontSize: 10, color: d.date === selected ? '#E8E4DA' : '#7B8491' }}>{d.date.slice(8, 10)}</span>
        </button>
      ))}
    </div>
  );
}

function TodayView() {
  const navigate = useNavigate();
  const { date: dateParam } = useParams<{ date?: string }>();
  const realToday = todayISO();
  const date = dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam) ? dateParam : realToday;
  const [habits, setHabits] = useState<TodayHabit[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [priorities, setPriorities] = useState<PriorityInfo[]>([]);
  const [filter, setFilter] = useState<string[]>([]);
  const [history, setHistory] = useState<SymbolDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Day-level levels (category headers) come with /today; refetched after each tap.
  const loadDay = useCallback(async () => {
    const res = await apiFetch<{ habits: TodayHabit[]; categories: CategoryInfo[]; priorities: PriorityInfo[] }>(
      `/habittracker/today?date=${date}`);
    setLoading(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setHabits(res.habits);
    setCategories(res.categories);
    setPriorities(res.priorities);
  }, [date]);

  // Levels for every category always (the filter only decides which layers are drawn).
  const loadHistory = useCallback(async () => {
    const res = await apiFetch<{ dates: string[]; categories: { symbol_layer: SymbolLayer | null; levels: (number | null)[] }[] }>(
      `/habittracker/category-progress?days=${HEAT_DAYS}&end=${realToday}`);
    if (isApiError(res)) return;
    setHistory(res.dates.map((d, i) => {
      const levels: SymbolLevels = {};
      for (const c of res.categories) if (c.symbol_layer) levels[c.symbol_layer] = c.levels[i] ?? 0;
      return { date: d, levels };
    }));
  }, [realToday]);

  useEffect(() => { loadDay(); }, [loadDay]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

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
    loadDay();
  };

  const undoLast = async (h: TodayHabit) => {
    const res = await apiFetch<{ total: number }>(
      `/habittracker/habits/${h.habit_id}/entries/last?date=${date}`, { method: 'DELETE' });
    if (isApiError(res)) { setError(res.error.message); return; }
    applyTotal(h.habit_id, res.total);
    loadHistory();
    loadDay();
  };

  const tapStyle = (done: boolean): React.CSSProperties => ({
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
    padding: '14px 16px', borderRadius: 10, cursor: 'pointer', fontSize: 16, textAlign: 'left',
    border: `1px solid ${done ? '#2a7a3b' : '#e0e0e0'}`,
    background: done ? '#dcf3df' : '#fff', color: '#14161A',
  });

  return (
    <div style={pageStyle}>
      <CategoryFilter categories={categories} value={filter} onChange={setFilter} />
      {history.length > 0 && (
        <HeatmapStrip days={history} selected={date} visible={visibleLayers(categories, filter)}
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
      {groupByCategory(habits.map(h => ({ ...h, category_id: h.category_id })), categories, filter).map(g => (
        <div key={g.category?.id ?? 'other'}>
          {categories.length > 0 && (
            <GroupHeader name={g.category?.name ?? 'Other'} level={g.category?.level} showLevel />
          )}
      {g.items.map(h => (
        <div key={h.habit_id} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <button style={{ ...tapStyle(h.done), cursor: h.linked ? 'default' : 'pointer' }}
                  onClick={() => { if (!h.linked) log(h); }}>
            <span style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {h.name}
              {h.priority && <Pips filled={h.priority} label={priorityLabel(h.priority, priorities)} />}
            </span>
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
  const { categories, priorities } = useCategories();
  const [categoryId, setCategoryId] = useState(habit.category_id ?? '');
  const [priority, setPriority] = useState(habit.priority ? String(habit.priority) : '');
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
      // Empty select = explicit null (clears), never omission (R-CON-AL-04/05).
      category_id: categoryId === '' ? null : categoryId,
      priority: priority === '' ? null : Number(priority),
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
        <CategoryPriorityFields categories={categories} priorities={priorities}
                                categoryId={categoryId} priority={priority}
                                onCategory={setCategoryId} onPriority={setPriority} />
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
  const { categories, priorities } = useCategories();
  const [categoryId, setCategoryId] = useState('');
  const [priority, setPriority] = useState('');
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
        category_id: categoryId === '' ? null : categoryId,
        priority: priority === '' ? null : Number(priority),
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
        <CategoryPriorityFields categories={categories} priorities={priorities}
                                categoryId={categoryId} priority={priority}
                                onCategory={setCategoryId} onPriority={setPriority} />
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

function HabitCard({ habit, cells, onClick, archived, priorities }: {
  habit: HabitRow; cells: (number | null)[]; onClick: () => void; archived?: boolean; priorities: PriorityInfo[];
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
      <span style={{ fontWeight: 600, fontSize: 15, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {habit.name}
        {habit.priority && <Pips filled={habit.priority} label={priorityLabel(habit.priority, priorities)} />}
      </span>
      <StreakDots cells={cells.length ? cells : Array(CARD_DAYS).fill(null)} />
    </button>
  );
}

function HabitDefinitionsView() {
  const navigate = useNavigate();
  const hist = useHabitHistory();
  const { categories, priorities } = useCategories();
  const [filter, setFilter] = useState<string[]>([]);
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
          <CategoryFilter categories={categories} value={filter} onChange={setFilter} />
          {groupByCategory(active.map(h => h), categories.map(c => c), filter).map(g => (
            <div key={g.category?.id ?? 'other'}>
              {categories.length > 0 && <GroupHeader name={g.category?.name ?? 'Other'} />}
              <div style={gridStyle}>
                {g.items.map(h => {
                  const i = active.findIndex(x => x.id === h.id);
                  return (
                    <div key={h.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <HabitCard habit={h} priorities={priorities} cells={hist[h.id] ?? []}
                                 onClick={() => navigate(`/habittracker/habits/${h.id}`)} />
                      {ordering && (
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                          <button style={{ ...btnStyle, padding: '2px 12px' }} onClick={() => move(h.id, -1)} disabled={i === 0}>↑</button>
                          <button style={{ ...btnStyle, padding: '2px 12px' }} onClick={() => move(h.id, 1)} disabled={i === active.length - 1}>↓</button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
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
                    <HabitCard key={h.id} habit={h} archived priorities={priorities} cells={hist[h.id] ?? []}
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
