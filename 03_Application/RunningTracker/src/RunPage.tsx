/**
 * Run page: a Free Run is started on the phone only. Here the user prepares runs that the phone downloads
 * (create, list, delete).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { fmtDateTime, fmtDuration } from './format';
import type { RouteRow } from './RoutesPage';

interface PreparedRow {
  id: string; short_id: string; title: string | null; planned_for: string | null;
  expires_at: string; is_expired: boolean; created_at: string; route_name: string | null; ghost_label: string | null;
}

interface RouteRunRow {
  id: string; started_at: string; moving_s: number | null; category: string | null;
  ghost_eligible: boolean; is_latest: boolean; is_fastest: boolean;
}

export default function RunPage() {
  const [rows, setRows] = useState<PreparedRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [routes, setRoutes] = useState<RouteRow[]>([]);
  const [routeId, setRouteId] = useState('');
  const [ghost, setGhost] = useState('none');
  const [candidates, setCandidates] = useState<RouteRunRow[]>([]);

  const load = useCallback(async () => {
    const res = await apiFetch<Dataset>('/runningtracker/prepared-runs');
    if (isApiError(res)) setError(res);
    else { setError(null); setRows(res.rows as unknown as PreparedRow[]); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiFetch<Dataset>('/runningtracker/routes').then((res) => { if (!isApiError(res)) setRoutes(res.rows as unknown as RouteRow[]); });
  }, []);
  useEffect(() => {
    setGhost('none');
    if (!routeId) { setCandidates([]); return; }
    apiFetch<Dataset>(`/runningtracker/routes/${routeId}/runs`).then((res) => {
      if (!isApiError(res)) setCandidates((res.rows as unknown as RouteRunRow[]).filter((r) => r.ghost_eligible));
    });
  }, [routeId]);

  const create = async () => {
    setBusy(true);
    const res = await apiFetch<Dataset>('/runningtracker/prepared-runs', {
      method: 'POST',
      body: JSON.stringify({ title: title.trim() === '' ? null : title.trim(), route_id: routeId === '' ? null : routeId, ghost: routeId === '' ? 'none' : ghost }),
    });
    setBusy(false);
    if (isApiError(res)) { setError(res); return; }
    setTitle('');
    load();
  };

  const remove = async (id: string) => {
    const res = await apiFetch<Dataset>(`/runningtracker/runs/${id}`, { method: 'DELETE' });
    if (isApiError(res)) { setError(res); return; }
    load();
  };

  return (
    <div className="running-page">
      <h2 className="type-headline">Run</h2>
      <div className="running-card">
        <strong>Free Run</strong>
        <span className="running-muted">
          A Free Run is started on the phone (AtlasPhone, Running Screen) and needs no preparation. It works without
          Atlas and syncs when the phone reaches Atlas again.
        </span>
      </div>

      <div className="running-card">
        <strong>Prepare a run</strong>
        <span className="running-muted">The phone lists prepared runs and downloads one; it can then start offline.</span>
        <label htmlFor="route"><strong>Route</strong></label>
        <select id="route" className="running-input" value={routeId} onChange={(e) => setRouteId(e.target.value)}>
          <option value="">Free run (no route)</option>
          {routes.map((r) => <option key={r.id} value={r.id}>{r.name} ({(r.reference_distance_m / 1000).toFixed(2)} km)</option>)}
        </select>
        {routeId !== '' && (
          <>
            <label htmlFor="ghost"><strong>Ghost runner</strong></label>
            <select id="ghost" className="running-input" value={ghost} onChange={(e) => setGhost(e.target.value)}>
              <option value="none">No ghost</option>
              {candidates.length > 0 && <option value="latest">Latest run</option>}
              {candidates.length > 0 && <option value="fastest">Fastest run</option>}
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {fmtDateTime(c.started_at)} · {fmtDuration(c.moving_s)}{c.category ? ` · ${c.category}` : ''}
                </option>
              ))}
            </select>
            {candidates.length === 0 && <span className="running-muted">No run on this route can be a ghost yet.</span>}
          </>
        )}
        <div className="running-row">
          <input className="running-input" placeholder="Title (optional)" aria-label="Title" value={title}
                 onChange={(e) => setTitle(e.target.value)} />
          <button className="running-btn primary" disabled={busy} onClick={create}>Prepare run</button>
        </div>
      </div>

      {error && <ErrorCard error={error} />}
      {rows === null && !error && <Skeleton />}
      {rows !== null && rows.length === 0 && <span className="running-muted">No prepared runs.</span>}
      {rows?.map((r) => (
        <div className="running-card" key={r.id} data-testid="prepared-run">
          <div className="running-row spread">
            <strong>{r.title ?? 'Untitled run'}</strong>
            <span className="running-row">
              {r.is_expired && <span className="running-chip expired">Expired</span>}
              <button className="running-btn danger" onClick={() => remove(r.id)} aria-label={`Delete ${r.title ?? r.short_id}`}>Delete</button>
            </span>
          </div>
          <span className="running-muted">Code {r.short_id} · expires {fmtDateTime(r.expires_at)}</span>
          {r.route_name && <span className="running-muted">Route {r.route_name}{r.ghost_label ? ` · ghost ${r.ghost_label}` : ' · no ghost'}</span>}
        </div>
      ))}
    </div>
  );
}
