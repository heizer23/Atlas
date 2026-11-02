/**
 * Cooked batch management (UI): cooking-completion dialog that splits the produced portions between
 * refrigerator and freezer, batch rows with freeze / thaw / use / discard, and base availability chips.
 *
 * All stock changes are done by the Kitchen API (StorageTracker ledger + batch events); nothing is
 * calculated here beyond what the user sees. Freezing/thawing always sends an explicit best-before date.
 */

import React, { useState } from 'react';
import { dayLabel, num, useAction } from './common';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Batch {
  id: number; name: string; recipe_id: string | null; quantity: number; unit: string; location: string | null;
  storage: 'fridge' | 'freezer'; expires_at: string | null; expiry_status: 'expired' | 'expiring_soon' | null;
  produced_at: string | null; suggested_freeze_expires_at: string | null; suggested_thaw_expires_at: string | null;
}

export interface BaseInfo {
  base_recipe_id: string; name: string; needed: number; ready: number; frozen: number; planned_cook: number;
  status: 'ready' | 'will_be_cooked' | 'needs_thaw' | 'missing';
}

/** What the dialog needs to know about the cooking session (all from the plan payload). */
export interface CookTarget {
  id: string; recipe_name: string; portions: number;
  shelf_life_days: number | null; freezer_shelf_life_days: number | null;
}

// ── Cooking completion dialog ─────────────────────────────────────────────────

function Stepper({ value, max, onChange, label }: { value: number; max: number; onChange: (v: number) => void; label: string }) {
  return (
    <div className="kitchen-stepper" role="group" aria-label={label}>
      <button className="kitchen-btn" onClick={() => onChange(Math.max(0, value - 1))} disabled={value <= 0} aria-label={`${label}: fewer`}>−</button>
      <span className="kitchen-stepper-value" aria-live="polite">{num(value)}</span>
      <button className="kitchen-btn" onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max} aria-label={`${label}: more`}>+</button>
    </div>
  );
}

