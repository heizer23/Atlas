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
import { ImportView, IngredientLine, useMaster } from './RecipeImport';
import type { Line } from './RecipeImport';
import './kitchen.css';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Dataset<T> { meta: { object_type: string; total: number }; rows: T[] }

type RecipeKind = 'base' | 'derived' | 'favorite';
type MealStatus = 'planned' | 'cooked' | 'eaten' | 'skipped';

interface RecipeSummary { id: string; name: string; kind: RecipeKind; status: 'draft' | 'active'; servings: number; yield_unit: string }
interface Recipe extends RecipeSummary {
  description: string | null; prep_minutes: number | null; cook_minutes: number | null;
  steps: string; shelf_life_days: number | null; storage_location: string | null; ingredients: Line[];
}
interface Meal {
  id: string; recipe_id: string | null; recipe_name: string | null; recipe_kind: RecipeKind | null;
  kind: 'cook' | 'meal'; day: string; portions: number; status: MealStatus;
}
interface Plan { id: string; week_start: string; meals: Meal[] }
interface Batch { id: string; name: string; quantity: number; unit: string; location: string | null; expires_at: string | null }
interface ShopLine { item_id: number; name: string; unit: string; needed: number; stock: number; to_buy?: number; covered?: number }
interface Shopping {
  buy: ShopLine[]; probably_have: ShopLine[]; missing_bases: { name: string; needed: number; available: number }[];
  draft_recipes: string[];
}

type Post = <T>(path: string, body?: unknown, method?: string) => Promise<T | null>;

