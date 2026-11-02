/**
 * Kitchen recipe import (Sprint 1.1) + shared ingredient-line resolver.
 *
 * Flow: copy example / ingredient master -> paste recipe JSON -> server preview (validates, matches
 * article ids against StorageTracker) -> resolve open lines (assign existing article or explicitly
 * create one) -> save. Saving uses the normal POST /kitchen/recipes; nothing is booked on import.
 * Clipboard handling follows EssayCards' prompts.ts (write/read helpers + manual-paste fallback).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Article { id: number; name: string; unit: string | null; quantity?: number }

export type LineStatus = 'base' | 'matched' | 'unit_mismatch' | 'unknown_id' | 'unresolved' | 'unknown_base';

export interface Line {
  name: string; qty: number; unit: string; item_id: number | null; base_recipe_id: string | null;
  line_status?: LineStatus; item_name?: string | null; item_unit?: string | null;
  suggestions?: { id: number; name: string; unit: string | null }[];
}

interface PreviewRecipe {
  name: string; kind: 'base' | 'derived' | 'favorite'; servings: number; yield_unit: string;
  description: string | null; prep_minutes: number | null; cook_minutes: number | null;
  shelf_life_days: number | null; storage_location: string | null; steps: string; ingredients: Line[];
}

interface Preview {
  ok: boolean; errors: { path: string; message: string }[]; recipe: PreviewRecipe | null;
  unresolved: number; name_exists: boolean; status_if_saved: 'active' | 'draft' | null;
}

interface Dataset<T> { rows: T[] }

const CLIPBOARD_WRITE_DENIED = 'Clipboard not available — check the browser permission.';
const CLIPBOARD_READ_DENIED = 'Could not read the clipboard — check the permission or paste manually into the box below (Ctrl/Cmd+V).';

async function writeClipboard(text: string): Promise<string | null> {
  try { await navigator.clipboard.writeText(text); return null; } catch { return CLIPBOARD_WRITE_DENIED; }
}

async function readClipboard(): Promise<{ text: string } | { error: string }> {
  try { return { text: await navigator.clipboard.readText() }; } catch { return { error: CLIPBOARD_READ_DENIED }; }
}

function norm(s: string): string { return s.trim().toLowerCase().split(/\s+/).join(' '); }

/** Same rule as backend/ingredients.py: article without base unit accepts any recipe unit; never converted. */
export function lineStatusFor(line: Line, article: Article | undefined): LineStatus {
  if (line.base_recipe_id) return 'base';
  if (!line.item_id) return line.line_status === 'unknown_base' ? 'unknown_base' : 'unresolved';
  if (!article) return 'unknown_id';
  return article.unit === null || norm(article.unit) === norm(line.unit) ? 'matched' : 'unit_mismatch';
}

export function useMaster(): { master: Article[]; reload: () => void; add: (a: Article) => void; error: string | null } {
  const [master, setMaster] = useState<Article[]>([]);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    const res = await apiFetch<Dataset<Article>>('/kitchen/ingredients');
    if (isApiError(res)) setError(res.error.message); else { setMaster(res.rows); setError(null); }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return { master, reload, add: (a) => setMaster((m) => [...m, a]), error };
}

// ── Resolver: assign existing article or explicitly create one ────────────────

