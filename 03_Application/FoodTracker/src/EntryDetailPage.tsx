/**
 * EntryDetailPage — Sprint 03
 *
 * Entry detail and edit screen for /food/entries/:id.
 * Loads one existing meal entry by id. Renders an editable form.
 * Save issues PUT /api/food/entries/{id} with EntryEditRequest body.
 *
 * EntryEditRequest contract (architecture.json contracts.named_contracts.EntryEditRequest):
 * {logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fat_g,
 *  fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes?}
 *
 * No items field. No timestamp field. dish_name is user-editable.
 * Edit and intake are separate flows (Option A, 2026-03-21).
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

/**
 * EntryDetail — conforms to architecture.json contracts.named_contracts.EntryDetail.
 * Returned by GET /api/food/entries/{id} and POST /api/food/entries/{id}/copy.
 */
interface EntryDetail {
  id:         string;
  logged_at:  string;
  meal_type:  string;
  dish_name:  string;
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
  created_at: string;
  updated_at: string;
}

/**
 * EntryFormState — local editing state for all user-editable fields
 * per the EntryEditRequest contract. dish_name is user-editable in this flow.
 */
interface EntryFormState {
  logged_at:  string;
  meal_type:  string;
  dish_name:  string;
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
  notes:      string;
}

// ── Private helpers ────────────────────────────────────────────────────────────

const ALLOWED_MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack', 'other'] as const;

function entryToFormState(entry: EntryDetail): EntryFormState {
  return {
    logged_at:  entry.logged_at,
    meal_type:  entry.meal_type,
    dish_name:  entry.dish_name,
    kcal:       entry.kcal,
    protein_g:  entry.protein_g,
    carbs_g:    entry.carbs_g,
    fat_g:      entry.fat_g,
    fiber_g:    entry.fiber_g,
    good_fat_g: entry.good_fat_g,
    meat_g:     entry.meat_g,
    red_meat_g: entry.red_meat_g,
    sodium_mg:  entry.sodium_mg,
    alcohol_g:  entry.alcohol_g ?? 0,
    confidence: entry.confidence,
    notes:      entry.notes ?? '',
  };
}

/**
 * _buildPutBody — constructs the EntryEditRequest JSON body string from form state.
 *
 * Conforms to architecture.json contracts.named_contracts.EntryEditRequest:
 * {logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fat_g,
 *  fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes?}
 *
 * No items field. No timestamp field. dish_name taken directly from formState
 * and is user-editable (Option A).
 */
function _buildPutBody(formState: EntryFormState): string {
  const body: Record<string, unknown> = {
    logged_at:  formState.logged_at,
    meal_type:  formState.meal_type,
    dish_name:  formState.dish_name,
    kcal:       Math.round(formState.kcal),
    protein_g:  formState.protein_g,
    carbs_g:    formState.carbs_g,
    fat_g:      formState.fat_g,
    fiber_g:    formState.fiber_g,
    good_fat_g: formState.good_fat_g,
    meat_g:     formState.meat_g,
    red_meat_g: formState.red_meat_g,
    sodium_mg:  formState.sodium_mg,
    alcohol_g:  formState.alcohol_g,
    confidence: formState.confidence,
  };
  if (formState.notes.trim() !== '') {
    body['notes'] = formState.notes;
  }
  return JSON.stringify(body);
}

// ── Field helpers ─────────────────────────────────────────────────────────────

interface FieldRowProps {
  label: string;
  children: React.ReactNode;
}

function FieldRow({ label, children }: FieldRowProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '140px 1fr',
        gap: 'var(--space-xs)',
        alignItems: 'center',
        marginBottom: 'var(--space-xs)',
      }}
    >
      <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '140px 1fr',
        gap: 'var(--space-xs)',
        alignItems: 'center',
        marginBottom: 'var(--space-xs)',
        opacity: 0.6,
      }}
    >
      <span className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
        {label}
      </span>
      <span className="type-body">{value}</span>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '6px 10px',
  border: '1px solid var(--md-sys-color-outline)',
  borderRadius: '4px',
  background: 'var(--md-sys-color-surface)',
  color: 'var(--md-sys-color-on-surface)',
  fontSize: '0.9rem',
  width: '100%',
  boxSizing: 'border-box',
};

// ── EntryDetailPage ───────────────────────────────────────────────────────────

