/** History: finished and uploading runs with sync state, paginated. */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import LineChart from '@platform-ui/components/LineChart';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { fmtDateTime, fmtDistance, fmtDuration, fmtHr, fmtPace, syncLabel } from './format';

export interface RunRow {
  id: string; status: string; sync_state: string; started_at: string | null; finished_at: string | null;
  elapsed_s: number | null; moving_s: number | null; distance_m: number | null; avg_pace_s_per_km: number | null;
  avg_hr: number | null; max_hr: number | null; avg_cadence_spm: number | null; category: string | null; route_id: string | null; route_name: string | null; comment: string | null; device_name: string | null;
  location_count: number; hr_count: number;
}

/** Latest efficiency factor vs the mean of up to 5 runs before it. */
function EfficiencyHeadline({ rows }: { rows: { efficiency: number }[] }) {
  const latest = rows[rows.length - 1].efficiency;
  const prev = rows.slice(-6, -1).map((r) => r.efficiency);
  const base = prev.reduce((a, b) => a + b, 0) / prev.length;
  const pct = ((latest - base) / base) * 100;
  return (
    <span data-testid="efficiency-headline">
      <strong>{latest.toFixed(3)}</strong> latest · {pct >= 0 ? '+' : ''}{pct.toFixed(1)}% vs previous {prev.length} run{prev.length === 1 ? '' : 's'}
    </span>
  );
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [trend, setTrend] = useState<Dataset | null>(null);
  const [eff, setEff] = useState<Dataset | null>(null);

  useEffect(() => {
    apiFetch<Dataset>('/runningtracker/runs/recovery-trend').then((res) => { if (!isApiError(res)) setTrend(res); });
    apiFetch<Dataset>('/runningtracker/runs/efficiency-trend').then((res) => { if (!isApiError(res)) setEff(res); });
  }, []);

  useEffect(() => {
    setData(null);
    apiFetch<Dataset>(`/runningtracker/runs?page=${page}&page_size=25`).then((res) => {
      if (isApiError(res)) setError(res);
      else { setError(null); setData(res); }
    });
  }, [page]);

  const rows = (data?.rows ?? []) as unknown as RunRow[];
  const totalPages = data ? Math.max(1, Math.ceil(data.meta.total / data.meta.page_size)) : 1;

  return (
    <div className="running-page">
      <h2 className="type-headline">History</h2>
      {error && <ErrorCard error={error} />}
      {!data && !error && <Skeleton />}
      {data && rows.length === 0 && (
        <div className="running-card" data-testid="empty-history">
          <strong>No runs yet</strong>
          <span className="running-muted">Record a run with AtlasPhone; it appears here once it has synced.</span>
        </div>
      )}
      {eff && eff.rows.length > 1 && (
        <div className="running-card" data-testid="efficiency-trend">
          <strong>Aerobic efficiency over time</strong>
          <span className="running-muted">Speed (m/min) divided by average heart rate; higher = faster at the same effort. Compare runs of similar type, and judge the trend, not single runs.</span>
          <EfficiencyHeadline rows={eff.rows as unknown as { efficiency: number }[]} />
          <LineChart dataset={eff} mapping={{ x: 'when', y: 'efficiency', aggregation: 'avg' }} options={{ title: 'Efficiency factor' }} />
        </div>
      )}
      {trend && trend.rows.length > 0 && (
        <div className="running-card" data-testid="recovery-trend">
          <strong>Heart-rate recovery over time</strong>
          <span className="running-muted">Beats dropped 60 s / 120 s after the run ends; higher = faster recovery. Compare runs with the same cool-down posture and similar effort.</span>
          <LineChart dataset={trend} mapping={{ x: 'when', y: 'hrr60', aggregation: 'avg' }} options={{ title: 'HRR60 (bpm)' }} />
          <LineChart dataset={trend} mapping={{ x: 'when', y: 'hrr120', aggregation: 'avg' }} options={{ title: 'HRR120 (bpm)' }} />
        </div>
      )}
      {rows.map((r) => (
        <div className="running-card clickable" key={r.id} data-testid="run-row" onClick={() => navigate(`/running/history/${r.id}`)}>
          <div className="running-row spread">
            <strong>{fmtDateTime(r.started_at)}{r.category ? ` · ${r.category}` : ''}{r.route_name ? ` · ${r.route_name}` : ''}</strong>
            <span className={`running-chip ${r.sync_state}`}>{syncLabel(r.sync_state)}</span>
          </div>
          <div className="running-stats">
            <span><span className="running-muted">Distance</span><br />{fmtDistance(r.distance_m)}</span>
            <span><span className="running-muted">Duration</span><br />{fmtDuration(r.elapsed_s)}</span>
            <span><span className="running-muted">Avg pace</span><br />{fmtPace(r.avg_pace_s_per_km)}</span>
            <span><span className="running-muted">Avg HR</span><br />{fmtHr(r.avg_hr)}</span>
          </div>
        </div>
      ))}
      {totalPages > 1 && (
        <div className="running-row">
          <button className="running-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="running-muted">Page {page} / {totalPages}</span>
          <button className="running-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
