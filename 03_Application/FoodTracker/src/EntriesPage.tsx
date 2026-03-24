/**
 * EntriesPage — Sprint 04
 *
 * Top-level entries overview screen for /food/entries.
 * Fetches GET /api/food/entries on mount. Each row now exposes a three-dots
 * menu with Standard / Remove Standard / Delete actions.
 *
 * Sprint 04 changes from Sprint 03:
 * - EntryRow now includes `standard: boolean`
 * - Flat action buttons replaced with ThreeDotsMenu per row
 * - Standard / Remove Standard calls PATCH /api/food/entries/{id}/standard
 *   and updates local state on success (no full re-fetch needed)
 * - Delete flow unchanged from Sprint 03
 * - row_actions from backend is now ['delete'] only; Copy button removed
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Row } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EntryRow extends Row {
  id:         string;
  logged_at:  string;
  meal_type:  string;
  dish_name:  string;
  kcal:       number;
  protein_g?: number;
  fat_g?:     number;
  standard:   boolean;  // Sprint 04
}

// ── DeleteConfirmDialog ───────────────────────────────────────────────────────

function DeleteConfirmDialog({
  open,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.4)',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: 'var(--md-sys-color-surface)',
          borderRadius: '12px',
          padding: 'var(--space-lg)',
          maxWidth: '360px',
          width: '90%',
          boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
        }}
      >
        <h2
          id="delete-dialog-title"
          className="type-title"
          style={{ marginBottom: 'var(--space-sm)' }}
        >
          Delete entry?
        </h2>
        <p
          className="type-body"
          style={{
            color: 'var(--md-sys-color-on-surface-variant)',
            marginBottom: 'var(--space-md)',
          }}
        >
          This will permanently remove the meal entry. This action cannot be undone.
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
          <button className="btn-outlined" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn-primary"
            style={{ background: 'var(--md-sys-color-error)', color: 'var(--md-sys-color-on-error)' }}
            onClick={onConfirm}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ThreeDotsMenu ─────────────────────────────────────────────────────────────

function ThreeDotsMenu({
  entryId,
  isStandard,
  onToggleStandard,
  onCopy,
  onDeleteTrigger,
}: {
  entryId: string;
  isStandard: boolean;
  onToggleStandard: (id: string, desiredState: boolean) => void;
  onCopy: (id: string) => void;
  onDeleteTrigger: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
      <button
        aria-label="Row actions"
        aria-haspopup="true"
        aria-expanded={open}
        className="btn-outlined"
        style={{ fontSize: '1rem', padding: '4px 10px', minWidth: '36px' }}
        onClick={() => setOpen((v) => !v)}
        title="Row actions"
      >
        &#8942;
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            right: 0,
            top: '100%',
            marginTop: '4px',
            background: 'var(--md-sys-color-surface)',
            border: '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: '8px',
            boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
            minWidth: '160px',
            zIndex: 200,
            overflow: 'hidden',
          }}
        >
          {/* Standard / Remove Standard */}
          <button
            role="menuitem"
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              padding: 'var(--space-sm) var(--space-md)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.9rem',
              color: 'var(--md-sys-color-on-surface)',
            }}
            onClick={() => {
              setOpen(false);
              onToggleStandard(entryId, !isStandard);
            }}
          >
            {isStandard ? 'Remove Standard' : 'Standard'}
          </button>

          {/* Copy */}
          <button
            role="menuitem"
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              padding: 'var(--space-sm) var(--space-md)',
              background: 'none',
              border: 'none',
              borderTop: '1px solid var(--md-sys-color-outline-variant)',
              cursor: 'pointer',
              fontSize: '0.9rem',
              color: 'var(--md-sys-color-on-surface)',
            }}
            onClick={() => {
              setOpen(false);
              onCopy(entryId);
            }}
          >
            Copy
          </button>

          {/* Delete */}
          <button
            role="menuitem"
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              padding: 'var(--space-sm) var(--space-md)',
              background: 'none',
              border: 'none',
              borderTop: '1px solid var(--md-sys-color-outline-variant)',
              cursor: 'pointer',
              fontSize: '0.9rem',
              color: 'var(--md-sys-color-error)',
            }}
            onClick={() => {
              setOpen(false);
              onDeleteTrigger(entryId);
            }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ── EntriesPage ───────────────────────────────────────────────────────────────

export default function EntriesPage() {
  const navigate = useNavigate();

  const [entries,         setEntries]         = useState<EntryRow[] | null>(null);
  const [isLoading,       setIsLoading]       = useState(true);
  const [error,           setError]           = useState<ApiError | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting,      setIsDeleting]      = useState(false);
  const [actionError,     setActionError]     = useState<ApiError | null>(null);

  const fetchEntries = useCallback(async () => {
    const res = await apiFetch<{ meta: object; schema: object[]; rows: EntryRow[] }>('/food/entries');
    setIsLoading(false);
    if (isApiError(res)) {
      setError(res);
    } else {
      const dataset = res as { meta: object; schema: object[]; rows: EntryRow[] };
      setEntries(dataset.rows ?? []);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  // ── Toggle standard handler ─────────────────────────────────────────────────

  async function handleToggleStandard(id: string, desiredState: boolean) {
    setActionError(null);
    const res = await apiFetch<{ id: string; standard: boolean }>(
      `/food/entries/${id}/standard`,
      {
        method: 'PATCH',
        body: JSON.stringify({ desired_standard: desiredState }),
      },
    );
    if (isApiError(res)) {
      setActionError(res);
    } else {
      await fetchEntries();
    }
  }

  async function handleCopy(id: string) {
    setActionError(null);
    const res = await apiFetch<unknown>(`/food/entries/${id}/copy`, { method: 'POST' });
    if (isApiError(res)) {
      setActionError(res);
    } else {
      await fetchEntries();
    }
  }

  // ── Delete handlers ────────────────────────────────────────────────────────

  function handleDeleteTrigger(id: string) {
    setActionError(null);
    setDeleteConfirmId(id);
  }

  function handleDeleteCancel() {
    setDeleteConfirmId(null);
  }

  async function handleDeleteConfirm() {
    if (!deleteConfirmId) return;
    setIsDeleting(true);
    try {
      const res = await apiFetch<null>(`/food/entries/${deleteConfirmId}`, {
        method: 'DELETE',
      });
      if (isApiError(res)) {
        setActionError(res);
        setDeleteConfirmId(null);
      } else {
        setEntries((prev) => prev ? prev.filter((e) => e.id !== deleteConfirmId) : prev);
        setDeleteConfirmId(null);
      }
    } finally {
      setIsDeleting(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Entries</h1>
        </div>
        <Skeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Entries</h1>
        </div>
        <ErrorCard error={error} />
      </div>
    );
  }

  return (
    <div className="page">
      <DeleteConfirmDialog
        open={deleteConfirmId !== null && !isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      <div className="page-header">
        <h1 className="type-display">Entries</h1>
      </div>

      {actionError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={actionError} />
        </div>
      )}

      {entries === null || entries.length === 0 ? (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No meal entries logged yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {entries.map((entry) => (
            <div
              key={entry.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-xs)',
                padding: 'var(--space-sm) var(--space-md)',
                background: 'var(--md-sys-color-surface)',
                border: '1px solid var(--md-sys-color-outline-variant)',
                borderRadius: '8px',
              }}
            >
              {/* Entry summary row */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 'var(--space-sm)',
                  flexWrap: 'wrap',
                }}
              >
                <div
                  style={{ cursor: 'pointer', flex: 1 }}
                  onClick={() => navigate(`/food/entries/${entry.id}`)}
                  title="Open detail"
                >
                  <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                    {entry.logged_at} &middot; {entry.meal_type}
                    {entry.standard && (
                      <span
                        style={{
                          marginLeft: 'var(--space-xs)',
                          fontSize: '0.75rem',
                          color: 'var(--md-sys-color-primary)',
                          fontWeight: 600,
                        }}
                      >
                        STANDARD
                      </span>
                    )}
                  </p>
                  <p className="type-body" style={{ margin: 0, fontWeight: 500 }}>
                    {entry.dish_name}
                  </p>
                  <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                    {entry.kcal} kcal
                  </p>
                </div>

                {/* Three-dots row menu */}
                <ThreeDotsMenu
                  entryId={entry.id}
                  isStandard={entry.standard}
                  onToggleStandard={handleToggleStandard}
                  onCopy={handleCopy}
                  onDeleteTrigger={handleDeleteTrigger}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
