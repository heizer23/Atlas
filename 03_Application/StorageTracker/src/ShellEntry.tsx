/**
 * StorageTracker ShellEntry — Sprint 01
 *
 * Views:
 *   /items              → AllItemsView
 *   /items/low-stock    → LowStockView
 *   /items/important    → ImportantItemsView
 *   /items/recycling    → RecyclingView
 *   /items/:id          → ItemDetailView
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ItemRow extends Row {
  id:           string;
  name:         string;
  item_type:    string;
  state:        string;
  location:     string | null;
  notes:        string | null;
  source_tags:  string[];
  quantity:     number | null;
  min_quantity: number | null;
  created_at:   string;
  updated_at:   string;
  history?:     HistoryRow[];
}

interface HistoryRow extends Row {
  id:          string;
  item_id:     string;
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

interface FormState {
  name:         string;
  item_type:    string;
  state:        string;
  location:     string;
  notes:        string;
  source_tags:  string;   // comma-separated input
  quantity:     string;
  min_quantity: string;
}

const EMPTY_FORM: FormState = {
  name:         '',
  item_type:    'object',
  state:        'stored',
  location:     '',
  notes:        '',
  source_tags:  '',
  quantity:     '',
  min_quantity: '',
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

function StateBadge({ state }: { state: string }) {
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
      {STATE_LABEL[state] ?? state}
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

// ── Item row card ─────────────────────────────────────────────────────────────

function ItemCard({
  item,
  onEdit,
  onDelete,
  onNavigate,
}: {
  item: ItemRow;
  onEdit: (item: ItemRow) => void;
  onDelete: (id: string) => void;
  onNavigate: (id: string) => void;
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
          <StateBadge state={item.state} />
          <span style={{ fontSize: 12, color: '#888' }}>{TYPE_LABEL[item.item_type] ?? item.item_type}</span>
        </div>
        {item.location && (
          <div style={{ fontSize: 13, color: '#555', marginTop: 2 }}>
            Location: {item.location}
          </div>
        )}
        {item.item_type === 'consumable' && item.quantity !== null && (
          <div style={{ fontSize: 13, color: '#555', marginTop: 2 }}>
            Qty: {item.quantity}{item.min_quantity !== null ? ` / min ${item.min_quantity}` : ''}
          </div>
        )}
        {item.source_tags && item.source_tags.length > 0 && (
          <div style={{ fontSize: 12, color: '#777', marginTop: 2 }}>
            Buy at: {item.source_tags.join(', ')}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
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
          name:         initial.name,
          item_type:    initial.item_type,
          state:        initial.state,
          location:     initial.location ?? '',
          notes:        initial.notes ?? '',
          source_tags:  (initial.source_tags ?? []).join(', '),
          quantity:     initial.quantity !== null ? String(initial.quantity) : '',
          min_quantity: initial.min_quantity !== null ? String(initial.min_quantity) : '',
        }
      : { ...EMPTY_FORM },
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    if (form.item_type === 'consumable') {
      body.quantity     = form.quantity !== '' ? parseInt(form.quantity, 10) : null;
      body.min_quantity = form.min_quantity !== '' ? parseInt(form.min_quantity, 10) : null;
    }

    const url    = initial ? `/api/items/${initial.id}` : '/api/items';
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
              {ALL_STATES.map(s => <option key={s} value={s}>{STATE_LABEL[s]}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            Location
            <input value={form.location} onChange={set('location')} style={inputStyle} />
          </label>
          {form.item_type === 'consumable' && (
            <>
              <label style={labelStyle}>
                Quantity
                <input type="number" min={0} value={form.quantity} onChange={set('quantity')} style={inputStyle} />
              </label>
              <label style={labelStyle}>
                Min Quantity
                <input type="number" min={0} value={form.min_quantity} onChange={set('min_quantity')} style={inputStyle} />
              </label>
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
}: {
  title: string;
  items: ItemRow[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  extraHeaderContent?: React.ReactNode;
}) {
  const navigate = useNavigate();
  const [editItem, setEditItem]   = useState<ItemRow | null>(null);
  const [creating, setCreating]   = useState(false);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this item?')) return;
    await apiFetch(`/api/items/${id}`, { method: 'DELETE' });
    reload();
  };

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

      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {!loading && !error && items.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>No items.</div>
      )}
      {!loading && !error && items.map(item => (
        <ItemCard
          key={item.id}
          item={item}
          onEdit={setEditItem}
          onDelete={handleDelete}
          onNavigate={id => navigate(`/items/${id}`)}
        />
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

  const params = new URLSearchParams();
  if (stateFilter) params.set('state', stateFilter);
  if (typeFilter)  params.set('item_type', typeFilter);
  const url = `/api/items?${params.toString()}`;

  const { items, loading, error, reload } = useItems(url, [stateFilter, typeFilter]);

  const header = (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {ALL_STATES.map(s => (
        <Chip key={s} label={STATE_LABEL[s]} active={stateFilter === s} onClick={() => setStateFilter(stateFilter === s ? null : s)} />
      ))}
      {ALL_TYPES.map(t => (
        <Chip key={t} label={TYPE_LABEL[t]} active={typeFilter === t} onClick={() => setTypeFilter(typeFilter === t ? null : t)} />
      ))}
    </div>
  );

  return (
    <ItemListView
      title="All Items"
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
  const { items, loading, error, reload } = useItems('/api/items/views/low_stock', []);
  return <ItemListView title="Low Stock" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Important Items View ──────────────────────────────────────────────────────

function ImportantItemsView() {
  const { items, loading, error, reload } = useItems('/api/items/views/important', []);
  return <ItemListView title="Important Items" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Recycling View ────────────────────────────────────────────────────────────

function RecyclingView() {
  const { items, loading, error, reload } = useItems('/api/items/views/recycling', []);
  return <ItemListView title="Recycling" items={items} loading={loading} error={error} reload={reload} />;
}

// ── Item Detail View ──────────────────────────────────────────────────────────

function ItemDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem]       = useState<ItemRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    const res = await apiFetch(`/api/items/${id}`);
    setLoading(false);
    if (isApiError(res)) {
      setError((res as ApiError).error.message);
      return;
    }
    const rows = (res as ItemsDataset).rows;
    setItem(rows?.[0] ?? null);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 16 }}><Skeleton /></div>;
  if (error)   return <div style={{ padding: 16 }}><ErrorCard message={error} /></div>;
  if (!item)   return <div style={{ padding: 16 }}>Item not found.</div>;

  const history: HistoryRow[] = (item as any).history ?? [];

  const handleDelete = async () => {
    if (!confirm('Delete this item?')) return;
    await apiFetch(`/api/items/${item.id}`, { method: 'DELETE' });
    navigate('/items');
  };

  return (
    <div style={{ padding: 16, maxWidth: 600 }}>
      <button onClick={() => navigate('/items')} style={{ ...btnStyle, marginBottom: 12 }}>← Back</button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>{item.name}</h2>
        <StateBadge state={item.state} />
        <span style={{ fontSize: 13, color: '#888' }}>{TYPE_LABEL[item.item_type] ?? item.item_type}</span>
      </div>

      {item.location && <div style={{ marginBottom: 6 }}>Location: <strong>{item.location}</strong></div>}

      {item.item_type === 'consumable' && (
        <div style={{ marginBottom: 6 }}>
          Quantity: <strong>{item.quantity ?? '—'}</strong>
          {item.min_quantity !== null && <> / Min: <strong>{item.min_quantity}</strong></>}
        </div>
      )}

      {item.source_tags && item.source_tags.length > 0 && (
        <div style={{ marginBottom: 6 }}>Buy at: {item.source_tags.join(', ')}</div>
      )}

      {item.notes && <div style={{ marginBottom: 6, color: '#555', fontStyle: 'italic' }}>{item.notes}</div>}

      <div style={{ fontSize: 12, color: '#aaa', marginBottom: 16 }}>
        Created: {item.created_at} · Updated: {item.updated_at}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button onClick={() => setEditing(true)} style={btnStyle}>Edit</button>
        <button onClick={handleDelete} style={{ ...btnStyle, color: 'var(--md-sys-color-error)' }}>Delete</button>
      </div>

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

// ── Root ──────────────────────────────────────────────────────────────────────

export default function StorageTrackerApp() {
  return (
    <Routes>
      <Route path="/"           element={<AllItemsView />} />
      <Route path="/low-stock"  element={<LowStockView />} />
      <Route path="/important"  element={<ImportantItemsView />} />
      <Route path="/recycling"  element={<RecyclingView />} />
      <Route path="/:id"        element={<ItemDetailView />} />
    </Routes>
  );
}