function ArticleResolver({ line, master, onAssign, onCreated }: {
  line: Line; master: Article[]; onAssign: (a: Article) => void; onCreated: (a: Article) => void;
}) {
  const [mode, setMode] = useState<'assign' | 'create' | null>(null);
  const [query, setQuery] = useState(line.name);
  const [name, setName] = useState(line.name);
  const [unit, setUnit] = useState(line.unit);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const q = norm(query);
  const hits = master.filter((a) => !q || norm(a.name).includes(q)).slice(0, 8);

  const create = async () => {
    setBusy(true); setError(null);
    const res = await apiFetch<Dataset<Article>>('/kitchen/ingredients', {
      method: 'POST', body: JSON.stringify({ name, unit }),
    });
    setBusy(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    onCreated(res.rows[0]); onAssign(res.rows[0]);
  };

  return (
    <div className="kitchen-col">
      <div className="kitchen-row">
        <button className="kitchen-btn" onClick={() => setMode(mode === 'assign' ? null : 'assign')}>Assign article</button>
        <button className="kitchen-btn" onClick={() => setMode(mode === 'create' ? null : 'create')}>Create new</button>
      </div>
      {mode === 'assign' && (
        <div className="kitchen-col">
          <input className="kitchen-input" placeholder="Search articles…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {hits.length === 0 && <span className="kitchen-muted">No article found.</span>}
          {hits.map((a) => (
            <button key={a.id} className="kitchen-btn kitchen-left" onClick={() => onAssign(a)}>
              #{a.id} {a.name} <span className="kitchen-muted">· {a.unit ?? 'no unit'}</span>
            </button>
          ))}
        </div>
      )}
      {mode === 'create' && (
        <div className="kitchen-col">
          <input className="kitchen-input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Article name" />
          <div className="kitchen-row">
            <input className="kitchen-input num" value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="Basiseinheit" />
            <span className="kitchen-muted">Base unit · stock 0</span>
          </div>
          <button className="kitchen-btn primary" disabled={busy || !name.trim() || !unit.trim()} onClick={create}>
            Create &amp; assign
          </button>
          {error && <div className="kitchen-warn">{error}</div>}
        </div>
      )}
    </div>
  );
}

// ── One ingredient line (import preview and recipe form) ──────────────────────

const STATUS_TEXT: Record<LineStatus, string> = {
  base: 'Cooked base', matched: '', unit_mismatch: 'Unit mismatch', unknown_id: 'Unknown article number',
  unresolved: 'Not assigned', unknown_base: 'Unknown base recipe',
};

export function IngredientLine({ line, master, onChange, onCreated, onRemove }: {
  line: Line; master: Article[]; onChange: (patch: Partial<Line>) => void;
  onCreated: (a: Article) => void; onRemove?: () => void;
}) {
  const article = line.item_id ? master.find((a) => a.id === line.item_id) : undefined;
  const status = lineStatusFor(line, article);
  const assign = (a: Article) => onChange({ item_id: a.id, item_name: a.name, item_unit: a.unit, line_status: undefined });
  const ok = status === 'matched' || status === 'base';

  return (
    <div className={`kitchen-card kitchen-line${ok ? '' : ' open'}`}>
      <div className="kitchen-row spread">
        <strong>{ok && article ? `✓ #${article.id} ${article.name}` : line.name || '—'}</strong>
        <span className="kitchen-row">
          {!ok && <span className="kitchen-chip warn">{STATUS_TEXT[status]}</span>}
          {onRemove && <button className="kitchen-btn" onClick={onRemove} aria-label="Remove ingredient">×</button>}
        </span>
      </div>
      <div className="kitchen-row">
        <input className="kitchen-input num" type="number" min="0" step="any" value={line.qty}
               onChange={(e) => onChange({ qty: Number(e.target.value) })} aria-label="Quantity" />
        {line.base_recipe_id ? <span>{line.unit}</span> :
          <input className="kitchen-input num" value={line.unit} onChange={(e) => onChange({ unit: e.target.value })} aria-label="Unit" />}
        {status === 'unit_mismatch' && article && (
          <span className="kitchen-muted">Article "{article.name}" uses {article.unit} — adjust quantity/unit, nothing is converted.</span>
        )}
      </div>
      {article && !line.base_recipe_id && (
        <button className="kitchen-btn kitchen-left" onClick={() => onChange({ item_id: null, item_name: null, item_unit: null })}>
          Change assignment
        </button>
      )}
      {(status === 'unresolved' || status === 'unknown_id' || status === 'unknown_base') && !line.base_recipe_id && (
        <ArticleResolver line={line} master={master} onAssign={assign} onCreated={onCreated} />
      )}
    </div>
  );
}

// ── Import view ───────────────────────────────────────────────────────────────

export function ImportView({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { master, add } = useMaster();
  const [text, setText] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [rec, setRec] = useState<PreviewRecipe | null>(null);
  const [busy, setBusy] = useState(false);

  const copyExample = async () => {
    const res = await apiFetch<Dataset<{ example: unknown }>>('/kitchen/recipes/import-example');
    if (isApiError(res)) { setMsg(res.error.message); return; }
    setMsg((await writeClipboard(JSON.stringify(res.rows[0].example, null, 2))) ?? 'Example JSON copied.');
  };

  const copyMaster = async () => {
    const res = await apiFetch<Dataset<Article>>('/kitchen/ingredients');
    if (isApiError(res)) { setMsg(res.error.message); return; }
    const payload = {
      format: 'atlas.kitchen.ingredient_master', version: 1,
      items: res.rows.map((a) => ({ item_id: a.id, name: a.name, unit: a.unit })),
    };
    setMsg((await writeClipboard(JSON.stringify(payload, null, 2))) ?? `Ingredient master copied (${res.rows.length} articles).`);
  };

  const check = async (raw: string) => {
    setBusy(true); setError(null); setPreview(null); setRec(null);
    const res = await apiFetch<Dataset<Preview>>('/kitchen/recipes/import/preview', {
      method: 'POST', body: JSON.stringify({ text: raw }),
    });
    setBusy(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    setPreview(res.rows[0]); setRec(res.rows[0].recipe);
  };

  const paste = async () => {
    const res = await readClipboard();
    if ('error' in res) { setMsg(res.error); return; }
    setMsg(null); setText(res.text); check(res.text);
  };

  const setLine = (i: number, patch: Partial<Line>) =>
    setRec((r) => r && ({ ...r, ingredients: r.ingredients.map((l, j) => (j === i ? { ...l, ...patch } : l)) }));

  const statuses = rec ? rec.ingredients.map((l) => lineStatusFor(l, l.item_id ? master.find((a) => a.id === l.item_id) : undefined)) : [];
  const open = statuses.filter((s) => s !== 'matched' && s !== 'base').length;

  const save = async () => {
    if (!rec) return;
    setBusy(true); setError(null);
    const body = {
      name: rec.name, kind: rec.kind, servings: rec.servings, description: rec.description,
      prep_minutes: rec.prep_minutes, cook_minutes: rec.cook_minutes, shelf_life_days: rec.shelf_life_days,
      storage_location: rec.storage_location, steps: rec.steps,
      ingredients: rec.ingredients.map((l) => ({
        name: l.name || l.item_name || '', qty: l.qty, unit: l.unit, item_id: l.item_id, base_recipe_id: l.base_recipe_id,
      })),
    };
    const res = await apiFetch<Dataset<{ status: string }>>('/kitchen/recipes', { method: 'POST', body: JSON.stringify(body) });
    setBusy(false);
    if (isApiError(res)) { setError(res.error.message); return; }
    onSaved();
  };

  return (
    <div className="kitchen-page">
      <div className="kitchen-row spread">
        <h1 className="type-headline">Import recipe</h1>
        <button className="kitchen-btn" onClick={onClose}>Close</button>
      </div>
      <div className="kitchen-row">
        <button className="kitchen-btn" onClick={copyExample}>Copy example JSON</button>
        <button className="kitchen-btn" onClick={copyMaster}>Copy ingredient master</button>
        <button className="kitchen-btn primary" disabled={busy} onClick={paste}>Import from clipboard</button>
      </div>
      {msg && <div className="kitchen-muted">{msg}</div>}
      <textarea className="kitchen-input kitchen-textarea kitchen-mono" value={text} rows={6}
                placeholder="Or paste recipe JSON here…" onChange={(e) => setText(e.target.value)} />
      <button className="kitchen-btn" disabled={busy || !text.trim()} onClick={() => check(text)}>Check</button>
      {error && <div className="kitchen-warn">{error}</div>}

      {preview && !preview.ok && (
        <div className="kitchen-warn">
          <strong>Import not possible:</strong>
          {preview.errors.map((e, i) => <div key={i}><code>{e.path}</code>: {e.message}</div>)}
        </div>
      )}

      {rec && preview?.ok && (
        <>
          <div className="kitchen-card">
            <input className="kitchen-input" value={rec.name} onChange={(e) => setRec({ ...rec, name: e.target.value })} aria-label="Recipe name" />
            <span className="kitchen-muted">
              {rec.kind === 'base' ? 'Cooked base' : rec.kind === 'derived' ? 'Derived dish' : 'Favorite'} · {rec.servings} {rec.yield_unit}
              {rec.prep_minutes !== null ? ` · Prep ${rec.prep_minutes} min` : ''}
              {rec.cook_minutes !== null ? ` · Cook ${rec.cook_minutes} min` : ''}
            </span>
            {rec.description && <span>{rec.description}</span>}
            {preview.name_exists && (
              <div className="kitchen-warn">A recipe with this name already exists — it will not be overwritten. Change the name to save it as a new recipe.</div>
            )}
          </div>
          <div className="kitchen-day">Ingredients ({rec.ingredients.length - open} assigned, {open} open)</div>
          {rec.ingredients.map((l, i) => (
            <IngredientLine key={i} line={l} master={master} onChange={(p) => setLine(i, p)} onCreated={add} />
          ))}
          {rec.steps && (<><div className="kitchen-day">Steps</div><pre className="kitchen-steps">{rec.steps}</pre></>)}
          <button className="kitchen-btn primary" disabled={busy || !rec.name.trim()} onClick={save}>
            {open === 0 ? 'Save (active)' : `Save as draft (${open} open)`}
          </button>
          {open > 0 && <span className="kitchen-muted">Drafts are not used for planning, shopping or stock bookings.</span>}
        </>
      )}
    </div>
  );
}