// ── Helpers ───────────────────────────────────────────────────────────────────

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: '2-digit' });
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
        <strong>{meal.recipe_name ?? 'Flexible day'}</strong>
        <span className="kitchen-chip">{isCook ? 'Cook' : 'Eat'} · {meal.status}</span>
      </div>
      {meal.recipe_id && <span className="kitchen-muted">{num(meal.portions)} portions</span>}
      {error && <div className="kitchen-warn">{error}</div>}

      {planned && meal.recipe_id && (
        <div className="kitchen-row">
          <input className="kitchen-input num" type="number" min="0.5" step="0.5" value={qty}
                 onChange={(e) => setQty(e.target.value)} aria-label="Portions" />
          <button className="kitchen-btn primary" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}/${isCook ? 'cooked' : 'eaten'}`,
                                     isCook ? { produced_qty: Number(qty) } : { portions: Number(qty) })}>
            {isCook ? 'Cooked' : 'Eaten'}
          </button>
        </div>
      )}
      {planned && !meal.recipe_id && (
        <button className="kitchen-btn" disabled={busy}
                onClick={() => run(`/meals/${meal.id}/eaten`)}>Eaten (no booking)</button>
      )}
      {planned && (
        <div className="kitchen-row">
          <button className="kitchen-btn" onClick={() => setMoving(!moving)}>Move / swap</button>
          <button className="kitchen-btn" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}`, { status: 'skipped' }, 'PATCH')}>Skip</button>
        </div>
      )}
      {planned && moving && (
        <div className="kitchen-row">
          <input className="kitchen-input" type="date" value={newDay} onChange={(e) => setNewDay(e.target.value)} />
          <select className="kitchen-input" value={swap} onChange={(e) => setSwap(e.target.value)}>
            <option value="">Flexible day</option>
            {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <button className="kitchen-btn primary" disabled={busy}
                  onClick={() => run(`/meals/${meal.id}`, { day: newDay, recipe_id: swap || null }, 'PATCH')}>Save</button>
        </div>
      )}
      {(meal.status === 'cooked' || meal.status === 'eaten') && (
        <button className="kitchen-btn" disabled={busy}
                onClick={() => run(`/meals/${meal.id}/undo`)}>Undo</button>
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
    if (!isApiError(r)) setRecipes(r.rows.filter((x) => x.status === 'active'));
    const b = await apiFetch<Dataset<Batch>>('/kitchen/batches');
    if (!isApiError(b)) setBatches(b.rows);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (plan === undefined) return <div className="kitchen-page"><Loading error={error} /></div>;

  const days = plan ? Array.from(new Set(plan.meals.map((m) => m.day))) : [];
  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Week plan</h1>
      {batches.length > 0 && (
        <div className="kitchen-card">
          <strong>Cooked bases in stock</strong>
          {batches.map((b) => (
            <div key={b.id} className="kitchen-row spread">
              <span>{b.name}</span>
              <span className="kitchen-muted">{num(b.quantity)} {b.unit}{b.expires_at ? ` · until ${dayLabel(b.expires_at)}` : ''}</span>
            </div>
          ))}
        </div>
      )}
      <button className="kitchen-btn primary" disabled={busy}
              onClick={async () => { if (await post('/plans/suggest', {})) load(); }}>
        {plan ? 'Suggest new week plan' : 'Suggest week plan'}
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
      <strong>Add meal</strong>
      <div className="kitchen-row">
        <select className="kitchen-input" value={recipeId} onChange={(e) => setRecipeId(e.target.value)}>
          <option value="">Choose recipe…</option>
          {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <input className="kitchen-input" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        <button className="kitchen-btn primary" disabled={busy || !recipe}
                onClick={async () => {
                  if (await post(`/plans/${planId}/meals`, { recipe_id: recipeId, day, kind: recipe!.kind === 'base' ? 'cook' : 'meal' })) {
                    setRecipeId(''); onAdded();
                  }
                }}>Add</button>
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
        <span className="kitchen-muted">need {num(line.needed)} {line.unit}, have {num(line.stock)}</span>
      </div>
      <div className="kitchen-row">
        <input className="kitchen-input num" type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />
        <span>{line.unit}</span>
        <button className="kitchen-btn primary" disabled={busy || !(Number(qty) > 0)}
                onClick={async () => {
                  if (await post('/shopping/purchase', { item_id: line.item_id, qty: Number(qty), idempotency_key: crypto.randomUUID?.() })) onDone();
                }}>Bought</button>
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
        <span className="kitchen-muted">need {num(line.needed)} {line.unit} · stock {num(line.stock)}</span>
      </div>
      <div className="kitchen-row">
        <input className="kitchen-input num" type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />
        <span>{line.unit} actually on hand</span>
        <button className="kitchen-btn" disabled={busy}
                onClick={async () => { if (await post('/shopping/stocktake', { item_id: line.item_id, qty: Number(qty) })) onDone(); }}>
          Confirm
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
  if (data === null) return <div className="kitchen-page"><p className="kitchen-muted">No week plan yet.</p></div>;

  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Shopping</h1>
      {data.draft_recipes.length > 0 && (
        <div className="kitchen-warn">Not included (draft, ingredients not assigned): {data.draft_recipes.join(', ')}</div>
      )}
      {data.missing_bases.map((b) => (
        <div key={b.name} className="kitchen-warn">
          Cooked base "{b.name}" is missing: need {num(b.needed)}, available {num(b.available)} — add a cooking session to the plan.
        </div>
      ))}
      <div className="kitchen-day">To buy ({data.buy.length})</div>
      {data.buy.length === 0 && <p className="kitchen-muted">Nothing to buy.</p>}
      {data.buy.map((l) => <BuyRow key={`${l.item_id}-${l.stock}`} line={l} onDone={load} />)}
      <div className="kitchen-day">Probably on hand ({data.probably_have.length})</div>
      {data.probably_have.map((l) => <HaveRow key={`${l.item_id}-${l.stock}`} line={l} onDone={load} />)}
    </div>
  );
}

// ── Recipes view ──────────────────────────────────────────────────────────────

const EMPTY: Recipe = { id: '', name: '', kind: 'favorite', status: 'draft', servings: 2, yield_unit: 'portions',
                        description: null, prep_minutes: null, cook_minutes: null, steps: '',
                        shelf_life_days: null, storage_location: null, ingredients: [] };

function RecipeForm({ initial, bases, onSaved, onCancel }: { initial: Recipe; bases: RecipeSummary[]; onSaved: () => void; onCancel: () => void }) {
  const { post, error, busy } = useAction();
  const { master, add } = useMaster();
  const [r, setR] = useState<Recipe>(initial);
  const set = (patch: Partial<Recipe>) => setR({ ...r, ...patch });
  const setIng = (i: number, patch: Partial<Line>) =>
    set({ ingredients: r.ingredients.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const minutes = (v: string) => (v === '' ? null : Number(v));

  const save = async () => {
    const body = {
      name: r.name, kind: r.kind, servings: r.servings, description: r.description, prep_minutes: r.prep_minutes,
      cook_minutes: r.cook_minutes, steps: r.steps, shelf_life_days: r.shelf_life_days, storage_location: r.storage_location,
      ingredients: r.ingredients.filter((i) => i.name.trim() || i.item_id || i.base_recipe_id).map((i) => ({
        name: i.name || i.item_name || '', qty: Number(i.qty), unit: i.base_recipe_id ? 'portions' : i.unit,
        base_recipe_id: i.base_recipe_id, item_id: i.item_id,
      })),
    };
    const res = r.id ? await post(`/recipes/${r.id}`, body, 'PATCH') : await post('/recipes', body);
    if (res) onSaved();
  };

  return (
    <div className="kitchen-card">
      <input className="kitchen-input" placeholder="Name" value={r.name} onChange={(e) => set({ name: e.target.value })} />
      <input className="kitchen-input" placeholder="Description" value={r.description ?? ''} onChange={(e) => set({ description: e.target.value || null })} />
      <div className="kitchen-row">
        <select className="kitchen-input" value={r.kind} onChange={(e) => set({ kind: e.target.value as RecipeKind })}>
          <option value="base">Cooked base</option>
          <option value="derived">Derived dish</option>
          <option value="favorite">Favorite</option>
        </select>
        <label className="kitchen-row">Servings
          <input className="kitchen-input num" type="number" min="0.5" step="0.5" value={r.servings}
                 onChange={(e) => set({ servings: Number(e.target.value) })} /></label>
        <label className="kitchen-row">Prep (min)
          <input className="kitchen-input num" type="number" min="0" value={r.prep_minutes ?? ''} onChange={(e) => set({ prep_minutes: minutes(e.target.value) })} /></label>
        <label className="kitchen-row">Cook (min)
          <input className="kitchen-input num" type="number" min="0" value={r.cook_minutes ?? ''} onChange={(e) => set({ cook_minutes: minutes(e.target.value) })} /></label>
        {r.kind === 'base' && (
          <label className="kitchen-row">Shelf life (days)
            <input className="kitchen-input num" type="number" min="0" value={r.shelf_life_days ?? ''}
                   onChange={(e) => set({ shelf_life_days: minutes(e.target.value) })} /></label>
        )}
      </div>
      <strong>Ingredients</strong>
      {r.ingredients.map((ing, i) => (
        <IngredientLine key={i} line={ing} master={master} onChange={(p) => setIng(i, p)} onCreated={add}
                        onRemove={() => set({ ingredients: r.ingredients.filter((_, j) => j !== i) })} />
      ))}
      <div className="kitchen-row">
        <button className="kitchen-btn" onClick={() => set({ ingredients: [...r.ingredients, { name: '', qty: 1, unit: 'g', item_id: null, base_recipe_id: null }] })}>+ Ingredient</button>
        {bases.length > 0 && r.kind !== 'base' && (
          <button className="kitchen-btn" onClick={() => set({ ingredients: [...r.ingredients, { name: bases[0].name, qty: 2, unit: 'portions', item_id: null, base_recipe_id: bases[0].id }] })}>+ Cooked base</button>
        )}
      </div>
      <textarea className="kitchen-input kitchen-textarea" placeholder="Preparation steps" value={r.steps} onChange={(e) => set({ steps: e.target.value })} />
      {error && <div className="kitchen-warn">{error}</div>}
      <span className="kitchen-muted">Recipes with unassigned ingredients are saved as drafts.</span>
      <div className="kitchen-row">
        <button className="kitchen-btn primary" disabled={busy || !r.name.trim()} onClick={save}>Save</button>
        <button className="kitchen-btn" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function RecipesView() {
  const [rows, setRows] = useState<RecipeSummary[] | null>(null);
  const [editing, setEditing] = useState<Recipe | null>(null);
  const [importing, setImporting] = useState(false);
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
  if (importing) return <ImportView onClose={() => setImporting(false)} onSaved={() => { setImporting(false); load(); }} />;
  if (editing) {
    return (
      <div className="kitchen-page">
        <RecipeForm initial={editing} bases={rows.filter((r) => r.kind === 'base')}
                    onSaved={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />
      </div>
    );
  }
  const label: Record<RecipeKind, string> = { base: 'Cooked bases', derived: 'Derived dishes', favorite: 'Favorites' };
  return (
    <div className="kitchen-page">
      <h1 className="type-headline">Recipes</h1>
      <div className="kitchen-row">
        <button className="kitchen-btn primary" onClick={() => setEditing(EMPTY)}>New recipe</button>
        <button className="kitchen-btn" onClick={() => setImporting(true)}>Import</button>
      </div>
      {(['base', 'derived', 'favorite'] as RecipeKind[]).map((k) => (
        <React.Fragment key={k}>
          <div className="kitchen-day">{label[k]}</div>
          {rows.filter((r) => r.kind === k).map((r) => (
            <button key={r.id} className="kitchen-btn" style={{ textAlign: 'left' }} onClick={() => open(r.id)}>
              {r.name} <span className="kitchen-muted">· {num(r.servings)} {r.yield_unit}</span>
              {r.status === 'draft' && <span className="kitchen-chip warn"> Draft</span>}
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