export function CookDialog({ meal, onClose, onSaved }: { meal: CookTarget; onClose: () => void; onSaved: () => void }) {
  const { post, error, busy } = useAction();
  const [produced, setProduced] = useState(meal.portions);
  const [freezer, setFreezer] = useState(0);
  const [fridgeDays, setFridgeDays] = useState<string>(meal.shelf_life_days !== null ? String(meal.shelf_life_days) : '');
  const [freezerDays, setFreezerDays] = useState<string>(meal.freezer_shelf_life_days !== null ? String(meal.freezer_shelf_life_days) : '');
  const [remember, setRemember] = useState(true);

  const fridge = Math.max(0, produced - freezer);
  const allocated = fridge + freezer;
  const complete = Math.abs(allocated - produced) < 1e-9 && produced > 0;
  const freezerNeedsDays = freezer > 0 && freezerDays.trim() === '';
  const canSave = complete && !freezerNeedsDays && !busy;
  const missingDefault = (fridge > 0 && meal.shelf_life_days === null && fridgeDays.trim() !== '') ||
                         (freezer > 0 && meal.freezer_shelf_life_days === null && freezerDays.trim() !== '');

  const save = async () => {
    const allocations: { location: string; qty: number; shelf_life_days?: number }[] = [];
    if (fridge > 0) allocations.push({ location: 'fridge', qty: fridge, ...(fridgeDays.trim() !== '' ? { shelf_life_days: Number(fridgeDays) } : {}) });
    if (freezer > 0) allocations.push({ location: 'freezer', qty: freezer, shelf_life_days: Number(freezerDays) });
    const res = await post(`/meals/${meal.id}/cooked`, { produced_qty: produced, allocations, remember_shelf_life: remember && missingDefault });
    if (res) onSaved();
  };

  return (
    <div className="kitchen-modal" role="dialog" aria-modal="true" aria-label={`Cooking completed: ${meal.recipe_name}`}>
      <div className="kitchen-sheet">
        <h2 className="type-title" style={{ margin: 0 }}>{meal.recipe_name}</h2>
        <div className="kitchen-muted">
          Cooking completed ·{' '}
          <input className="kitchen-input num" type="number" min="1" step="1" value={produced} aria-label="Portions produced"
                 onChange={(e) => { const v = Math.max(0, Number(e.target.value)); setProduced(v); setFreezer((f) => Math.min(f, v)); }} />
          {' '}portions
        </div>

        <div className="kitchen-alloc">
          <div className="kitchen-alloc-row">
            <div>
              <strong>Refrigerator</strong>
              <div className="kitchen-muted">Short-term storage · ready to use</div>
              <label className="kitchen-muted">Best before in{' '}
                <input className="kitchen-input num" type="number" min="0" value={fridgeDays} placeholder="days"
                       onChange={(e) => setFridgeDays(e.target.value)} aria-label="Refrigerator shelf life in days" /> days</label>
            </div>
            <Stepper label="Refrigerator portions" value={fridge} max={produced} onChange={(v) => setFreezer(produced - v)} />
          </div>
          <div className="kitchen-alloc-row">
            <div>
              <strong>Freezer</strong>
              <div className="kitchen-muted">Long-term storage · thaw before use</div>
              <label className="kitchen-muted">Best before in{' '}
                <input className="kitchen-input num" type="number" min="0" value={freezerDays} placeholder="days"
                       onChange={(e) => setFreezerDays(e.target.value)} aria-label="Freezer shelf life in days" /> days</label>
            </div>
            <Stepper label="Freezer portions" value={freezer} max={produced} onChange={setFreezer} />
          </div>
        </div>

        <div className={`kitchen-total${complete ? ' ok' : ''}`} aria-live="polite">
          Total allocated <strong>{num(allocated)} / {num(produced)}</strong> portions
        </div>
        {freezerNeedsDays && <div className="kitchen-warn">Enter the freezer shelf life (days) — it is never assumed.</div>}
        {fridge > 0 && fridgeDays.trim() === '' && (
          <div className="kitchen-muted">No refrigerator shelf life set: this batch will not get a best-before date.</div>
        )}
        {missingDefault && (
          <label className="kitchen-row">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember these days as the recipe default
          </label>
        )}
        {error && <div className="kitchen-warn">{error}</div>}
        <div className="kitchen-row">
          <button className="kitchen-btn primary" disabled={!canSave} onClick={save}>Save cooking</button>
          <button className="kitchen-btn" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Batch row ─────────────────────────────────────────────────────────────────

export function BatchRow({ batch, onChanged }: { batch: Batch; onChanged: () => void }) {
  const { post, error, busy } = useAction();
  const [mode, setMode] = useState<'freeze' | 'thaw' | 'use' | null>(null);
  const suggested = mode === 'freeze' ? batch.suggested_freeze_expires_at : batch.suggested_thaw_expires_at;
  const [date, setDate] = useState<string>('');
  const [qty, setQty] = useState('1');
  const frozen = batch.storage === 'freezer';

  const open = (m: 'freeze' | 'thaw' | 'use') => {
    setMode(mode === m ? null : m);
    setDate((m === 'freeze' ? batch.suggested_freeze_expires_at : batch.suggested_thaw_expires_at) ?? '');
  };
  const done = (res: unknown) => { if (res) { setMode(null); onChanged(); } };

  return (
    <div className="kitchen-batch">
      <div className="kitchen-row spread">
        <span>{batch.name}</span>
        <span className="kitchen-row">
          <span className={`kitchen-chip${frozen ? ' frozen' : ''}`}>{frozen ? 'Freezer' : 'Fridge'}</span>
          {batch.expiry_status === 'expired' && <span className="kitchen-chip expired">Expired</span>}
          {batch.expiry_status === 'expiring_soon' && <span className="kitchen-chip warn">Expires soon</span>}
        </span>
      </div>
      <div className="kitchen-muted">
        {num(batch.quantity)} {batch.unit}{batch.expires_at ? ` · until ${dayLabel(batch.expires_at)}` : ' · no best-before'}
        {frozen ? ' · thaw before use' : ''}
      </div>
      <div className="kitchen-row">
        {!frozen && batch.expiry_status !== 'expired' && (
          <>
            <button className="kitchen-btn" onClick={() => open('use')}>Use</button>
            <button className="kitchen-btn" onClick={() => open('freeze')}>Freeze</button>
          </>
        )}
        {frozen && batch.expiry_status !== 'expired' && <button className="kitchen-btn" onClick={() => open('thaw')}>Thaw</button>}
        {batch.expiry_status === 'expired' && (
          <button className="kitchen-btn" disabled={busy} onClick={async () => {
            if (!confirm(`Discard ${num(batch.quantity)} ${batch.unit} ${batch.name} (expired ${batch.expires_at})? It is removed from stock; reversible in StorageTracker history.`)) return;
            done(await post(`/batches/${batch.id}/discard`));
          }}>Discard</button>
        )}
      </div>
      {mode === 'use' && (
        <div className="kitchen-row">
          <input className="kitchen-input num" type="number" min="0.5" step="0.5" max={batch.quantity} value={qty}
                 onChange={(e) => setQty(e.target.value)} aria-label="Portions to use" />
          <button className="kitchen-btn primary" disabled={busy || !(Number(qty) > 0)}
                  onClick={async () => done(await post(`/batches/${batch.id}/consume`, { qty: Number(qty), idempotency_key: crypto.randomUUID?.() }))}>
            Use portions
          </button>
        </div>
      )}
      {(mode === 'freeze' || mode === 'thaw') && (
        <div className="kitchen-col">
          <label className="kitchen-muted">
            New best-before date after {mode === 'freeze' ? 'freezing' : 'thawing'} (never reset automatically)
            <input className="kitchen-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="New best-before date" />
          </label>
          {!suggested && <span className="kitchen-muted">
            No {mode === 'freeze' ? 'freezer shelf life' : 'thawing policy'} configured on the recipe — choose the date yourself.
          </span>}
          <button className="kitchen-btn primary" disabled={busy || !date}
                  onClick={async () => done(await post(`/batches/${batch.id}/${mode}`, { expires_at: date }))}>
            {mode === 'freeze' ? 'Move to freezer' : 'Move to refrigerator'}
          </button>
        </div>
      )}
      {error && <div className="kitchen-warn">{error}</div>}
    </div>
  );
}

// ── Availability chips for a planned meal ─────────────────────────────────────

const BASE_TEXT: Record<BaseInfo['status'], string> = {
  ready: 'ready to use', will_be_cooked: 'will be cooked', needs_thaw: 'requires thawing', missing: 'no prepared portions in stock',
};

export function BaseChips({ bases }: { bases: BaseInfo[] }) {
  if (!bases?.length) return null;
  return (
    <div className="kitchen-col">
      {bases.map((b) => (
        <span key={b.base_recipe_id} className={`kitchen-chip base-${b.status}`}>
          {b.name}: {BASE_TEXT[b.status]}
          {b.status === 'needs_thaw' ? ` (${num(b.frozen)} in freezer)` : ''}
        </span>
      ))}
    </div>
  );
}