export default function EntryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [entry,       setEntry]       = useState<EntryDetail | null>(null);
  const [formState,   setFormState]   = useState<EntryFormState | null>(null);
  const [isLoading,   setIsLoading]   = useState(true);
  const [isSaving,    setIsSaving]    = useState(false);
  const [loadError,   setLoadError]   = useState<ApiError | null>(null);
  const [saveError,   setSaveError]   = useState<ApiError | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!id) return;
    apiFetch<EntryDetail>(`/food/entries/${id}`).then((res) => {
      setIsLoading(false);
      if (isApiError(res)) {
        setLoadError(res);
      } else {
        const detail = res as EntryDetail;
        setEntry(detail);
        setFormState(entryToFormState(detail));
      }
    });
  }, [id]);

  // ── Field change handler ───────────────────────────────────────────────────

  function handleChange(field: keyof EntryFormState, value: string | number) {
    setSaveError(null);
    setSaveSuccess(false);
    setFormState((prev) => prev ? { ...prev, [field]: value } : prev);
  }

  // ── Save handler ───────────────────────────────────────────────────────────

  async function handleSave() {
    if (!id || !formState) return;
    setSaveError(null);
    setSaveSuccess(false);
    setIsSaving(true);
    try {
      const body = _buildPutBody(formState);
      const res = await apiFetch<{ meta: object; schema: object[]; rows: Record<string, unknown>[] }>(
        `/food/entries/${id}`,
        { method: 'PUT', body },
      );
      if (isApiError(res)) {
        setSaveError(res);
      } else {
        // Refresh displayed values from the returned Dataset row
        const dataset = res as { meta: object; schema: object[]; rows: Record<string, unknown>[] };
        const row = dataset.rows[0];
        // Update form state from returned row (the authoritative values after save)
        setFormState((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            logged_at:  String(row['logged_at'] ?? prev.logged_at),
            meal_type:  String(row['meal_type'] ?? prev.meal_type),
            dish_name:  String(row['dish_name'] ?? prev.dish_name),
            kcal:       Number(row['kcal'] ?? prev.kcal),
            protein_g:  Number(row['protein_g'] ?? prev.protein_g),
            fat_g:      Number(row['fat_g'] ?? prev.fat_g),
          };
        });
        setSaveSuccess(true);
      }
    } finally {
      setIsSaving(false);
    }
  }

  // ── Render: loading ────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <button className="btn-outlined" style={{ marginBottom: 'var(--space-sm)' }} onClick={() => navigate('/food/entries')}>
            Back
          </button>
          <h1 className="type-display">Entry Detail</h1>
        </div>
        <Skeleton />
      </div>
    );
  }

  // ── Render: load error ─────────────────────────────────────────────────────

  if (loadError) {
    return (
      <div className="page">
        <div className="page-header">
          <button className="btn-outlined" style={{ marginBottom: 'var(--space-sm)' }} onClick={() => navigate('/food/entries')}>
            Back
          </button>
          <h1 className="type-display">Entry Detail</h1>
        </div>
        <ErrorCard error={loadError} />
      </div>
    );
  }

  if (!entry || !formState) return null;

  // ── Render: edit form ──────────────────────────────────────────────────────

  return (
    <div className="page">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <button className="btn-outlined" onClick={() => navigate('/food/entries')}>
          Back
        </button>
        <h1 className="type-display" style={{ margin: 0 }}>Entry Detail</h1>
      </div>

      {/* Read-only context — system-managed fields */}
      <section
        style={{
          background: 'var(--md-sys-color-surface-variant)',
          borderRadius: '8px',
          padding: 'var(--space-sm) var(--space-md)',
          marginBottom: 'var(--space-md)',
        }}
      >
        <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 'var(--space-xs)' }}>
          System fields (read-only)
        </p>
        <ReadOnlyField label="ID"         value={entry.id} />
        <ReadOnlyField label="Created at" value={entry.created_at} />
        <ReadOnlyField label="Updated at" value={entry.updated_at} />
      </section>

      {/* Editable fields */}
      <section
        style={{
          background: 'var(--md-sys-color-surface)',
          border: '1px solid var(--md-sys-color-outline)',
          borderRadius: '8px',
          padding: 'var(--space-md)',
          marginBottom: 'var(--space-md)',
        }}
      >
        <FieldRow label="Date / Time">
          <input
            type="text"
            value={formState.logged_at}
            onChange={(e) => handleChange('logged_at', e.target.value)}
            style={inputStyle}
            placeholder="YYYY-MM-DDTHH:MM:SS"
          />
        </FieldRow>

        <FieldRow label="Meal type">
          <select
            value={formState.meal_type}
            onChange={(e) => handleChange('meal_type', e.target.value)}
            style={inputStyle}
          >
            {ALLOWED_MEAL_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label="Dish name">
          <input
            type="text"
            value={formState.dish_name}
            onChange={(e) => handleChange('dish_name', e.target.value)}
            style={inputStyle}
            placeholder="e.g. chicken breast, rice"
          />
        </FieldRow>

        <FieldRow label="kcal">
          <input
            type="number"
            value={formState.kcal}
            min={0}
            onChange={(e) => handleChange('kcal', Number(e.target.value))}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Protein (g)">
          <input
            type="number"
            value={formState.protein_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('protein_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Carbs (g)">
          <input
            type="number"
            value={formState.carbs_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('carbs_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Fat (g)">
          <input
            type="number"
            value={formState.fat_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('fat_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Fiber (g)">
          <input
            type="number"
            value={formState.fiber_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('fiber_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Good fat (g)">
          <input
            type="number"
            value={formState.good_fat_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('good_fat_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Meat (g)">
          <input
            type="number"
            value={formState.meat_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('meat_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Red meat (g)">
          <input
            type="number"
            value={formState.red_meat_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('red_meat_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Sodium (mg)">
          <input
            type="number"
            value={formState.sodium_mg}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('sodium_mg', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Alcohol (g)">
          <input
            type="number"
            value={formState.alcohol_g}
            min={0}
            step="0.1"
            onChange={(e) => handleChange('alcohol_g', parseFloat(e.target.value) || 0)}
            style={inputStyle}
          />
        </FieldRow>

        <FieldRow label="Confidence">
          <select
            value={formState.confidence}
            onChange={(e) => handleChange('confidence', parseInt(e.target.value, 10))}
            style={inputStyle}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label="Notes">
          <textarea
            value={formState.notes}
            onChange={(e) => handleChange('notes', e.target.value)}
            style={{ ...inputStyle, minHeight: '72px', resize: 'vertical' }}
            placeholder="Optional notes"
          />
        </FieldRow>
      </section>

      {/* Save controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <button
          className="btn-filled"
          onClick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        {saveSuccess && (
          <span className="type-label" style={{ color: 'var(--md-sys-color-primary)' }}>
            Saved.
          </span>
        )}
      </div>

      {saveError && (
        <div style={{ marginTop: 'var(--space-sm)' }}>
          <ErrorCard error={saveError} />
        </div>
      )}
    </div>
  );
}
