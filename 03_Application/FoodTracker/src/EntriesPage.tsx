/**
 * EntriesPage — Sprint 03
 *
 * Top-level entries overview screen for /food/entries.
 * Fetches GET /api/food/entries on mount. Renders all stored meal entries
 * with row-level delete, copy, and open-detail actions.
 *
 * Behaviours:
 * - Delete: confirmation dialog → DELETE /api/food/entries/{id} → remove from list
 * - Copy:   POST /api/food/entries/{id}/copy → navigate to /food/entries/{newId}
 * - Detail: navigate to /food/entries/{id}
 */

import { useState, useEffect } from 'react';
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
}

interface EntryDetail {
  id: string;
  [key: string]: unknown;
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

// ── EntriesPage ───────────────────────────────────────────────────────────────

export default function EntriesPage() {
  const navigate = useNavigate();

  const [entries,         setEntries]         = useState<EntryRow[] | null>(null);
  const [isLoading,       setIsLoading]       = useState(true);
  const [error,           setError]           = useState<ApiError | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting,      setIsDeleting]      = useState(false);
  const [deleteError,     setDeleteError]     = useState<ApiError | null>(null);
  const [isCopying,       setIsCopying]       = useState<string | null>(null); // id being copied

  useEffect(() => {
    apiFetch<{ meta: object; schema: object[]; rows: EntryRow[] }>('/food/entries').then((res) => {
      setIsLoading(false);
      if (isApiError(res)) {
        setError(res);
      } else {
        const dataset = res as { meta: object; schema: object[]; rows: EntryRow[] };
        setEntries(dataset.rows ?? []);
      }
    });
  }, []);

  // ── Delete handlers ────────────────────────────────────────────────────────

  function handleDeleteTrigger(id: string) {
    setDeleteError(null);
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
        setDeleteError(res);
        setDeleteConfirmId(null);
      } else {
        // Remove from local list
        setEntries((prev) => prev ? prev.filter((e) => e.id !== deleteConfirmId) : prev);
        setDeleteConfirmId(null);
      }
    } finally {
      setIsDeleting(false);
    }
  }

  // ── Copy handler ───────────────────────────────────────────────────────────

  async function handleCopy(id: string) {
    setIsCopying(id);
    try {
      const res = await apiFetch<EntryDetail>(`/food/entries/${id}/copy`, {
        method: 'POST',
      });
      if (isApiError(res)) {
        setDeleteError(res); // reuse error display for copy errors
      } else {
        const copied = res as EntryDetail;
        navigate(`/food/entries/${copied.id}`);
      }
    } finally {
      setIsCopying(null);
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

      {deleteError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={deleteError} />
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
                <div>
                  <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                    {entry.logged_at} &middot; {entry.meal_type}
                  </p>
                  <p className="type-body" style={{ margin: 0, fontWeight: 500 }}>
                    {entry.dish_name}
                  </p>
                  <p className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                    {entry.kcal} kcal
                  </p>
                </div>

                {/* Row actions */}
                <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                  <button
                    className="btn-outlined"
                    style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                    onClick={() => navigate(`/food/entries/${entry.id}`)}
                    title="Open detail"
                  >
                    Detail
                  </button>
                  <button
                    className="btn-outlined"
                    style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                    onClick={() => handleCopy(entry.id)}
                    disabled={isCopying === entry.id}
                    title="Copy entry"
                  >
                    {isCopying === entry.id ? 'Copying…' : 'Copy'}
                  </button>
                  <button
                    className="btn-outlined"
                    style={{
                      fontSize: '0.8rem',
                      padding: '4px 10px',
                      color: 'var(--md-sys-color-error)',
                      borderColor: 'var(--md-sys-color-error)',
                    }}
                    onClick={() => handleDeleteTrigger(entry.id)}
                    title="Delete entry"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
