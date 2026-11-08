/** History: finished and uploading runs with sync state, paginated. */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { fmtDateTime, fmtDistance, fmtDuration, fmtHr, fmtPace, syncLabel } from './format';

export interface RunRow {
  id: string; status: string; sync_state: string; started_at: string | null; finished_at: string | null;
  elapsed_s: number | null; moving_s: number | null; distance_m: number | null; avg_pace_s_per_km: number | null;
  avg_hr: number | null; max_hr: number | null; category: string | null; route_id: string | null; route_name: string | null; comment: string | null; device_name: string | null;
  location_count: number; hr_count: number;
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

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
