/**
 * FoodTracker ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 * All platform imports use the @platform-ui alias.
 *
 * Routes covered:
 *   /food              → FoodIntake (idle → preview → success state machine)
 *   /food/report       → ReportPage (Sprint 02 — reporting slice)
 *   /food/entries      → EntriesPage (Sprint 03 — entry overview with row actions)
 *   /food/entries/:id  → EntryDetailPage (Sprint 03 — entry detail and edit)
 */

import { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ReportPage from './ReportPage';
import EntriesPage from './EntriesPage';
import EntryDetailPage from './EntryDetailPage';
import StandardsPage from './StandardsPage';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

type FlowState = 'idle' | 'preview' | 'success';

interface PreviewData {
  logged_at:  string;
  meal_type:  string;
  dish_name:  string;
  items:      { name: string; quantity?: number; unit?: string }[];
  kcal:       number;
  protein_g:  number;
  carbs_g:    number;
  fat_g:      number;
  fiber_g:    number;
  good_fat_g: number;
  meat_g:     number;
  red_meat_g: number;
  sodium_mg:  number;
  alcohol_g:  number;
  confidence: number;
  notes:      string | null;
  quantity_g: number | null;
}

interface SuccessData {
  logged_at: string;
  meal_type: string;
  dish_name: string;
  kcal:      number;
}

// ── Preview field list ─────────────────────────────────────────────────────────

const PREVIEW_FIELDS: { key: keyof PreviewData; label: string }[] = [
  { key: 'logged_at',  label: 'Date / Time' },
  { key: 'meal_type',  label: 'Meal' },
  { key: 'dish_name',  label: 'Dish' },
  { key: 'quantity_g', label: 'Quantity (g)' },
  { key: 'kcal',       label: 'kcal' },
  { key: 'protein_g',  label: 'Protein (g)' },
  { key: 'carbs_g',    label: 'Carbs (g)' },
  { key: 'fat_g',      label: 'Fat (g)' },
  { key: 'fiber_g',    label: 'Fiber (g)' },
  { key: 'good_fat_g', label: 'Good Fat (g)' },
  { key: 'meat_g',     label: 'Meat (g)' },
  { key: 'red_meat_g', label: 'Red Meat (g)' },
  { key: 'sodium_mg',  label: 'Sodium (mg)' },
  { key: 'alcohol_g',  label: 'Alcohol (g)' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'notes',      label: 'Notes' },
];

// ── FoodIntake ─────────────────────────────────────────────────────────────────

export function FoodIntake() {
  const [flow,           setFlow]           = useState<FlowState>('idle');
  const [template,       setTemplate]       = useState<string | null>(null);
  const [templateErr,    setTemplateErr]    = useState<ApiError | null>(null);
  const [templateOpen,   setTemplateOpen]   = useState(false);
  const [pastedJson,     setPastedJson]     = useState('');
  const [preview,        setPreview]        = useState<PreviewData | null>(null);
  const [success,        setSuccess]        = useState<SuccessData | null>(null);
  const [formError,      setFormError]      = useState<ApiError | null>(null);
  const [inFlight,       setInFlight]       = useState(false);

  // Fetch template on mount.
  // apiFetch always JSON.parse()s the response body. The template endpoint
  // returns text/plain whose body is itself valid JSON, so apiFetch yields a
  // parsed JS object. We re-serialise it to a formatted string for display.
  useEffect(() => {
    apiFetch<unknown>('/food/template').then((res) => {
      if (isApiError(res)) {
        setTemplateErr(res);
      } else {
        setTemplate(JSON.stringify(res, null, 2));
      }
    });
  }, []);

  // ── Idle handlers ────────────────────────────────────────────────────────────

  function handleCopyTemplate() {
    if (template) {
      navigator.clipboard.writeText(template);
    }
  }

  async function handleLogMeal() {
    setFormError(null);
    setInFlight(true);
    try {
      const res = await apiFetch<{ preview: PreviewData }>('/food/validate', {
        method: 'POST',
        body: pastedJson,
      });
      if (isApiError(res)) {
        setFormError(res);
      } else {
        setPreview((res as { preview: PreviewData }).preview);
        setFlow('preview');
      }
    } finally {
      setInFlight(false);
    }
  }

  // ── Preview handlers ─────────────────────────────────────────────────────────

  function handleBack() {
    setFormError(null);
    setFlow('idle');
    // pastedJson is preserved — do not clear it
  }

  async function handleAccept() {
    setFormError(null);
    setInFlight(true);
    try {
      const res = await apiFetch<{ meta: object; schema: object[]; rows: object[] }>(
        '/food/meals',
        {
          method: 'POST',
          body: pastedJson,
        },
      );
      if (isApiError(res)) {
        setFormError(res);
      } else {
        // Extract key confirmation values from the first row of the Dataset response
        const dataset = res as { meta: object; schema: object[]; rows: Record<string, unknown>[] };
        const row = dataset.rows[0];
        setSuccess({
          logged_at: String(row['logged_at']),
          meal_type: String(row['meal_type']),
          dish_name: String(row['dish_name']),
          kcal:      Number(row['kcal']),
        });
        setFlow('success');
      }
    } finally {
      setInFlight(false);
    }
  }

  // ── Reset ────────────────────────────────────────────────────────────────────

  function handleLogAnother() {
    setFlow('idle');
    setPastedJson('');
    setPreview(null);
    setSuccess(null);
    setFormError(null);
  }

  // ── Render: idle ─────────────────────────────────────────────────────────────

  if (flow === 'idle') {
    return (
      <div className="page">
        <section style={{ marginBottom: 'var(--space-md)' }}>
          {/* Collapsible template disclosure — collapsed by default */}
          <button
            className="btn-outlined"
            style={{ marginBottom: templateOpen ? 'var(--space-sm)' : 0 }}
            onClick={() => setTemplateOpen((v) => !v)}
            aria-expanded={templateOpen}
          >
            {templateOpen ? 'Hide template' : 'Show template'}
          </button>

          {templateOpen && (
            <>
              {templateErr ? (
                <ErrorCard error={templateErr} />
              ) : template === null ? (
                <Skeleton />
              ) : (
                <>
                  <textarea
                    readOnly
                    value={template}
                    className="type-body"
                    style={{
                      width: '100%',
                      minHeight: '220px',
                      fontFamily: 'monospace',
                      fontSize: '0.875rem',
                      padding: 'var(--space-sm)',
                      background: 'var(--md-sys-color-surface)',
                      border: '1px solid var(--md-sys-color-outline)',
                      borderRadius: '4px',
                      resize: 'vertical',
                      boxSizing: 'border-box',
                      marginTop: 'var(--space-xs)',
                    }}
                  />
                  <button
                    className="btn-outlined"
                    style={{ marginTop: 'var(--space-sm)' }}
                    onClick={handleCopyTemplate}
                  >
                    Copy Template
                  </button>
                </>
              )}
            </>
          )}
        </section>

        <section>
          <label className="type-label" htmlFor="paste-area" style={{ display: 'block', marginBottom: 'var(--space-xs)' }}>
            Paste filled JSON here
          </label>
          <textarea
            id="paste-area"
            value={pastedJson}
            onChange={(e) => setPastedJson(e.target.value)}
            className="type-body"
            placeholder='{ "timestamp": "...", "meal_type": "lunch", ... }'
            style={{
              width: '100%',
              minHeight: '180px',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              padding: 'var(--space-sm)',
              background: 'var(--md-sys-color-surface)',
              border: '1px solid var(--md-sys-color-outline)',
              borderRadius: '4px',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />

          <button
            className="btn-filled"
            style={{ marginTop: 'var(--space-sm)' }}
            onClick={handleLogMeal}
            disabled={inFlight || pastedJson.trim() === ''}
          >
            {inFlight ? 'Validating…' : 'Log Meal'}
          </button>

          {formError && (
            <div style={{ marginTop: 'var(--space-sm)' }}>
              <ErrorCard error={formError} />
            </div>
          )}
        </section>
      </div>
    );
  }

  // ── Render: preview ──────────────────────────────────────────────────────────

  if (flow === 'preview' && preview !== null) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Preview — does this look right?</h1>
        </div>

        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'max-content 1fr',
            gap: 'var(--space-xs) var(--space-md)',
            marginBottom: 'var(--space-md)',
            background: 'var(--md-sys-color-surface)',
            padding: 'var(--space-md)',
            borderRadius: '4px',
            border: '1px solid var(--md-sys-color-outline)',
          }}
        >
          {PREVIEW_FIELDS.map(({ key, label }) => (
            <div key={key} style={{ display: 'contents' }}>
              <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
                {label}
              </dt>
              <dd className="type-body" style={{ margin: 0 }}>
                {preview[key] === null || preview[key] === undefined
                  ? <span style={{ opacity: 0.4 }}>—</span>
                  : String(preview[key])}
              </dd>
            </div>
          ))}
        </dl>

        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
          <button className="btn-outlined" onClick={handleBack} disabled={inFlight}>
            Back
          </button>
          <button className="btn-filled" onClick={handleAccept} disabled={inFlight}>
            {inFlight ? 'Saving…' : 'Accept'}
          </button>
        </div>

        {formError && (
          <div style={{ marginTop: 'var(--space-sm)' }}>
            <ErrorCard error={formError} />
          </div>
        )}
      </div>
    );
  }

  // ── Render: success ──────────────────────────────────────────────────────────

  if (flow === 'success' && success !== null) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Logged</h1>
        </div>

        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'max-content 1fr',
            gap: 'var(--space-xs) var(--space-md)',
            marginBottom: 'var(--space-md)',
            background: 'var(--md-sys-color-surface)',
            padding: 'var(--space-md)',
            borderRadius: '4px',
            border: '1px solid var(--md-sys-color-outline)',
          }}
        >
          <div style={{ display: 'contents' }}>
            <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Date / Time</dt>
            <dd className="type-body" style={{ margin: 0 }}>{success.logged_at}</dd>
          </div>
          <div style={{ display: 'contents' }}>
            <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Meal</dt>
            <dd className="type-body" style={{ margin: 0 }}>{success.meal_type}</dd>
          </div>
          <div style={{ display: 'contents' }}>
            <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Dish</dt>
            <dd className="type-body" style={{ margin: 0 }}>{success.dish_name}</dd>
          </div>
          <div style={{ display: 'contents' }}>
            <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>kcal</dt>
            <dd className="type-body" style={{ margin: 0 }}>{success.kcal}</dd>
          </div>
        </dl>

        <button className="btn-outlined" onClick={handleLogAnother}>
          Log Another
        </button>
      </div>
    );
  }

  // Fallback (should not be reached in normal flow)
  return null;
}

// ── Shell entry point ─────────────────────────────────────────────────────────

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/"            element={<FoodIntake />} />
      <Route path="/report"      element={<ReportPage />} />
      <Route path="/entries"     element={<EntriesPage />} />
      <Route path="/entries/:id" element={<EntryDetailPage />} />
      <Route path="/day"         element={<StandardsPage />} />
    </Routes>
  );
}
