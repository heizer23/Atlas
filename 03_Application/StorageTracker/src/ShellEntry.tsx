/**
 * StorageTracker ShellEntry — Sprint 02
 *
 * Views:
 *   /items              → AllItemsView
 *   /items/low-stock    → LowStockView
 *   /items/important    → ImportantItemsView
 *   /items/recycling    → RecyclingView
 *   /items/:id          → ItemDetailView
 *   /shopping           → ShoppingListView
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ItemRow extends Row {
  id:           number;
  name:         string;
  item_type:    string;
  state:        string;
  location:     string | null;
  notes:        string | null;
  source_tags:  string[];
  quantity:     number | null;
  min_quantity: number | null;
  unit:         string | null;
  expires_at:   string | null;
  expiry_status: 'expired' | 'expiring_soon' | null;
  produced_at:  string | null;
  archived_at:  string | null;
  kind:         'ingredient' | 'batch';
  stock_management_type: 'QUANTITY' | 'KANBAN';
  category:     string;
  created_at:   string;
  updated_at:   string;
  history?:     HistoryRow[];
}

interface HistoryRow extends Row {
  id:          string;
  item_id:     number;
  timestamp:   string;
  change_type: string;
  old_value:   string | null;
  new_value:   string | null;
  notes:       string | null;
}

interface ItemsDataset {
  meta: { object_type: string; total: number };
  rows: ItemRow[];
}

interface ShoppingTaskRow extends Row {
  id:           string;
  item_id:      number;
  item_name:    string;
  status:       string;
  source_tags:  string[];
  notes:        string | null;
  created_at:   string;
  completed_at: string | null;
  source_tag?:  string;  // only present in by_source view
}

interface ShoppingTasksDataset {
  meta: { object_type: string; total: number };
  rows: ShoppingTaskRow[];
}

interface FormState {
  name:             string;
  item_type:        string;
  state:            string;
  location:         string;
  notes:            string;
  source_tags:      string;   // comma-separated input
  quantity:         string;
  min_quantity:     string;
  restock_quantity: string;
  unit:             string;
  expires_at:       string;   // YYYY-MM-DD or ''
  stock_management_type: string;
  category:         string;
}

const EMPTY_FORM: FormState = {
  name:             '',
  item_type:        'object',
  state:            'stored',
  location:         '',
  notes:            '',
  source_tags:      '',
  quantity:         '',
  min_quantity:     '',
  restock_quantity: '',
  unit:             '',
  expires_at:       '',
  stock_management_type: 'QUANTITY',
  category:         'Other',
};

// ── Constants ─────────────────────────────────────────────────────────────────

const ALL_STATES = [
  'stored', 'low_stock', 'out_of_stock',
  'marked_for_recycling', 'missing', 'lent_out',
];

const ALL_TYPES = ['consumable', 'object', 'pending_action'];

const STATE_COLOURS: Record<string, string> = {
  stored:               'var(--md-sys-color-on-surface-variant)',
  low_stock:            '#b45309',
  out_of_stock:         'var(--md-sys-color-error)',
  marked_for_recycling: 'var(--md-sys-color-secondary)',
  missing:              'var(--md-sys-color-error)',
  lent_out:             'var(--md-sys-color-secondary)',
};

const CATEGORIES = [
  'Vegetables & Fruit', 'Meat & Fish', 'Dairy', 'Dry Goods', 'Spices', 'Frozen', 'Beverages', 'Other',
];

// Kanban articles: items.state is the manual status (stored = In Stock, low_stock = Low, out_of_stock = Out)
const KANBAN_STATES = ['stored', 'low_stock', 'out_of_stock'];
const KANBAN_LABEL: Record<string, string> = {
  stored: 'In Stock', low_stock: 'Low', out_of_stock: 'Out of Stock',
};

const STATE_LABEL: Record<string, string> = {
  stored:               'Stored',
  low_stock:            'Low Stock',
  out_of_stock:         'Out of Stock',
  marked_for_recycling: 'Recycling',
  missing:              'Missing',
  lent_out:             'Lent Out',
};

const TYPE_LABEL: Record<string, string> = {
  consumable:     'Consumable',
  object:         'Object',
  pending_action: 'Pending',
};

// ── Small UI pieces ───────────────────────────────────────────────────────────

function StateBadge({ state, kanban }: { state: string; kanban?: boolean }) {
  return (
    <span style={{
      display:      'inline-block',
      padding:      '2px 8px',
      borderRadius: 12,
      fontSize:     12,
      fontWeight:   600,
      background:   STATE_COLOURS[state] ?? '#888',
      color:        '#fff',
    }}>
      {(kanban ? KANBAN_LABEL[state] : undefined) ?? STATE_LABEL[state] ?? state}
    </span>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding:      '4px 12px',
        borderRadius: 16,
        border:       active ? '2px solid var(--md-sys-color-primary)' : '1px solid #ccc',
        background:   active ? 'var(--md-sys-color-primary-container)' : 'transparent',
        cursor:       'pointer',
        fontSize:     13,
        fontWeight:   active ? 600 : 400,
      }}
    >
      {label}
    </button>
  );
}

// ── Expiry ────────────────────────────────────────────────────────────────────
// Status is derived by the backend (server date, Europe/Berlin): expires_at is the last good day.
// Discarding is always an explicit confirmation and books a reversible 'expired' ledger movement.

const EXPIRY_STYLE: Record<string, React.CSSProperties> = {
  expired:       { background: '#fee2e2', color: '#991b1b', border: '1px solid #fca5a5' },
  expiring_soon: { background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d' },
};

function ExpiryLine({ item }: { item: ItemRow }) {
  const label = item.expiry_status === 'expired' ? 'EXPIRED' : item.expiry_status === 'expiring_soon' ? 'Expires soon' : null;
  return (
    <div style={{ fontSize: 13, color: '#555', marginTop: 2, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      Best before: {item.expires_at}
      {label && (
        <span style={{ ...EXPIRY_STYLE[item.expiry_status as string], fontSize: 11, padding: '1px 6px', borderRadius: 10, fontWeight: 600 }}>
          {label}
        </span>
      )}
    </div>
  );
}

function DiscardButton({ item, onDone }: { item: ItemRow; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const discard = async () => {
    const what = `${item.quantity ?? ''}${item.unit ? ' ' + item.unit : ''} ${item.name}`.trim();
    if (!confirm(`Discard ${what} (expired ${item.expires_at})? This removes it from stock; it can be reversed in the item history.`)) return;
    setBusy(true);
    await apiFetch(`/items/${item.id}/movements`, {
      method: 'POST',
      body: JSON.stringify({
        delta: -(item.quantity ?? 0), reason: 'expired',
        idempotency_key: `expired:${item.id}:${item.expires_at}`,
      }),
    });
    setBusy(false);
    onDone();
  };
  return (
    <button onClick={discard} disabled={busy} style={{ ...btnStyle, ...EXPIRY_STYLE.expired }}>Discard</button>
  );
}

function ExpiryBanner() {
  const navigate = useNavigate();
  const { items } = useItems('/items/views/expiring', []);
  if (items.length === 0) return null;
  const expired = items.filter((i) => i.expiry_status === 'expired').length;
  return (
    <div
      onClick={() => navigate('/items/expiring')}
      style={{ ...EXPIRY_STYLE[expired ? 'expired' : 'expiring_soon'], padding: '8px 12px', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}
    >
      {expired > 0 ? `${expired} expired` : ''}{expired > 0 && items.length > expired ? ' · ' : ''}
      {items.length > expired ? `${items.length - expired} expiring soon` : ''} — review
    </div>
  );
}

// ── Kanban status (manual) ────────────────────────────────────────────────────
// Low / Out create the open shopping task (backend); marking the task done resets the status to In Stock.

function KanbanStatus({ item, onChanged }: { item: ItemRow; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const set = async (state: string) => {
    if (state === item.state) return;
    setBusy(true);
    await apiFetch(`/items/${item.id}`, { method: 'PATCH', body: JSON.stringify({ state }) });
    setBusy(false);
    onChanged();
  };
  return (
    <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
      {KANBAN_STATES.map(s => (
        <Chip key={s} label={KANBAN_LABEL[s]} active={item.state === s} onClick={() => !busy && set(s)} />
      ))}
    </div>
  );
}

// ── Item row card ─────────────────────────────────────────────────────────────

const SHOPPING_STATES = new Set(['low_stock', 'out_of_stock']);

function ItemCard({
  item,
  onEdit,
  onDelete,
  onNavigate,
  onChanged,
}: {
  item: ItemRow;
  onEdit: (item: ItemRow) => void;
  onDelete: (id: number) => void;
  onNavigate: (id: number) => void;
  onChanged: () => void;
}) {
  return (
    <div style={{
      padding:      12,
      borderRadius: 8,
      border:       '1px solid #e0e0e0',
      marginBottom: 8,
      background:   '#fff',
      display:      'flex',
      justifyContent: 'space-between',
      alignItems:   'flex-start',
      gap:          12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{ fontWeight: 600, cursor: 'pointer', textDecoration: 'underline dotted' }}
            onClick={() => onNavigate(item.id)}
          >
            {item.name}
          </span>
          <span style={{ fontSize: 12, color: '#888' }} title="Article number">#{item.id}</span>
          <StateBadge state={item.state} kanban={item.stock_management_type === 'KANBAN'} />
          <span style={{ fontSize: 12, color: '#888' }}>{TYPE_LABEL[item.item_type] ?? item.item_type}</span>
          {item.category && item.category !== 'Other' && (
            <span style={{ fontSize: 12, color: '#888' }}>· {item.category}</span>
          )}
          {SHOPPING_STATES.has(item.state) && (
            <span style={{
              fontSize: 11, padding: '1px 6px', borderRadius: 10,
              background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d',
            }} title="Shopping task pending">
              cart
            </span>
          )}
        </div>
        {item.location && (
          <div style={{ fontSize: 13, color: '#555', marginTop: 2 }}>
            Location: {item.location}
          </div>
        )}
        {item.item_type === 'consumable' && item.stock_management_type !== 'KANBAN' && item.quantity !== null && (
          <div style={{ fontSize: 13, color: '#555', marginTop: 2 }}>
            Qty: {item.quantity}{item.unit ? ` ${item.unit}` : ''}{item.min_quantity !== null ? ` / min ${item.min_quantity}` : ''}
          </div>
        )}
        {item.produced_at && <div style={{ fontSize: 13, color: '#555', marginTop: 2 }}>Produced: {item.produced_at}</div>}
        {item.expires_at && <ExpiryLine item={item} />}
        {item.source_tags && item.source_tags.length > 0 && (
          <div style={{ fontSize: 12, color: '#777', marginTop: 2 }}>
            Buy at: {item.source_tags.join(', ')}
          </div>
        )}
        {item.stock_management_type === 'KANBAN' && <KanbanStatus item={item} onChanged={onChanged} />}
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        {item.expiry_status === 'expired' && <DiscardButton item={item} onDone={onChanged} />}
        <button onClick={() => onEdit(item)} style={btnStyle}>Edit</button>
        <button onClick={() => onDelete(item.id)} style={{ ...btnStyle, color: 'var(--md-sys-color-error)' }}>Del</button>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding:      '4px 10px',
  borderRadius: 6,
  border:       '1px solid #ccc',
  background:   'transparent',
  cursor:       'pointer',
  fontSize:     12,
};

// ── Item Form Modal ───────────────────────────────────────────────────────────

function ItemFormModal({
  initial,
  onClose,
  onSaved,
}: {
  initial?: ItemRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<FormState>(
    initial
      ? {
          name:             initial.name,
          item_type:        initial.item_type,
          state:            initial.state,
          location:         initial.location ?? '',
          notes:            initial.notes ?? '',
          source_tags:      (initial.source_tags ?? []).join(', '),
          quantity:         initial.quantity !== null ? String(initial.quantity) : '',
          min_quantity:     initial.min_quantity !== null ? String(initial.min_quantity) : '',
          restock_quantity: (initial as any).restock_quantity !== null && (initial as any).restock_quantity !== undefined
            ? String((initial as any).restock_quantity)
            : '',
          unit:             initial.unit ?? '',
          expires_at:       initial.expires_at ?? '',
          stock_management_type: initial.stock_management_type ?? 'QUANTITY',
          category:         initial.category ?? 'Other',
        }
      : { ...EMPTY_FORM },
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isKanban = form.item_type === 'consumable' && form.stock_management_type === 'KANBAN';

  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const body: Record<string, unknown> = {
      name:      form.name.trim(),
      item_type: form.item_type,
      state:     form.state,
      location:  form.location.trim() || null,
      notes:     form.notes.trim() || null,
      source_tags: form.source_tags
        ? form.source_tags.split(',').map(s => s.trim()).filter(Boolean)
        : [],
    };

    body.category = form.category;
    if (form.item_type === 'consumable') body.stock_management_type = form.stock_management_type;
    const kanban = form.item_type === 'consumable' && form.stock_management_type === 'KANBAN';
    if (form.item_type === 'consumable' && !kanban) {
      body.quantity         = form.quantity !== '' ? parseFloat(form.quantity) : null;
      body.min_quantity     = form.min_quantity !== '' ? parseInt(form.min_quantity, 10) : null;
      body.restock_quantity = form.restock_quantity !== '' ? parseInt(form.restock_quantity, 10) : null;
      body.unit             = form.unit.trim() || null;
    }
    // explicit null clears the date (PATCH null vs omit); new items send null too
    body.expires_at = form.expires_at || null;

    const url    = initial ? `/items/${initial.id}` : '/items';
    const method = initial ? 'PATCH' : 'POST';

    const res = await apiFetch(url, { method, body: JSON.stringify(body) });
    setSaving(false);

    if (isApiError(res)) {
      setError(res.error.message);
      return;
    }
    onSaved();
    onClose();
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: 24,
        width: '100%', maxWidth: 480, maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h3 style={{ margin: '0 0 16px' }}>{initial ? 'Edit Item' : 'New Item'}</h3>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={labelStyle}>
            Name *
            <input value={form.name} onChange={set('name')} required style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Type
            <select value={form.item_type} onChange={set('item_type')} style={inputStyle}>
              {ALL_TYPES.map(t => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            State
            <select value={form.state} onChange={set('state')} style={inputStyle}>
              {(isKanban ? KANBAN_STATES : ALL_STATES).map(s => (
                <option key={s} value={s}>{isKanban ? KANBAN_LABEL[s] : STATE_LABEL[s]}</option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            Category
            <select value={form.category} onChange={set('category')} style={inputStyle}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          {form.item_type === 'consumable' && (
            <label style={labelStyle}>
              Stock management
              <select value={form.stock_management_type}
                      onChange={(e) => setForm(f => ({
                        ...f, stock_management_type: e.target.value,
                        state: e.target.value === 'KANBAN' && !KANBAN_STATES.includes(f.state) ? 'stored' : f.state,
                      }))}
                      style={inputStyle}>
                <option value="QUANTITY">Quantity (count stock)</option>
                <option value="KANBAN">Kanban (In Stock / Low / Out)</option>
              </select>
            </label>
          )}
          <label style={labelStyle}>
            Location
            <input value={form.location} onChange={set('location')} style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Best before / expires
            <input type="date" value={form.expires_at} onChange={set('expires_at')} style={inputStyle} />
          </label>
          {form.item_type === 'consumable' && (
            <>
              {!isKanban && <>
              <label style={labelStyle}>
                Quantity
                <input type="number" min={0} step="any" value={form.quantity} onChange={set('quantity')} style={inputStyle} />
              </label>
              <label style={labelStyle}>
                Unit
                <input value={form.unit} onChange={set('unit')} placeholder="g, ml, piece, portions…" style={inputStyle} />
              </label>
              <label style={labelStyle}>
                Min Quantity
                <input type="number" min={0} value={form.min_quantity} onChange={set('min_quantity')} style={inputStyle} />
              </label>
              <label style={labelStyle}>
                Restock Quantity
                <input type="number" min={0} value={form.restock_quantity} onChange={set('restock_quantity')} style={inputStyle} placeholder="quantity to set when restocked" />
              </label>
              </>}
              <label style={labelStyle}>
                Buy at (comma-separated)
                <input value={form.source_tags} onChange={set('source_tags')} placeholder="Rewe, DM" style={inputStyle} />
              </label>
            </>
          )}
          <label style={labelStyle}>
            Notes
            <textarea value={form.notes} onChange={set('notes')} rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
          </label>
          {error && <div style={{ color: 'var(--md-sys-color-error)', fontSize: 13 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" onClick={onClose} style={btnStyle} disabled={saving}>Cancel</button>
            <button type="submit" style={{ ...btnStyle, background: 'var(--md-sys-color-primary)', color: '#fff', borderColor: 'transparent' }} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, fontWeight: 500 };
const inputStyle: React.CSSProperties = { padding: '6px 10px', borderRadius: 6, border: '1px solid #ccc', fontSize: 14 };

// ── Shared fetch hook ─────────────────────────────────────────────────────────

function useItems(url: string, deps: unknown[]) {
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await apiFetch(url);
    setLoading(false);
    if (isApiError(res)) {
      setError(res.error.message);
      return;
    }
    setItems((res as ItemsDataset).rows ?? []);
  }, [url]);

  useEffect(() => { load(); }, [load, ...deps]);

  return { items, loading, error, reload: load };
}

// ── Shared list view skeleton ─────────────────────────────────────────────────

function ItemListView({
  title,
  items,
  loading,
  error,
  reload,
  extraHeaderContent,
  topContent,
  groupByCategory,
}: {
  title: string;
  items: ItemRow[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  extraHeaderContent?: React.ReactNode;
  topContent?: React.ReactNode;
  groupByCategory?: boolean;
}) {
  const navigate = useNavigate();
  const [editItem, setEditItem]   = useState<ItemRow | null>(null);
  const [creating, setCreating]   = useState(false);

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this item?')) return;
    await apiFetch(`/items/${id}`, { method: 'DELETE' });
    reload();
  };

  // Category groups in master order (empty groups omitted); ungrouped = one headerless block
  const groupedItems: [string | null, ItemRow[]][] = groupByCategory
    ? CATEGORIES.map(c => [c, items.filter(i => (i.category ?? 'Other') === c)] as [string, ItemRow[]])
        .filter(([, rows]) => rows.length > 0)
    : [[null, items]];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {extraHeaderContent}
          <button onClick={() => setCreating(true)} style={{ ...btnStyle, background: 'var(--md-sys-color-primary)', color: '#fff', borderColor: 'transparent' }}>
            + New Item
          </button>
        </div>
      </div>

      {topContent && <div style={{ marginBottom: 12 }}>{topContent}</div>}
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {!loading && !error && items.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>No items.</div>
      )}
      {!loading && !error && groupedItems.map(([category, rows]) => (
        <div key={category ?? 'all'}>
          {category && (
            <h3 style={{ margin: '16px 0 8px', fontSize: 15, color: '#555', borderBottom: '1px solid #e0e0e0', paddingBottom: 4 }}>
              {category} <span style={{ fontWeight: 400, color: '#999' }}>({rows.length})</span>
            </h3>
          )}
          {rows.map(item => (
            <ItemCard
              key={item.id}
              item={item}
              onEdit={setEditItem}
              onDelete={handleDelete}
              onNavigate={(id: number) => navigate(`/items/${id}`)}
              onChanged={reload}
            />
          ))}
        </div>
      ))}

      {creating && (
        <ItemFormModal onClose={() => setCreating(false)} onSaved={reload} />
      )}
      {editItem && (
        <ItemFormModal initial={editItem} onClose={() => setEditItem(null)} onSaved={reload} />
      )}
    </div>
  );
}

// ── All Items View ─────────────────────────────────────────────────────────────

function AllItemsView() {
  const [stateFilter, setStateFilter]   = useState<string | null>(null);
  const [typeFilter, setTypeFilter]     = useState<string | null>(null);
  const [archivedOnly, setArchivedOnly] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const params = new URLSearchParams();
  if (stateFilter) params.set('state', stateFilter);
  if (typeFilter)  params.set('item_type', typeFilter);
  if (categoryFilter) params.set('category', categoryFilter);
  if (archivedOnly) params.set('archived', 'only');
  const url = `/items?${params.toString()}`;

  const { items, loading, error, reload } = useItems(url, [stateFilter, typeFilter, archivedOnly, categoryFilter]);

  const header = (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {ALL_STATES.map(s => (
        <Chip key={s} label={STATE_LABEL[s]} active={stateFilter === s} onClick={() => setStateFilter(stateFilter === s ? null : s)} />
      ))}
      {ALL_TYPES.map(t => (
        <Chip key={t} label={TYPE_LABEL[t]} active={typeFilter === t} onClick={() => setTypeFilter(typeFilter === t ? null : t)} />
      ))}
      <Chip label="Archived (depleted batches)" active={archivedOnly} onClick={() => setArchivedOnly(!archivedOnly)} />
    </div>
  );

  const categoryBar = (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {CATEGORIES.map(c => (
        <Chip key={c} label={c} active={categoryFilter === c} onClick={() => setCategoryFilter(categoryFilter === c ? null : c)} />
      ))}
    </div>
  );

  return (
    <ItemListView
      title="All Items"
      topContent={<><ExpiryBanner /><div style={{ marginTop: 8 }}>{categoryBar}</div></>}
      groupByCategory
      items={items}
      loading={loading}
      error={error}
      reload={reload}
      extraHeaderContent={header}
    />
  );
}

// ── Low Stock View ────────────────────────────────────────────────────────────

function LowStockView() {
  const { items, loading, error, reload } = useItems('/items/views/low_stock', []);
  return <ItemListView title="Low Stock" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Expiring View ─────────────────────────────────────────────────────────────

function ExpiringView() {
  const { items, loading, error, reload } = useItems('/items/views/expiring', []);
  return <ItemListView title="Expired &amp; expiring soon" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Important Items View ──────────────────────────────────────────────────────

function ImportantItemsView() {
  const { items, loading, error, reload } = useItems('/items/views/important', []);
  return <ItemListView title="Important Items" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Recycling View ────────────────────────────────────────────────────────────

function RecyclingView() {
  const { items, loading, error, reload } = useItems('/items/views/recycling', []);
  return <ItemListView title="Recycling" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Item Detail View ──────────────────────────────────────────────────────────

function ItemDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem]             = useState<ItemRow | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [editing, setEditing]       = useState(false);
  const [hasOpenTask, setHasOpenTask] = useState(false);
  const [taskMsg, setTaskMsg]       = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    const res = await apiFetch(`/items/${id}`);
    setLoading(false);
    if (isApiError(res)) {
      setError((res as ApiError).error.message);
      return;
    }
    const rows = (res as ItemsDataset).rows;
    const loaded = rows?.[0] ?? null;
    setItem(loaded);

    // Check if there is an open shopping task for this item
    if (loaded) {
      const tasksRes = await apiFetch(`/shopping-tasks?status=open`);
      if (!isApiError(tasksRes)) {
        const taskRows = (tasksRes as ShoppingTasksDataset).rows ?? [];
        setHasOpenTask(taskRows.some(t => t.item_id === loaded.id));
      }
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 16 }}><Skeleton /></div>;
  if (error)   return <div style={{ padding: 16 }}><ErrorCard message={error} /></div>;
  if (!item)   return <div style={{ padding: 16 }}>Item not found.</div>;

  const history: HistoryRow[] = (item as any).history ?? [];
  const itemAny = item as any;

  const handleDelete = async () => {
    if (!confirm('Delete this item?')) return;
    await apiFetch(`/items/${item.id}`, { method: 'DELETE' });
    navigate('/items');
  };

  const handleCreateTask = async () => {
    setTaskMsg(null);
    const res = await apiFetch('/shopping-tasks', {
      method: 'POST',
      body: JSON.stringify({ item_id: item.id }),
    });
    if (isApiError(res)) {
      setTaskMsg((res as ApiError).error.message);
    } else {
      setHasOpenTask(true);
      setTaskMsg('Shopping task created.');
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 600 }}>
      <button onClick={() => navigate('/items')} style={{ ...btnStyle, marginBottom: 12 }}>← Back</button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>{item.name} <span style={{ fontSize: 14, color: '#888', fontWeight: 400 }}>#{item.id}</span></h2>
        <StateBadge state={item.state} kanban={item.stock_management_type === 'KANBAN'} />
        <span style={{ fontSize: 13, color: '#888' }}>{TYPE_LABEL[item.item_type] ?? item.item_type}</span>
      </div>

      <div style={{ marginBottom: 6 }}>Category: <strong>{item.category ?? 'Other'}</strong>{item.stock_management_type === 'KANBAN' && <> · <strong>Kanban</strong></>}</div>
      {item.stock_management_type === 'KANBAN' && <div style={{ marginBottom: 8 }}><KanbanStatus item={item} onChanged={load} /></div>}

      {item.location && <div style={{ marginBottom: 6 }}>Location: <strong>{item.location}</strong></div>}

      {item.item_type === 'consumable' && item.stock_management_type !== 'KANBAN' && (
        <div style={{ marginBottom: 6 }}>
          Quantity: <strong>{item.quantity ?? '—'}{item.unit ? ` ${item.unit}` : ''}</strong>
          {item.min_quantity !== null && <> / Min: <strong>{item.min_quantity}</strong></>}
          {itemAny.restock_quantity != null && <> / Restock: <strong>{itemAny.restock_quantity}</strong></>}
        </div>
      )}

      {item.produced_at && <div style={{ marginBottom: 6 }}>Produced: <strong>{item.produced_at}</strong></div>}
      {item.archived_at && <div style={{ marginBottom: 6, color: '#777' }}>Archived (depleted) — history kept</div>}
      {item.expires_at && <ExpiryLine item={item} />}
      {item.expiry_status === 'expired' && <div style={{ margin: '6px 0' }}><DiscardButton item={item} onDone={load} /></div>}

      {item.source_tags && item.source_tags.length > 0 && (
        <div style={{ marginBottom: 6 }}>Buy at: {item.source_tags.join(', ')}</div>
      )}

      {item.notes && <div style={{ marginBottom: 6, color: '#555', fontStyle: 'italic' }}>{item.notes}</div>}

      <div style={{ fontSize: 12, color: '#aaa', marginBottom: 16 }}>
        Created: {item.created_at} · Updated: {item.updated_at}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setEditing(true)} style={btnStyle}>Edit</button>
        <button onClick={handleDelete} style={{ ...btnStyle, color: 'var(--md-sys-color-error)' }}>Delete</button>
        {!hasOpenTask && (
          <button onClick={handleCreateTask} style={{ ...btnStyle, background: '#fef3c7', borderColor: '#fcd34d' }}>
            + Shopping Task
          </button>
        )}
        {hasOpenTask && (
          <span style={{ fontSize: 12, color: '#92400e', padding: '4px 8px', background: '#fef3c7', borderRadius: 6 }}>
            Task open — see Shopping List
          </span>
        )}
      </div>
      {taskMsg && <div style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>{taskMsg}</div>}

      {history.length > 0 && (
        <div>
          <h3 style={{ margin: '0 0 8px', fontSize: 15 }}>History</h3>
          <ol style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {history.map(h => (
              <li key={h.id} style={{
                borderLeft:  '3px solid #e0e0e0',
                paddingLeft: 12,
                marginBottom: 10,
                fontSize:    13,
              }}>
                <div style={{ color: '#888', fontSize: 11 }}>{h.timestamp}</div>
                <div>
                  <strong>{h.change_type.replace('_', ' ')}</strong>
                  {h.old_value !== null && h.new_value !== null && (
                    <> — {h.old_value} → {h.new_value}</>
                  )}
                  {h.old_value === null && h.new_value !== null && (
                    <> — {h.new_value}</>
                  )}
                </div>
                {h.notes && <div style={{ color: '#777' }}>{h.notes}</div>}
              </li>
            ))}
          </ol>
        </div>
      )}

      {editing && (
        <ItemFormModal
          initial={item}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); load(); }}
        />
      )}
    </div>
  );
}

// ── Shopping List View ────────────────────────────────────────────────────────

function ShoppingListView() {
  const [grouped, setGrouped]   = useState(false);
  const [tasks, setTasks]       = useState<ShoppingTaskRow[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const url = grouped
      ? '/shopping-tasks/views/by_source'
      : '/shopping-tasks?status=open';
    const res = await apiFetch(url);
    setLoading(false);
    if (isApiError(res)) {
      setError((res as ApiError).error.message);
      return;
    }
    setTasks((res as ShoppingTasksDataset).rows ?? []);
  }, [grouped]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (taskId: string, action: 'done' | 'dismissed') => {
    setActionMsg(null);
    const res = await apiFetch(`/shopping-tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: action }),
    });
    if (isApiError(res)) {
      setActionMsg((res as ApiError).error.message);
    } else {
      load();
    }
  };

  // Plain-text export of what is on screen (flat or by store): copy to clipboard, share sheet as fallback
  const exportText = () => {
    const line = (t: ShoppingTaskRow) => `- ${t.item_name}${t.notes ? ` (${t.notes})` : ''}`;
    if (!grouped) return tasks.map(line).join('\n');
    const groups: Record<string, ShoppingTaskRow[]> = {};
    for (const row of tasks) (groups[row.source_tag ?? 'Other'] ??= []).push(row);
    return Object.keys(groups)
      .sort((a, b) => (a === 'Other' ? 1 : b === 'Other' ? -1 : a.localeCompare(b)))
      .map(tag => `${tag}:\n${groups[tag].map(line).join('\n')}`)
      .join('\n\n');
  };

  const handleCopy = async () => {
    const text = exportText();
    try {
      await navigator.clipboard.writeText(text);
      setActionMsg('Shopping list copied.');
    } catch {
      if (navigator.share) {
        try { await navigator.share({ title: 'Shopping list', text }); } catch { /* cancelled */ }
      } else {
        setActionMsg('Clipboard not available — check the browser permission.');
      }
    }
  };

  // When grouped, render rows grouped by source_tag
  const renderGrouped = () => {
    const groups: Record<string, ShoppingTaskRow[]> = {};
    for (const row of tasks) {
      const key = row.source_tag ?? 'Other';
      if (!groups[key]) groups[key] = [];
      groups[key].push(row);
    }
    // 'Other' last
    const keys = Object.keys(groups).sort((a, b) => {
      if (a === 'Other') return 1;
      if (b === 'Other') return -1;
      return a.localeCompare(b);
    });

    return keys.map(tag => (
      <div key={tag} style={{ marginBottom: 20 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 15, color: '#555', borderBottom: '1px solid #e0e0e0', paddingBottom: 4 }}>
          {tag}
        </h3>
        {groups[tag].map(t => (
          <TaskCard key={`${t.id}-${tag}`} task={t} onAction={handleAction} />
        ))}
      </div>
    ));
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Shopping List</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <Chip label="Flat" active={!grouped} onClick={() => setGrouped(false)} />
          <Chip label="By Store" active={grouped} onClick={() => setGrouped(true)} />
          <button onClick={handleCopy} disabled={tasks.length === 0} style={btnStyle}>Copy as text</button>
        </div>
      </div>

      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {actionMsg && <div style={{ color: actionMsg === 'Shopping list copied.' ? '#065f46' : 'var(--md-sys-color-error)', fontSize: 13, marginBottom: 8 }}>{actionMsg}</div>}

      {!loading && !error && tasks.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>No open shopping tasks.</div>
      )}

      {!loading && !error && tasks.length > 0 && (
        grouped
          ? renderGrouped()
          : tasks.map(t => <TaskCard key={t.id} task={t} onAction={handleAction} />)
      )}
    </div>
  );
}

