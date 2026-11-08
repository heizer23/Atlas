/** Routes: the route library (name, distance, runs, latest run, best time) with rename/description edit and delete. No map. */

import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { DASH, fmtDateTime, fmtDistance, fmtDuration } from './format';

export interface RouteRow {
  id: string; name: string; description: string | null; reference_distance_m: number; is_loop: boolean;
  run_count: number; latest_run_at: string | null; best_moving_s: number | null; created_at: string;
}

export default function RoutesPage() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const load = useCallback(async () => {
    const res = await apiFetch<Dataset>('/runningtracker/routes');
    if (isApiError(res)) setError(res); else { setError(null); setData(res); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const startEdit = (r: RouteRow) => { setEditing(r.id); setName(r.name); setDescription(r.description ?? ''); };
  const save = async (id: string) => {
    // Empty description is sent as null (clears it); the name is always sent and must not be blank.
    const body = { name: name.trim(), description: description.trim() === '' ? null : description.trim() };
    const res = await apiFetch<Dataset>(`/runningtracker/routes/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
    if (isApiError(res)) { setError(res); return; }
    setEditing(null); setError(null); load();
  };
  const remove = async (r: RouteRow) => {
    if (!window.confirm(`Delete route "${r.name}"?`)) return;
    const res = await apiFetch<Dataset>(`/runningtracker/routes/${r.id}`, { method: 'DELETE' });
    if (isApiError(res)) { setError(res); return; }
    setError(null); load();
  };

  const rows = (data?.rows ?? []) as unknown as RouteRow[];
  return (
    <div className="running-page">
      <h2 className="type-headline">Routes</h2>
      {error && <ErrorCard error={error} />}
      {!data && !error && <Skeleton />}
      {data && rows.length === 0 && (
        <div className="running-card" data-testid="empty-routes">
          <strong>No routes yet</strong>
          <span className="running-muted">Open a completed run in History and choose "Create route from this run".</span>
        </div>
      )}
      {rows.map((r) => (
        <div className="running-card" key={r.id} data-testid="route-row">
          {editing === r.id ? (
            <>
              <input className="running-input" aria-label="Route name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
              <textarea className="running-input running-textarea" aria-label="Route description" value={description} onChange={(e) => setDescription(e.target.value)} />
              <div className="running-row">
                <button className="running-btn primary" onClick={() => save(r.id)}>Save</button>
                <button className="running-btn" onClick={() => setEditing(null)}>Cancel</button>
              </div>
            </>
          ) : (
            <>
              <div className="running-row spread">
                <strong>{r.name}</strong>
                <span className="running-chip">{r.is_loop ? 'Loop' : 'One way'}</span>
              </div>
              {r.description && <span className="running-muted">{r.description}</span>}
              <div className="running-stats">
                <span><span className="running-muted">Distance</span><br />{fmtDistance(r.reference_distance_m)}</span>
                <span><span className="running-muted">Runs</span><br />{r.run_count}</span>
                <span><span className="running-muted">Latest</span><br />{r.latest_run_at ? fmtDateTime(r.latest_run_at) : DASH}</span>
                <span><span className="running-muted">Best time</span><br />{r.best_moving_s != null ? fmtDuration(r.best_moving_s) : DASH}</span>
              </div>
              <div className="running-row">
                <button className="running-btn" onClick={() => startEdit(r)}>Edit</button>
                <button className="running-btn danger" onClick={() => remove(r)}>Delete</button>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
