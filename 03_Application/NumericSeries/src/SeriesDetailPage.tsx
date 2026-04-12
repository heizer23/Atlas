/**
 * SeriesDetailPage — full measurement history for a single series.
 *
 * Features:
 *  - Creation mode when label_id === 'new': single text input, POST /api/series, redirect
 *  - Dataset table of measurements (value, recorded_at) with edit and delete actions
 *  - Add measurement form: split date + time inputs (cross-platform, no datetime-local)
 *  - Delete series button (navigates back to list on success)
 *
 * Sprint03 changes:
 *   - Split date+time input: type=date + type=time, combined with browser UTC offset
 *   - All input inline styles updated to CSS theme tokens (no hardcoded hex)
 *   - Timestamp display formatted with toLocaleString() in browser local timezone
 *   - Table border colors use var(--md-sys-color-outline-variant)
 *
 * Source of truth: Sprint03_Chronos&UXpt2/10_architecture.json §internal_flow[5,6,7]
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Dataset, Row } from '@platform-ui/api/types';

// ── Types ──────────────────────────────────────────────────────────────────────

interface MeasurementRow extends Row {
  id: string;
  value: number;
  recorded_at: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Format a UTC/timezone-aware ISO-8601 timestamp for display in the browser's
 * local timezone.
 * Architecture: Sprint03/10_architecture.json §internal_flow[4] (timestamp_display)
 */
function formatTimestamp(raw: string): string {
  try {
    return new Date(raw).toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return raw;
  }
}

/**
 * Combine split date (YYYY-MM-DD) and time (HH:MM) inputs into a
 * timezone-aware ISO-8601 string using the browser's UTC offset.
 * Architecture: Sprint03/10_architecture.json §internal_flow[5] (datetime_input)
 */
function combineDateTime(date: string, time: string): string {
  const localStr = `${date}T${time}:00`;
  const d = new Date(localStr);
  const off = -d.getTimezoneOffset(); // minutes ahead of UTC
  const sign = off >= 0 ? '+' : '-';
  const hh = String(Math.floor(Math.abs(off) / 60)).padStart(2, '0');
  const mm = String(Math.abs(off) % 60).padStart(2, '0');
  return `${localStr}${sign}${hh}:${mm}`;
}

/**
 * Split an ISO-8601 timestamp string into [date, time] parts for pre-filling
 * the split inputs during edit mode. Converts through Date so the result is
 * in the browser's local timezone — consistent with combineDateTime.
 */
function splitDateTime(raw: string): [string, string] {
  const d = new Date(raw);
  const yyyy = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return [`${yyyy}-${mo}-${dd}`, `${hh}:${mi}`];
}

