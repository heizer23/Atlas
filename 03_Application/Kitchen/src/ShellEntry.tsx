/**
 * Kitchen ShellEntry — Sprint 01
 *
 * Views:
 *   /kitchen            -> PlanView      (week plan, cook / eat / move / undo, batches)
 *   /kitchen/shopping   -> ShoppingView  (buy list + "probably have" check)
 *   /kitchen/recipes    -> RecipesView   (list, create, edit)
 *
 * All stock changes happen server-side (StorageTracker ledger); this UI only triggers
 * business events (cooked / eaten / undo / purchase / stocktake).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import Skeleton from '@platform-ui/components/Skeleton';
import './kitchen.css';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Dataset<T> { meta: { object_type: string; total: number }; rows: T[] }

type RecipeKind = 'base' | 'derived' | 'favorite';
type MealStatus = 'planned' | 'cooked' | 'eaten' | 'skipped';

interface RecipeSummary { id: string; name: string; kind: RecipeKind; servings: number; yield_unit: string }
interface Ingredient { name: string; qty: number; unit: string; base_recipe_id: string | null }
interface Recipe extends RecipeSummary {
  steps: string; shelf_life_days: number | null; storage_location: string | null; ingredients: Ingredient[];
}
interface Meal {
  id: string; recipe_id: string | null; recipe_name: string | null; recipe_kind: RecipeKind | null;
  kind: 'cook' | 'meal'; day: string; portions: number; status: MealStatus;
}
interface Plan { id: string; week_start: string; meals: Meal[] }
interface Batch { id: string; name: string; quantity: number; unit: string; location: string | null; expires_at: string | null }
interface ShopLine { name: string; unit: string; needed: number; stock: number; to_buy?: number; covered?: number }
interface Shopping {
  buy: ShopLine[]; probably_have: ShopLine[]; missing_bases: { name: string; needed: number; available: number }[];
}

type Post = <T>(path: string, body?: unknown, method?: string) => Promise<T | null>;

// ── Helpers ───────────────────────────────────────────────────────────────────

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
}

function num(v: number): string { return String(Math.round(v * 100) / 100); }

function useAction(): { post: Post; error: string | null; busy: boolean } {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const post: Post = useCallback(async (path, body, method = 'POST') => {
    setBusy(true); setError(null);
    const res = await apiFetch<any>(`/kitchen${path}`, { method, body: body === undefined ? undefined : JSON.stringify(body) });
    setBusy(false);
    if (isApiError(res)) { setError(res.error.message); return null; }
    return res;
  }, []);
  return { post, error, busy };
}

function Loading({ error }: { error: string | null }) {
  return error ? <div className="kitchen-warn">{error}</div> : <Skeleton />;
}

// ── Plan view ─────────────────────────────────────────────────────────────────

function MealCard({ meal, recipes, onChanged }: { meal: Meal; recipes: RecipeSummary[]; onChanged: () => void }) {
  const { post, error, busy } = useAction();
  const [qty, setQty] = useState<string>(String(meal.portions));
  const [moving, setMoving] = useState(false);
  const [newDay, setNewDay] = useState(meal.day);
  const [swap, setSwap] = useState(meal.recipe_id ?? '');
  const planned = meal.status === 'planned';
  const isCook = meal.kind === 'cook';

  const run = async (path: string, body?: unknown, method?: string) => {
    if (await post(path, body, method)) { setMoving(false); onChanged(); }
  };

  return (
    <div className={`kitchen-card${planned ? '' : ' done'}`}>
      <div className="kitchen-row spread">
        <strong>{meal.recipe_name ?? 'Flexibler Tag'}</strong>
        <span className="kitchen-chip">{isCook ? 'Kochen' : 'Essen'} · {meal.status}</span>
      </div>
      {meal.recipe_id && <span className="kitchen-muted">{num(meal.portions)} Portionen</span>}
      {error && <div className="kitchen-warn">{error}</div>}

      {planned && meal.recipe_id && (
        <div className="kitchen-row">
          <input className="kitchen-input num" type="number" min="0.5" step="0.5" value={qty}
                 onChange={(e) => setQty(e.target.value)} aria-label="Portionen" />
          <button className="kitchen-btn primary" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}/${isCook ? 'cooked' : 'eaten'}`,
                                     isCook ? { produced_qty: Number(qty) } : { portions: Number(qty) })}>
            {isCook ? 'Gekocht' : 'Gegessen'}
          </button>
        </div>
      )}
      {planned && !meal.recipe_id && (
        <button className="kitchen-btn" disabled={busy}
                onClick={() => run(`/meals/${meal.id}/eaten`)}>Gegessen (ohne Buchung)</button>
      )}
      {planned && (
        <div className="kitchen-row">
          <button className="kitchen-btn" onClick={() => setMoving(!moving)}>Verschieben / Tauschen</button>
          <button className="kitchen-btn" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}`, { status: 'skipped' }, 'PATCH')}>Überspringen</button>
        </div>
      )}
      {planned && moving && (
        <div className="kitchen-row">
          <input className="kitchen-input" type="date" value={newDay} onChange={(e) => setNewDay(e.target.value)} />
          <select className="kitchen-input" value={swap} onChange={(e) => setSwap(e.target.value)}>
            <option value="">Flexibler Tag</option>
            {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <button className="kitchen-btn primary" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}`, { day: newDay, recipe_id: swap || null }, 'PATCH')}>Speichern</button>
        </div>
      )}
      {(meal.status === 'cooked' || meal.status === 'eaten') && (
        <button className="kitchen-btn" disabled={busy}
                onClick={() => run(`/meals/${meal.id}/undo`)}>Rückgängig</button>
      )}
    </div>
  );
}

function PlanView() {
  const [plan, setPlan] = useState<Plan | null | undefined>(undefined);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { post, error: actionError, busy } = useAction();

  const load = useCallback(async () => {
    const list = await apiFetch<Dataset<{ id: string }>>('/kitchen/plans');
    if (isApiError(list)) { setError(list.error.message); return; }
    if (list.rows.length) {
      const p = await apiFetch<Dataset<Plan>>(`/kitchen/plans/${list.rows[0].id}`);
      if (isApiError(p)) { setError(p.error.message); return; }
      setPlan(p.rows[0]);
    } else setPlan(null);
    const r = await apiFetch<Dataset<RecipeSummary>>('/kitchen/recipes');
    if (!isApiError(r)) setRecipes(r.rows);
    const b = await apiFetch<Dataset<Batch>>('/kitchen/batches');
    if (!isApiError(b)) setBatches(b.rows);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (plan === undefined) return <div className="kitchen-page"><Loading error={error} /></div>;

  const days = plan ? Array.from(new Set(plan.meals.map((m) => m.day))) : [];
  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Wochenplan</h1>
      {batches.length > 0 && (
        <div className="kitchen-card">
          <strong>Vorrat Kochbasen</strong>
          {batches.map((b) => (
            <div key={b.id} className="kitchen-row spread">
              <span>{b.name}</span>
              <span className="kitchen-muted">{num(b.quantity)} {b.unit}{b.expires_at ? ` · bis ${dayLabel(b.expires_at)}` : ''}</span>
            </div>
          ))}
        </div>
      )}
      <button className="kitchen-btn primary" disabled={busy}
              onClick={async () => { if (await post('/plans/suggest', {})) load(); }}>
        {plan ? 'Neuen Wochenplan vorschlagen' : 'Wochenplan vorschlagen'}
      </button>
      {(actionError || error) && <div className="kitchen-warn">{actionError ?? error}</div>}
      {days.map((d) => (
        <React.Fragment key={d}>
          <div className="kitchen-day">{dayLabel(d)}</div>
          {plan!.meals.filter((m) => m.day === d).map((m) => (
            <MealCard key={`${m.id}-${m.status}-${m.day}`} meal={m} recipes={recipes} onChanged={load} />
          ))}
        </React.Fragment>
      ))}
      {plan && <AddMeal planId={plan.id} recipes={recipes} weekStart={plan.week_start} onAdded={load} />}
    </div>
  );
}

function AddMeal({ planId, recipes, weekStart, onAdded }: { planId: string; recipes: RecipeSummary[]; weekStart: string; onAdded: () => void }) {
  const { post, error, busy } = useAction();
  const [recipeId, setRecipeId] = useState('');
  const [day, setDay] = useState(weekStart);
  const recipe = recipes.find((r) => r.id === recipeId);
  return (
    <div className="kitchen-card">
      <strong>Gericht hinzufügen</strong>
      <div className="kitchen-row">
        <select className="kitchen-input" value={recipeId} onChange={(e) => setRecipeId(e.target.value)}>
          <option value="">Rezept wählen…</option>
          {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <input className="kitchen-input" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        <button className="kitchen-btn primary" disabled={busy || !recipe}
                onClick={async () => {
                  if (await post(`/plans/${planId}/meals`, { recipe_id: recipeId, day, kind: recipe!.kind === 'base' ? 'cook' : 'meal' })) {
                    setRecipeId(''); onAdded();
                  }
                }}>Hinzufügen</button>
      </div>
      {error && <div className="kitchen-warn">{error}</div>}
    </div>
  );
}

// ── Shopping view ─────────────────────────────────────────────────────────────

function BuyRow({ line, onDone }: { line: ShopLine; onDone: () => void }) {
  const { post, error, busy } = useAction();
  const [qty, setQty] = useState(String(line.to_buy ?? 0));
  return (
    <div className="kitchen-card">
      <div className="kitchen-row spread">
        <strong>{line.name}</strong>
        <span className="kitchen-muted">brauche {num(line.needed)} {line.unit}, da {num(line.stock)}</span>
      </div>
      <div className="kitchen-row">
        <input className="kitchen-input num" type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />
        <span>{line.unit}</span>
        <button className="kitchen-btn primary" disabled={busy || !(Number(qty) > 0)}
                onClick={async () => {
                  if (await post('/shopping/purchase', { name: line.name, unit: line.unit, qty: Number(qty), idempotency_key: crypto.randomUUID?.() })) onDone();
                }}>Gekauft</button>
      </div>
      {error && <div className="kitchen-warn">{error}</div>}
    </div>
  );
}

function HaveRow({ line, onDone }: { line: ShopLine; onDone: () => void }) {
  const { post, error, busy } = useAction();
  const [qty, setQty] = useState(String(line.stock));
  return (
    <div className="kitchen-card">
      <div className="kitchen-row spread">
        <strong>{line.name}</strong>
        <span className="kitchen-muted">brauche {num(line.needed)} {line.unit} · Bestand {num(line.stock)}</span>
      </div>
      <div className="kitchen-row">
        <input className="kitchen-input num" type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />
        <span>{line.unit} tatsächlich da</span>
        <button className="kitchen-btn" disabled={busy}
                onClick={async () => { if (await post('/shopping/stocktake', { name: line.name, unit: line.unit, qty: Number(qty) })) onDone(); }}>
          Bestätigen
        </button>
      </div>
      {error && <div className="kitchen-warn">{error}</div>}
    </div>
  );
}

function ShoppingView() {
  const [data, setData] = useState<Shopping | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const list = await apiFetch<Dataset<{ id: string }>>('/kitchen/plans');
    if (isApiError(list)) { setError(list.error.message); return; }
    if (!list.rows.length) { setData(null); return; }
    const res = await apiFetch<Dataset<Shopping>>(`/kitchen/plans/${list.rows[0].id}/shopping`);
    if (isApiError(res)) { setError(res.error.message); return; }
    setData(res.rows[0]);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (data === undefined) return <div className="kitchen-page"><Loading error={error} /></div>;
  if (data === null) return <div className="kitchen-page"><p className="kitchen-muted">Noch kein Wochenplan.</p></div>;

  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Einkauf</h1>
      {data.missing_bases.map((b) => (
        <div key={b.name} className="kitchen-warn">
          Kochbasis „{b.name}" fehlt: benötigt {num(b.needed)}, verfügbar {num(b.available)} — im Plan eine Kochsession ergänzen.
        </div>
      ))}
      <div className="kitchen-day">Einkaufen ({data.buy.length})</div>
      {data.buy.length === 0 && <p className="kitchen-muted">Nichts zu kaufen.</p>}
      {data.buy.map((l) => <BuyRow key={`${l.name}-${l.unit}-${l.stock}`} line={l} onDone={load} />)}
      <div className="kitchen-day">Vermutlich vorhanden ({data.probably_have.length})</div>
      {data.probably_have.map((l) => <HaveRow key={`${l.name}-${l.unit}-${l.stock}`} line={l} onDone={load} />)}
    </div>
  );
}

// ── Recipes view ──────────────────────────────────────────────────────────────

const EMPTY: Recipe = { id: '', name: '', kind: 'favorite', servings: 2, yield_unit: 'Portionen', steps: '',
                        shelf_life_days: null, storage_location: null, ingredients: [] };

function RecipeForm({ initial, bases, onSaved, onCancel }: { initial: Recipe; bases: RecipeSummary[]; onSaved: () => void; onCancel: () => void }) {
  const { post, error, busy } = useAction();
  const [r, setR] = useState<Recipe>(initial);
  const set = (patch: Partial<Recipe>) => setR({ ...r, ...patch });
  const setIng = (i: number, patch: Partial<Ingredient>) =>
    set({ ingredients: r.ingredients.map((x, j) => (j === i ? { ...x, ...patch } : x)) });

  const save = async () => {
    const body = {
      name: r.name, kind: r.kind, servings: r.servings, steps: r.steps,
      shelf_life_days: r.shelf_life_days, storage_location: r.storage_location,
      ingredients: r.ingredients.filter((i) => i.name.trim()).map((i) => ({
        name: i.name, qty: Number(i.qty), unit: i.base_recipe_id ? 'Portionen' : i.unit, base_recipe_id: i.base_recipe_id,
      })),
    };
    const res = r.id ? await post(`/recipes/${r.id}`, body, 'PATCH') : await post('/recipes', body);
    if (res) onSaved();
  };

  return (
    <div className="kitchen-card">
      <input className="kitchen-input" placeholder="Name" value={r.name} onChange={(e) => set({ name: e.target.value })} />
      <div className="kitchen-row">
        <select className="kitchen-input" value={r.kind} onChange={(e) => set({ kind: e.target.value as RecipeKind })}>
          <option value="base">Kochbasis</option>
          <option value="derived">Abgeleitetes Gericht</option>
          <option value="favorite">Favorit</option>
        </select>
        <label className="kitchen-row">Portionen
          <input className="kitchen-input num" type="number" min="0.5" step="0.5" value={r.servings}
                 onChange={(e) => set({ servings: Number(e.target.value) })} /></label>
        {r.kind === 'base' && (
          <label className="kitchen-row">Haltbar (Tage)
            <input className="kitchen-input num" type="number" min="0" value={r.shelf_life_days ?? ''}
                   onChange={(e) => set({ shelf_life_days: e.target.value === '' ? null : Number(e.target.value) })} /></label>
        )}
      </div>
      <strong>Zutaten</strong>
      {r.ingredients.map((ing, i) => (
        <div key={i} className="kitchen-row">
          {ing.base_recipe_id ? (
            <select className="kitchen-input" value={ing.base_recipe_id}
                    onChange={(e) => setIng(i, { base_recipe_id: e.target.value, name: bases.find((b) => b.id === e.target.value)?.name ?? '' })}>
              {bases.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          ) : (
            <input className="kitchen-input" placeholder="Zutat" value={ing.name} onChange={(e) => setIng(i, { name: e.target.value })} />
          )}
          <input className="kitchen-input num" type="number" min="0" step="any" value={ing.qty} onChange={(e) => setIng(i, { qty: Number(e.target.value) })} />
          {ing.base_recipe_id ? <span>Portionen</span> :
            <input className="kitchen-input num" placeholder="Einheit" value={ing.unit} onChange={(e) => setIng(i, { unit: e.target.value })} />}
          <button className="kitchen-btn" onClick={() => set({ ingredients: r.ingredients.filter((_, j) => j !== i) })}>×</button>
        </div>
      ))}
      <div className="kitchen-row">
        <button className="kitchen-btn" onClick={() => set({ ingredients: [...r.ingredients, { name: '', qty: 1, unit: 'g', base_recipe_id: null }] })}>+ Zutat</button>
        {bases.length > 0 && r.kind !== 'base' && (
          <button className="kitchen-btn" onClick={() => set({ ingredients: [...r.ingredients, { name: bases[0].name, qty: 2, unit: 'Portionen', base_recipe_id: bases[0].id }] })}>+ Kochbasis</button>
        )}
      </div>
      <textarea className="kitchen-input kitchen-textarea" placeholder="Zubereitungsschritte" value={r.steps} onChange={(e) => set({ steps: e.target.value })} />
      {error && <div className="kitchen-warn">{error}</div>}
      <div className="kitchen-row">
        <button className="kitchen-btn primary" disabled={busy || !r.name.trim()} onClick={save}>Speichern</button>
        <button className="kitchen-btn" onClick={onCancel}>Abbrechen</button>
      </div>
    </div>
  );
}

function RecipesView() {
  const [rows, setRows] = useState<RecipeSummary[] | null>(null);
  const [editing, setEditing] = useState<Recipe | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await apiFetch<Dataset<RecipeSummary>>('/kitchen/recipes');
    if (isApiError(res)) { setError(res.error.message); return; }
    setRows(res.rows);
  }, []);
  useEffect(() => { load(); }, [load]);

  const open = async (id: string) => {
    const res = await apiFetch<Dataset<Recipe>>(`/kitchen/recipes/${id}`);
    if (isApiError(res)) { setError(res.error.message); return; }
    setEditing(res.rows[0]);
  };

  if (!rows) return <div className="kitchen-page"><Loading error={error} /></div>;
  if (editing) {
    return (
      <div className="kitchen-page">
        <RecipeForm initial={editing} bases={rows.filter((r) => r.kind === 'base')}
                    onSaved={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />
      </div>
    );
  }
  const label: Record<RecipeKind, string> = { base: 'Kochbasen', derived: 'Abgeleitete Gerichte', favorite: 'Favoriten' };
  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Rezepte</h1>
      <button className="kitchen-btn primary" onClick={() => setEditing(EMPTY)}>Neues Rezept</button>
      {(['base', 'derived', 'favorite'] as RecipeKind[]).map((k) => (
        <React.Fragment key={k}>
          <div className="kitchen-day">{label[k]}</div>
          {rows.filter((r) => r.kind === k).map((r) => (
            <button key={r.id} className="kitchen-btn" style={{ textAlign: 'left' }} onClick={() => open(r.id)}>
              {r.name} <span className="kitchen-muted">· {num(r.servings)} {r.yield_unit}</span>
            </button>
          ))}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function KitchenApp() {
  return (
    <Routes>
      <Route path="/" element={<PlanView />} />
      <Route path="/shopping" element={<ShoppingView />} />
      <Route path="/recipes" element={<RecipesView />} />
    </Routes>
  );
}
