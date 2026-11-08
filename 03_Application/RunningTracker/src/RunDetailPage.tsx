/** Run detail: summary, pace and heart-rate charts, km splits, comment (U1 round trip). No map. */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import LineChart from '@platform-ui/components/LineChart';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { DASH, fmtDateTime, fmtDistance, fmtDuration, fmtHr, fmtPace, syncLabel } from './format';
import type { RunRow } from './HistoryPage';
import type { RouteRow } from './RoutesPage';

interface SplitRow { id: string; km: number; distance_m: number; duration_s: number; pace_s_per_km: number; avg_hr: number | null; partial: boolean }

export default function RunDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunRow | null>(null);
  const [splits, setSplits] = useState<SplitRow[] | null>(null);
  const [pace, setPace] = useState<Dataset | null>(null);
  const [hr, setHr] = useState<Dataset | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [comment, setComment] = useState('');
  const [category, setCategory] = useState('');
  const [saving, setSaving] = useState(false);
  const [routes, setRoutes] = useState<RouteRow[]>([]);
  const [newRoute, setNewRoute] = useState('');

  const load = useCallback(async () => {
    const [r, s, p, h] = await Promise.all([
      apiFetch<Dataset>(`/runningtracker/runs/${id}`),
      apiFetch<Dataset>(`/runningtracker/runs/${id}/splits`),
      apiFetch<Dataset>(`/runningtracker/runs/${id}/series?metric=pace`),
      apiFetch<Dataset>(`/runningtracker/runs/${id}/series?metric=heart_rate`),
    ]);
    for (const res of [r, s, p, h]) if (isApiError(res)) { setError(res); return; }
    const rt = await apiFetch<Dataset>('/runningtracker/routes');
    if (!isApiError(rt)) setRoutes(rt.rows as unknown as RouteRow[]);
    const row = (r as Dataset).rows[0] as unknown as RunRow;
    setRun(row);
    setComment(row.comment ?? '');
    setCategory(row.category ?? '');
    setSplits((s as Dataset).rows as unknown as SplitRow[]);
    setPace(p as Dataset);
    setHr(h as Dataset);
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const saveComment = async () => {
    setSaving(true);
    // Empty textarea -> null (not omission, not an empty string): invariant U1.
    const body = {
      comment: comment.trim() === '' ? null : comment,
      category: category.trim() === '' ? null : category.trim(),
    };
    const res = await apiFetch<Dataset>(`/runningtracker/runs/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
    setSaving(false);
    if (isApiError(res)) { setError(res); return; }
    const row = res.rows[0] as unknown as RunRow;
    setRun(row);
    setComment(row.comment ?? '');
    setCategory(row.category ?? '');
  };

  const linkRoute = async (routeId: string) => {
    // '' (no route) is sent as null to unlink; a route id links the run.
    const res = await apiFetch<Dataset>(`/runningtracker/runs/${id}`, { method: 'PATCH', body: JSON.stringify({ route_id: routeId === '' ? null : routeId }) });
    if (isApiError(res)) { setError(res); return; }
    setRun(res.rows[0] as unknown as RunRow);
    load();
  };

  const createRoute = async () => {
    const res = await apiFetch<Dataset>('/runningtracker/routes', { method: 'POST', body: JSON.stringify({ run_id: id, name: newRoute.trim() }) });
    if (isApiError(res)) { setError(res); return; }
    setNewRoute('');
    load();
  };

  const remove = async () => {
    if (!window.confirm('Delete this run and all its samples?')) return;
    const res = await apiFetch<Dataset>(`/runningtracker/runs/${id}`, { method: 'DELETE' });
    if (isApiError(res)) { setError(res); return; }
    navigate('/running/history');
  };

  if (error) return <div className="running-page"><ErrorCard error={error} /></div>;
  if (!run) return <div className="running-page"><Skeleton /></div>;

  const hasPace = (pace?.rows.length ?? 0) > 0;
  const hasHr = (hr?.rows.length ?? 0) > 0;

  return (
    <div className="running-page">
      <div className="running-row spread">
        <button className="running-btn" onClick={() => navigate('/running/history')}>Back</button>
        <span className={`running-chip ${run.sync_state}`}>{syncLabel(run.sync_state)}</span>
      </div>
      <h2 className="type-headline">{fmtDateTime(run.started_at)}</h2>

      <div className="running-card">
        <div className="running-stats">
          <span><span className="running-muted">Distance</span><div className="running-stat-value">{fmtDistance(run.distance_m)}</div></span>
          <span><span className="running-muted">Duration</span><div className="running-stat-value">{fmtDuration(run.elapsed_s)}</div></span>
          <span><span className="running-muted">Moving</span><div className="running-stat-value">{fmtDuration(run.moving_s)}</div></span>
          <span><span className="running-muted">Avg pace</span><div className="running-stat-value">{fmtPace(run.avg_pace_s_per_km)}</div></span>
          <span><span className="running-muted">Avg HR</span><div className="running-stat-value">{fmtHr(run.avg_hr)}</div></span>
          <span><span className="running-muted">Max HR</span><div className="running-stat-value">{fmtHr(run.max_hr)}</div></span>
        </div>
        <span className="running-muted">Device {run.device_name ?? DASH} · {run.location_count} GPS and {run.hr_count} HR samples</span>
      </div>

      {run.status !== 'complete' && (
        <div className="running-warn">This run is still uploading; charts and splits appear after the phone finishes syncing.</div>
      )}

      <div className="running-card" data-testid="pace-chart">
        {hasPace
          ? <LineChart dataset={pace} mapping={{ x: 't_label', y: 'value', aggregation: 'avg' }} options={{ title: 'Pace over time (s/km)' }} />
          : <span className="running-muted">No pace data.</span>}
      </div>
      <div className="running-card" data-testid="hr-chart">
        {hasHr
          ? <LineChart dataset={hr} mapping={{ x: 't_label', y: 'value', aggregation: 'avg' }} options={{ title: 'Heart rate over time (bpm)' }} />
          : <span className="running-muted">No heart-rate data.</span>}
      </div>

      <div className="running-card">
        <strong>Splits</strong>
        {splits && splits.length > 0 ? (
          <table className="running-table" data-testid="splits">
            <thead><tr><th>Km</th><th>Time</th><th>Pace</th><th>Avg HR</th></tr></thead>
            <tbody>
              {splits.map((s) => (
                <tr key={s.id}>
                  <td>{s.partial ? `${(s.distance_m / 1000).toFixed(2)} km` : s.km}</td>
                  <td>{fmtDuration(s.duration_s)}</td>
                  <td>{fmtPace(s.pace_s_per_km)}</td>
                  <td>{fmtHr(s.avg_hr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <span className="running-muted">No splits.</span>}
      </div>

      <div className="running-card" data-testid="route-card">
        <label htmlFor="route"><strong>Route</strong></label>
        <select id="route" className="running-input" value={run.route_id ?? ''} onChange={(e) => linkRoute(e.target.value)}>
          <option value="">No route</option>
          {routes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        {run.status === 'complete' && (
          <div className="running-row">
            <input className="running-input" aria-label="New route name" maxLength={120} placeholder="Name for a new route" value={newRoute} onChange={(e) => setNewRoute(e.target.value)} />
            <button className="running-btn" disabled={newRoute.trim() === ''} onClick={createRoute}>Create route from this run</button>
          </div>
        )}
      </div>

      <div className="running-card">
        <label htmlFor="category"><strong>Category</strong></label>
        <input id="category" className="running-input" maxLength={60} placeholder="e.g. Easy Continuous" value={category} onChange={(e) => setCategory(e.target.value)} />
        <label htmlFor="comment"><strong>Comment</strong></label>
        <textarea id="comment" className="running-input running-textarea" value={comment} onChange={(e) => setComment(e.target.value)} />
        <div className="running-row">
          <button className="running-btn primary" disabled={saving} onClick={saveComment}>Save</button>
          <button className="running-btn danger" onClick={remove}>Delete run</button>
        </div>
      </div>
    </div>
  );
}