function TaskCard({
  task,
  onAction,
}: {
  task: ShoppingTaskRow;
  onAction: (id: string, action: 'done' | 'dismissed') => void;
}) {
  return (
    <div style={{
      padding:      10,
      borderRadius: 8,
      border:       '1px solid #e0e0e0',
      marginBottom: 8,
      background:   '#fff',
      display:      'flex',
      justifyContent: 'space-between',
      alignItems:   'center',
      gap:          12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{task.item_name}</div>
        {task.source_tags && task.source_tags.length > 0 && (
          <div style={{ fontSize: 12, color: '#777' }}>
            Buy at: {task.source_tags.join(', ')}
          </div>
        )}
        {task.notes && <div style={{ fontSize: 12, color: '#555', fontStyle: 'italic' }}>{task.notes}</div>}
        <div style={{ fontSize: 11, color: '#aaa' }}>{task.created_at}</div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button
          onClick={() => onAction(task.id, 'done')}
          style={{ ...btnStyle, background: '#d1fae5', borderColor: '#6ee7b7' }}
        >
          Done
        </button>
        <button
          onClick={() => onAction(task.id, 'dismissed')}
          style={{ ...btnStyle, color: '#888' }}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function StorageTrackerApp() {
  return (
    <Routes>
      <Route path="/"           element={<AllItemsView />} />
      <Route path="/low-stock"  element={<LowStockView />} />
      <Route path="/important"  element={<ImportantItemsView />} />
      <Route path="/recycling"  element={<RecyclingView />} />
      <Route path="/expiring"   element={<ExpiringView />} />
      <Route path="/shopping"   element={<ShoppingListView />} />
      <Route path="/:id"        element={<ItemDetailView />} />
    </Routes>
  );
}