// ── Input style shared across all form inputs ─────────────────────────────────
const INPUT_STYLE: React.CSSProperties = {
  padding: '0.4rem',
  borderRadius: '4px',
  border: '1px solid var(--md-sys-color-outline-variant)',
  background: 'var(--md-sys-color-surface)',
  color: 'var(--md-sys-color-on-surface)',
  boxSizing: 'border-box',
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function SeriesDetailPage() {
  const { label_id } = useParams<{ label_id: string }>();
  const navigate = useNavigate();

  const isNew = label_id === 'new';

  // ── Creation mode state ──────────────────────────────────────────────────────

  const [seriesName, setSeriesName]   = useState('');
  const [creating, setCreating]       = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // ── Detail mode state ────────────────────────────────────────────────────────

  const [rows, setRows]             = useState<MeasurementRow[]>([]);
  const [loading, setLoading]       = useState(!isNew);
  const [error, setError]           = useState<string | null>(null);

  // Add measurement form state — split date + time
  const [addDate, setAddDate]         = useState('');
  const [addTime, setAddTime]         = useState('');
  const [addValue, setAddValue]       = useState('');
  const [adding, setAdding]           = useState(false);
  const [addError, setAddError]       = useState<string | null>(null);

  // Edit state: which row is being edited
  const [editId, setEditId]           = useState<string | null>(null);
  const [editDate, setEditDate]       = useState('');
  const [editTime, setEditTime]       = useState('');
  const [editValue, setEditValue]     = useState('');
  const [editError, setEditError]     = useState<string | null>(null);

  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (isNew || !label_id) return;
    setLoading(true);
    setError(null);
    const result = await apiFetch<Dataset>(`/series/${label_id}`);
    if (isApiError(result)) {
      setError(result.error.message);
    } else {
      setRows(result.rows as MeasurementRow[]);
    }
    setLoading(false);
  }, [label_id, isNew]);

  useEffect(() => { load(); }, [load]);

  // ── Creation mode handler ────────────────────────────────────────────────────

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    const result = await apiFetch<{ label_id: string; label_name: string }>(
      '/series',
      { method: 'POST', body: JSON.stringify({ label_name: seriesName.trim() }) },
    );
    setCreating(false);
    if (isApiError(result)) {
      setCreateError(result.error.message);
    } else {
      navigate(`/series/${result.label_id}`);
    }
  }

  // ── Add measurement ──────────────────────────────────────────────────────────

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addDate || !addTime) return;
    setAdding(true);
    setAddError(null);
    const recorded_at = combineDateTime(addDate, addTime);
    const result = await apiFetch(
      `/series/${label_id}/measurements`,
      {
        method: 'POST',
        body: JSON.stringify({ value: parseFloat(addValue), recorded_at }),
      },
    );
    setAdding(false);
    if (isApiError(result)) {
      setAddError(result.error.message);
    } else {
      setAddValue('');
      setAddDate('');
      setAddTime('');
      load();
    }
  }

  // ── Edit measurement ─────────────────────────────────────────────────────────

  function startEdit(row: MeasurementRow) {
    setEditId(row.id);
    setEditValue(String(row.value));
    const [d, t] = splitDateTime(row.recorded_at);
    setEditDate(d);
    setEditTime(t);
    setEditError(null);
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editId || !editDate || !editTime) return;
    setEditError(null);
    const recorded_at = combineDateTime(editDate, editTime);
    const result = await apiFetch(
      `/series/${label_id}/measurements/${editId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ value: parseFloat(editValue), recorded_at }),
      },
    );
    if (isApiError(result)) {
      setEditError(result.error.message);
    } else {
      setEditId(null);
      load();
    }
  }

  // ── Delete measurement ───────────────────────────────────────────────────────

  async function handleDeleteMeasurement(id: string) {
    const result = await apiFetch(
      `/series/${label_id}/measurements/${id}`,
      { method: 'DELETE' },
    );
    if (isApiError(result)) {
      setDeleteError(result.error.message);
    } else {
      load();
    }
  }

  // ── Delete series ────────────────────────────────────────────────────────────

  async function handleDeleteSeries() {
    if (!confirm('Delete this series and all its measurements? This cannot be undone.')) return;
    const result = await apiFetch(`/series/${label_id}`, { method: 'DELETE' });
    if (isApiError(result)) {
      setDeleteError(result.error.message);
    } else {
      navigate('/series');
    }
  }

  // ── Creation mode render ─────────────────────────────────────────────────────

  if (isNew) {
    return (
      <div style={{ padding: '1rem', maxWidth: '480px' }}>
        <button onClick={() => navigate('/series')} style={{ marginBottom: '1rem', cursor: 'pointer' }}>
          ← Back to series
        </button>

        <h2 style={{ marginBottom: '1rem' }}>New Series</h2>

        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <label>
            <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Series name</span>
            <input
              type="text"
              placeholder="e.g. Weight"
              value={seriesName}
              onChange={e => setSeriesName(e.target.value)}
              required
              autoFocus
              style={{ ...INPUT_STYLE, width: '100%' }}
            />
          </label>
          <button type="submit" disabled={creating} style={{ padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer', alignSelf: 'flex-start' }}>
            {creating ? 'Creating…' : 'Create'}
          </button>
          {createError && (
            <ErrorCard error={{ error: { code: 'CREATE_ERROR', message: createError, request_id: '' } }} />
          )}
        </form>
      </div>
    );
  }

  // ── Detail mode render ───────────────────────────────────────────────────────

  return (
    <div style={{ padding: '1rem', maxWidth: '700px' }}>
      <button onClick={() => navigate('/series')} style={{ marginBottom: '1rem', cursor: 'pointer' }}>
        ← Back to series
      </button>

      <h2 style={{ marginBottom: '0.5rem' }}>Measurements</h2>
      <p style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: '0.85rem', marginBottom: '1rem' }}>
        Series ID: {label_id}
      </p>

      {/* Delete series */}
      <div style={{ marginBottom: '1.5rem' }}>
        <button
          onClick={handleDeleteSeries}
          style={{ background: 'var(--md-sys-color-error)', color: 'var(--md-sys-color-on-error)', border: 'none', padding: '0.4rem 0.8rem', borderRadius: '4px', cursor: 'pointer' }}
        >
          Delete series
        </button>
        {deleteError && (
          <ErrorCard error={{ error: { code: 'DELETE_ERROR', message: deleteError, request_id: '' } }} />
        )}
      </div>

      {/* Add measurement form — split date + time inputs */}
      <form onSubmit={handleAdd} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.2rem', color: 'var(--md-sys-color-on-surface-variant)' }}>Value</label>
          <input
            type="number"
            step="any"
            placeholder="Value"
            value={addValue}
            onChange={e => setAddValue(e.target.value)}
            required
            style={{ ...INPUT_STYLE, width: '110px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.2rem', color: 'var(--md-sys-color-on-surface-variant)' }}>Date</label>
          <input
            type="date"
            value={addDate}
            onChange={e => setAddDate(e.target.value)}
            required
            style={{ ...INPUT_STYLE }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.2rem', color: 'var(--md-sys-color-on-surface-variant)' }}>Time</label>
          <input
            type="time"
            value={addTime}
            onChange={e => setAddTime(e.target.value)}
            required
            style={{ ...INPUT_STYLE }}
          />
        </div>
        <button type="submit" disabled={adding} style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', cursor: 'pointer' }}>
          {adding ? 'Adding…' : 'Add measurement'}
        </button>
        {addError && (
          <ErrorCard error={{ error: { code: 'ADD_ERROR', message: addError, request_id: '' } }} />
        )}
      </form>

      {/* Measurements table */}
      {loading && <Skeleton />}
      {error && (
        <ErrorCard error={{ error: { code: 'LOAD_ERROR', message: error, request_id: '' } }} />
      )}

      {!loading && !error && rows.length === 0 && (
        <p style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>No measurements yet. Add one above.</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--md-sys-color-outline-variant)', color: 'var(--md-sys-color-on-surface-variant)' }}>
              <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Recorded at</th>
              <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>Value</th>
              <th style={{ padding: '0.4rem 0.5rem' }}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id} style={{ borderBottom: '1px solid var(--md-sys-color-outline-variant)' }}>
                {editId === row.id ? (
                  <>
                    <td colSpan={2} style={{ padding: '0.4rem 0.5rem' }}>
                      <form onSubmit={handleEdit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                        <input
                          type="number"
                          step="any"
                          value={editValue}
                          onChange={e => setEditValue(e.target.value)}
                          required
                          style={{ ...INPUT_STYLE, width: '90px' }}
                        />
                        <input
                          type="date"
                          value={editDate}
                          onChange={e => setEditDate(e.target.value)}
                          required
                          style={{ ...INPUT_STYLE }}
                        />
                        <input
                          type="time"
                          value={editTime}
                          onChange={e => setEditTime(e.target.value)}
                          required
                          style={{ ...INPUT_STYLE }}
                        />
                        <button type="submit" style={{ cursor: 'pointer' }}>Save</button>
                        <button type="button" onClick={() => setEditId(null)} style={{ cursor: 'pointer' }}>Cancel</button>
                      </form>
                      {editError && <span style={{ color: 'var(--md-sys-color-error)', fontSize: '0.8rem' }}>{editError}</span>}
                    </td>
                    <td></td>
                  </>
                ) : (
                  <>
                    <td style={{ padding: '0.4rem 0.5rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
                      {formatTimestamp(row.recorded_at)}
                    </td>
                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {typeof row.value === 'number' ? row.value.toLocaleString() : row.value}
                    </td>
                    <td style={{ padding: '0.4rem 0.5rem', whiteSpace: 'nowrap' }}>
                      <button
                        onClick={() => startEdit(row)}
                        style={{ marginRight: '0.4rem', cursor: 'pointer', fontSize: '0.8rem' }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteMeasurement(row.id)}
                        style={{ cursor: 'pointer', fontSize: '0.8rem', background: 'var(--md-sys-color-error)', color: 'var(--md-sys-color-on-error)', border: 'none', borderRadius: '3px' }}
                      >
                        Delete
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
