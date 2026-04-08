/**
 * SeriesListPage — list all numeric series with sparkline and latest value.
 *
 * Custom list component — NOT standard platform TableView.
 * sparkline_values is a JSON-encoded float array; parsed here.
 * Row click navigates to /series/:label_id (detail page).
 *
 * Source of truth: Sprint01/20_design/architecture.json internal_flow[2] (list_read)
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LineChart,
  Line,
  ResponsiveContainer,
} from 'recharts';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import CreateForm from '@platform-ui/components/CreateForm';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Dataset, FormField, ApiError } from '@platform-ui/api/types';

// ── Types ──────────────────────────────────────────────────────────────────────

interface SeriesRow {
  id: string;
  label_name: string;
  latest_value: number | null;
  sparkline_values: string; // JSON-encoded float array
}

// ── Form fields ────────────────────────────────────────────────────────────────

const CREATE_FIELDS: FormField[] = [
  { key: 'label_name', label: 'Series name', type: 'string', required: true, placeholder: 'e.g. Weight' },
];

// ── Inline sparkline ───────────────────────────────────────────────────────────

function InlineSparkline({ values }: { values: number[] }) {
  if (values.length === 0) return <span style={{ color: '#555', fontSize: '0.8rem' }}>—</span>;
  const data = values.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={28}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="v"
          dot={false}
          stroke="#7c6af5"
          strokeWidth={1.5}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function SeriesListPage() {
  const navigate = useNavigate();

  const [rows, setRows]       = useState<SeriesRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await apiFetch<Dataset>('/series');
    if (isApiError(result)) {
      setError(result.error.message);
    } else {
      setRows(result.rows as SeriesRow[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(values: Record<string, unknown>): Promise<ApiError | void> {
    const result = await apiFetch<{ label_id: string; label_name: string }>(
      '/series',
      { method: 'POST', body: JSON.stringify({ label_name: values['label_name'] }) },
    );
    if (isApiError(result)) {
      return result;
    }
    load();
  }

  function parseSparkline(raw: string): number[] {
    try { return JSON.parse(raw) as number[]; }
    catch { return []; }
  }

  return (
    <div style={{ padding: '1rem', maxWidth: '800px' }}>
      <h2>Numeric Series</h2>

      {/* Create form */}
      <div style={{ marginBottom: '1.5rem' }}>
        <CreateForm
          title="Add Series"
          fields={CREATE_FIELDS}
          onSubmit={handleCreate}
          submitLabel="Add Series"
        />
      </div>

      {/* List */}
      {loading && <Skeleton />}
      {error && (
        <ErrorCard error={{ error: { code: 'LOAD_ERROR', message: error, request_id: '' } }} />
      )}

      {!loading && !error && rows.length === 0 && (
        <p style={{ color: '#888' }}>No series yet. Add one above.</p>
      )}

      {!loading && !error && rows.map((row) => {
        const sparkData = parseSparkline(row.sparkline_values);
        return (
          <div
            key={row.id}
            onClick={() => navigate(`/series/${row.id}`)}
            style={{
              display: 'grid',
              gridTemplateColumns: '160px 1fr 80px',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.6rem 1rem',
              marginBottom: '0.4rem',
              background: '#1e1e2e',
              borderRadius: '6px',
              cursor: 'pointer',
              border: '1px solid #2e2e3e',
            }}
          >
            <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.label_name}
            </span>

            <div style={{ width: '100%', height: '28px' }}>
              <InlineSparkline values={sparkData} />
            </div>

            <span style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#a0a0b0' }}>
              {row.latest_value !== null && row.latest_value !== undefined
                ? row.latest_value.toLocaleString()
                : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}
