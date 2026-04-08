/**
 * SeriesDetailPage — full measurement history for a single series.
 *
 * Features:
 *  - Dataset table of measurements (value, recorded_at) with edit and delete actions
 *  - Add measurement form (value + recorded_at)
 *  - Delete series button (navigates back to list on success)
 *
 * Source of truth: Sprint01/20_design/architecture.json internal_flow[3] (detail_read)
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

// ── Component ──────────────────────────────────────────────────────────────────

export default function SeriesDetailPage() {
  const { label_id } = useParams<{ label_id: string }>();
  const navigate = useNavigate();

  const [rows, setRows]             = useState<MeasurementRow[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  // Add measurement form state
  const [addValue, setAddValue]           = useState('');
  const [addRecordedAt, setAddRecordedAt] = useState('');
  const [adding, setAdding]               = useState(false);
  const [addError, setAddError]           = useState<string | null>(null);

  // Edit state: which row is being edited
  const [editId, setEditId]               = useState<string | null>(null);
  const [editValue, setEditValue]         = useState('');
  const [editRecordedAt, setEditRecordedAt] = useState('');
  const [editError, setEditError]         = useState<string | null>(null);

  const [deleteError, setDeleteError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!label_id) return;
    setLoading(true);
    setError(null);
    const result = await apiFetch<Dataset>(`/series/${label_id}`);
    if (isApiError(result)) {
      setError(result.error.message);
    } else {
      setRows(result.rows as MeasurementRow[]);
    }
    setLoading(false);
  }, [label_id]);

  useEffect(() => { load(); }, [load]);

  // ── Add measurement ──────────────────────────────────────────────────────────

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    setAddError(null);
    const result = await apiFetch(
      `/series/${label_id}/measurements`,
      {
        method: 'POST',
        body: JSON.stringify({ value: parseFloat(addValue), recorded_at: addRecordedAt }),
      },
    );
    setAdding(false);
    if (isApiError(result)) {
      setAddError(result.error.message);
    } else {
      setAddValue('');
      setAddRecordedAt('');
      load();
    }
  }

  // ── Edit measurement ─────────────────────────────────────────────────────────

  function startEdit(row: MeasurementRow) {
    setEditId(row.id);
    setEditValue(String(row.value));
    setEditRecordedAt(row.recorded_at);
    setEditError(null);
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editId) return;
    setEditError(null);
    const result = await apiFetch(
      `/series/${label_id}/measurements/${editId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ value: parseFloat(editValue), recorded_at: editRecordedAt }),
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

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: '1rem', maxWidth: '700px' }}>
      <button onClick={() => navigate('/series')} style={{ marginBottom: '1rem', cursor: 'pointer' }}>
        ← Back to series
      </button>

      <h2 style={{ marginBottom: '0.5rem' }}>Measurements</h2>
      <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: '1rem' }}>
        Series ID: {label_id}
      </p>

      {/* Delete series */}
      <div style={{ marginBottom: '1.5rem' }}>
        <button
          onClick={handleDeleteSeries}
          style={{ background: '#8b2020', color: '#fff', border: 'none', padding: '0.4rem 0.8rem', borderRadius: '4px', cursor: 'pointer' }}
        >
          Delete series
        </button>
        {deleteError && (
          <ErrorCard error={{ error: { code: 'DELETE_ERROR', message: deleteError, request_id: '' } }} />
        )}
      </div>

      {/* Add measurement form */}
      <form onSubmit={handleAdd} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <input
          type="number"
          step="any"
          placeholder="Value"
          value={addValue}
          onChange={e => setAddValue(e.target.value)}
          required
          style={{ padding: '0.4rem', borderRadius: '4px', border: '1px solid #444', background: '#121220', color: '#fff', width: '120px' }}
        />
        <input
          type="datetime-local"
          value={addRecordedAt}
          onChange={e => setAddRecordedAt(e.target.value)}
          required
          style={{ padding: '0.4rem', borderRadius: '4px', border: '1px solid #444', background: '#121220', color: '#fff' }}
        />
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
        <p style={{ color: '#888' }}>No measurements yet. Add one above.</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #2e2e3e', color: '#888' }}>
              <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Recorded at</th>
              <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>Value</th>
              <th style={{ padding: '0.4rem 0.5rem' }}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id} style={{ borderBottom: '1px solid #1e1e2e' }}>
                {editId === row.id ? (
                  <>
                    <td colSpan={2} style={{ padding: '0.4rem 0.5rem' }}>
                      <form onSubmit={handleEdit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <input
                          type="number"
                          step="any"
                          value={editValue}
                          onChange={e => setEditValue(e.target.value)}
                          required
                          style={{ padding: '0.3rem', borderRadius: '4px', border: '1px solid #444', background: '#121220', color: '#fff', width: '100px' }}
                        />
                        <input
                          type="datetime-local"
                          value={editRecordedAt.slice(0, 16)}
                          onChange={e => setEditRecordedAt(e.target.value)}
                          required
                          style={{ padding: '0.3rem', borderRadius: '4px', border: '1px solid #444', background: '#121220', color: '#fff' }}
                        />
                        <button type="submit" style={{ cursor: 'pointer' }}>Save</button>
                        <button type="button" onClick={() => setEditId(null)} style={{ cursor: 'pointer' }}>Cancel</button>
                      </form>
                      {editError && <span style={{ color: '#f88', fontSize: '0.8rem' }}>{editError}</span>}
                    </td>
                    <td></td>
                  </>
                ) : (
                  <>
                    <td style={{ padding: '0.4rem 0.5rem', color: '#a0a0b0' }}>{row.recorded_at}</td>
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
                        style={{ cursor: 'pointer', fontSize: '0.8rem', background: '#5a1010', color: '#fff', border: 'none', borderRadius: '3px' }}
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
