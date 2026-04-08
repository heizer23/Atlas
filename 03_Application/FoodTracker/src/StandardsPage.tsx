/**
 * DayPage (rendered at /food/day) — Sprint 04
 *
 * Fetches GET /api/food/day on mount and after any mutating action.
 * Renders two sections:
 *
 *   Top    — Today: ALL entries logged today, with a Delete button per row
 *   Bottom — Standards: all standard dishes grouped by meal_type, click to log a copy
 *
 * Re-fetches the full payload after every mutating action.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';

// ── Date helpers ──────────────────────────────────────────────────────────────

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface TodayEntry {
  id:                  string;
  logged_at:           string;
  meal_type:           string;
  dish_name:           string;
  kcal:                number;
  protein_g:           number;
  fat_g:               number;
  standard:            boolean;
  source_standard_id:  string | null;
}

interface StandardDish {
  id:          string;
  meal_type:   string;
  dish_name:   string;
  kcal:        number;
  protein_g:   number;
  carbs_g:     number;
  fat_g:       number;
  fiber_g:     number;
  good_fat_g:  number;
  meat_g:      number;
  red_meat_g:  number;
  sodium_mg:   number;
  confidence:  number;
}

interface DayPagePayload {
  today_entries: TodayEntry[];
  standards:     StandardDish[];
}

// ── TodaySection ──────────────────────────────────────────────────────────────

function TodaySection({
  entries,
  onCopy,
  onDelete,
  actioningId,
}: {
  entries:     TodayEntry[];
  onCopy:      (id: string) => void;
  onDelete:    (id: string) => void;
  actioningId: string | null;
}) {
  if (entries.length === 0) {
    return (
      <section style={{ marginBottom: 'var(--space-lg)' }}>
        <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
          Today
        </h2>
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          Nothing logged yet today.
        </p>
      </section>
    );
  }

  const totalKcal    = entries.reduce((sum, e) => sum + e.kcal, 0);
  const totalProtein = entries.reduce((sum, e) => sum + e.protein_g, 0);

  return (
    <section style={{ marginBottom: 'var(--space-lg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--space-sm)' }}>
        <h2 className="type-title">Today</h2>
        <span className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          {totalKcal} kcal &middot; P {totalProtein.toFixed(1)} g
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
        {entries.map((entry) => {
          const busy = actioningId === entry.id;
          const time = entry.logged_at.includes('T')
            ? entry.logged_at.split('T')[1].slice(0, 5)
            : entry.logged_at;
          return (
            <div
              key={entry.id}
              style={{
                padding: 'var(--space-sm) var(--space-md)',
                background: 'var(--md-sys-color-surface)',
                border: '1px solid var(--md-sys-color-outline-variant)',
                borderRadius: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                opacity: busy ? 0.5 : 1,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                  {time} &middot; {entry.meal_type}
                  {entry.standard && (
                    <span style={{ marginLeft: 'var(--space-xs)', color: 'var(--md-sys-color-primary)', fontWeight: 600 }}>
                      STANDARD
                    </span>
                  )}
                </p>
                <p className="type-body" style={{ margin: 0, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.dish_name}
                </p>
                <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                  {entry.kcal} kcal &middot; P {entry.protein_g.toFixed(1)} g
                </p>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                <button
                  className="btn-outlined"
                  style={{ fontSize: '1rem', padding: '2px 10px', fontWeight: 600 }}
                  disabled={busy}
                  onClick={() => onCopy(entry.id)}
                  title="Add a copy"
                >
                  +
                </button>
                <button
                  className="btn-outlined"
                  style={{ fontSize: '1rem', padding: '2px 10px', fontWeight: 600, color: 'var(--md-sys-color-error)', borderColor: 'var(--md-sys-color-error)' }}
                  disabled={busy}
                  onClick={() => onDelete(entry.id)}
                  title="Remove one"
                >
                  −
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── StandardsSection ──────────────────────────────────────────────────────────

function StandardsSection({
  standards,
  onLogCopy,
  isActioning,
}: {
  standards:   StandardDish[];
  onLogCopy:   (standard_id: string) => void;
  isActioning: string | null;
}) {
  if (standards.length === 0) {
    return (
      <section>
        <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
          Standards
        </h2>
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No standards defined yet. Mark an entry as Standard from the Entries page.
        </p>
      </section>
    );
  }

  const groups: Record<string, StandardDish[]> = {};
  for (const dish of standards) {
    if (!groups[dish.meal_type]) groups[dish.meal_type] = [];
    groups[dish.meal_type].push(dish);
  }
  const mealTypeOrder = ['breakfast', 'lunch', 'dinner', 'snack', 'other'];
  const sortedKeys = Object.keys(groups).sort(
    (a, b) => mealTypeOrder.indexOf(a) - mealTypeOrder.indexOf(b),
  );

  return (
    <section>
      <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
        Standards
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        {sortedKeys.map((mealType) => (
          <div key={mealType}>
            <p
              className="type-label"
              style={{
                color: 'var(--md-sys-color-on-surface-variant)',
                marginBottom: 'var(--space-xs)',
                textTransform: 'capitalize',
                fontWeight: 600,
              }}
            >
              {mealType}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
              {groups[mealType].map((dish) => {
                const actioning = isActioning === dish.id;
                return (
                  <button
                    key={dish.id}
                    disabled={actioning}
                    onClick={() => onLogCopy(dish.id)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: 'var(--space-sm) var(--space-md)',
                      background: actioning
                        ? 'var(--md-sys-color-surface-variant)'
                        : 'var(--md-sys-color-surface)',
                      border: '1px solid var(--md-sys-color-outline-variant)',
                      borderRadius: '8px',
                      cursor: actioning ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      width: '100%',
                    }}
                    title={`Log a copy of ${dish.dish_name}`}
                  >
                    <span className="type-body" style={{ fontWeight: 500 }}>
                      {dish.dish_name}
                    </span>
                    <span
                      className="type-label"
                      style={{ color: 'var(--md-sys-color-on-surface-variant)', flexShrink: 0 }}
                    >
                      {dish.kcal} kcal
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── DayPage ───────────────────────────────────────────────────────────────────

export default function StandardsPage() {
  const [selectedDate, setSelectedDate] = useState<string>(() => todayIso());
  const [payload,     setPayload]     = useState<DayPagePayload | null>(null);
  const [isLoading,   setIsLoading]   = useState(true);
  const [error,       setError]       = useState<ApiError | null>(null);
  const [actionError,  setActionError]  = useState<ApiError | null>(null);
  const [actioningId,  setActioningId]  = useState<string | null>(null);

  const isToday = useMemo(() => selectedDate === todayIso(), [selectedDate]);

  const fetchPayload = useCallback(async (dateStr: string) => {
    setIsLoading(true);
    setError(null);
    const url = `/food/day?date=${dateStr}`;
    const res = await apiFetch<DayPagePayload>(url);
    setIsLoading(false);
    if (isApiError(res)) {
      setError(res);
    } else {
      setPayload(res as DayPagePayload);
    }
  }, []);

  useEffect(() => {
    fetchPayload(selectedDate);
  }, [fetchPayload, selectedDate]);

  // ── Date navigation ─────────────────────────────────────────────────────────

  function handlePrevDay() {
    setSelectedDate((prev) => {
      const d = new Date(prev + 'T00:00:00');
      d.setDate(d.getDate() - 1);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    });
  }

  function handleNextDay() {
    if (isToday) return;
    setSelectedDate((prev) => {
      const d = new Date(prev + 'T00:00:00');
      d.setDate(d.getDate() + 1);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    });
  }

  function handleDateInput(value: string) {
    if (value) setSelectedDate(value);
  }

  // ── Copy a today entry ─────────────────────────────────────────────────────

  async function handleCopy(id: string) {
    setActionError(null);
    setActioningId(id);
    try {
      const res = await apiFetch<unknown>(`/food/entries/${id}/copy`, { method: 'POST' });
      if (isApiError(res)) setActionError(res);
      else await fetchPayload(selectedDate);
    } finally {
      setActioningId(null);
    }
  }

  // ── Delete a today entry ────────────────────────────────────────────────────

  async function handleDelete(id: string) {
    setActionError(null);
    setActioningId(id);
    try {
      const res = await apiFetch<null>(`/food/entries/${id}`, { method: 'DELETE' });
      if (isApiError(res)) setActionError(res);
      else await fetchPayload(selectedDate);
    } finally {
      setActioningId(null);
    }
  }

  // ── Log copy from standards section ────────────────────────────────────────

  async function handleLogCopy(standardId: string) {
    setActionError(null);
    setActioningId(standardId);
    try {
      const res = await apiFetch<unknown>(`/food/standards/${standardId}/log`, { method: 'POST' });
      if (isApiError(res)) setActionError(res);
      else await fetchPayload(selectedDate);
    } finally {
      setActioningId(null);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Day</h1>
        </div>
        <Skeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Day</h1>
        </div>
        <ErrorCard error={error} />
      </div>
    );
  }

  const todayEntries = payload?.today_entries ?? [];
  const standards    = payload?.standards     ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="type-display">Day</h1>
      </div>

      {/* Date navigation controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <button
          className="btn-outlined"
          onClick={handlePrevDay}
          title="Previous day"
          style={{ padding: '4px 12px', fontWeight: 600, fontSize: '1rem' }}
        >
          &#8592;
        </button>
        <input
          type="date"
          value={selectedDate}
          max={todayIso()}
          onChange={(e) => handleDateInput(e.target.value)}
          style={{
            padding: '4px 8px',
            border: '1px solid var(--md-sys-color-outline)',
            borderRadius: '4px',
            background: 'var(--md-sys-color-surface)',
            color: 'var(--md-sys-color-on-surface)',
            fontSize: '0.9rem',
          }}
        />
        <button
          className="btn-outlined"
          onClick={handleNextDay}
          disabled={isToday}
          title="Next day"
          style={{ padding: '4px 12px', fontWeight: 600, fontSize: '1rem' }}
        >
          &#8594;
        </button>
      </div>

      {actionError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={actionError} />
        </div>
      )}

      <TodaySection
        entries={todayEntries}
        onCopy={handleCopy}
        onDelete={handleDelete}
        actioningId={actioningId}
      />

      <StandardsSection
        standards={standards}
        onLogCopy={handleLogCopy}
        isActioning={actioningId}
      />
    </div>
  );
}
