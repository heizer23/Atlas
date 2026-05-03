/**
 * EntriesPage — Sprint 08
 *
 * Top-level entries overview screen for /food/entries.
 *
 * Sprint 08 changes from Sprint 04:
 * - Add selectedDate state (YYYY-MM-DD, default = today).
 * - Render a date input in the page header.
 * - handleCopy POSTs { logged_at: selectedDate + 'T12:00:00' } to the copy endpoint
 *   so copied meals default to the user's selected date, not server now().
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
          <button className="btn-danger" onClick={onConfirm}>
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

// ── Date grouping helpers ─────────────────────────────────────────────────────

/**
 * Format a YYYY-MM-DD date string as a full date heading.
 * e.g. "2026-04-08" → "Wednesday, 8 April 2026"
 */
function _formatDateHeading(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

/**
 * Extract YYYY-MM-DD from a logged_at string (either YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD).
 */
function _dateKey(logged_at: string): string {
  return logged_at.slice(0, 10);
}

// ── GroupedEntries ─────────────────────────────────────────────────────────────

interface GroupedEntriesProps {
  entries:          EntryRow[];
  onToggleStandard: (id: string, desiredState: boolean) => void;
  onCopy:           (id: string) => void;
  onDeleteTrigger:  (id: string) => void;
  navigate:         (path: string) => void;
}

function GroupedEntries({ entries, onToggleStandard, onCopy, onDeleteTrigger, navigate }: GroupedEntriesProps) {
  // Group entries by date, most recent date first.
  // Within each group, sort by logged_at ascending (earliest meal first).
  const groupOrder: string[] = [];
  const groupMap: Record<string, EntryRow[]> = {};

  // entries are already sorted descending by logged_at from the backend
  // We build groups maintaining date order (most recent first).
  for (const entry of entries) {
    const dk = _dateKey(entry.logged_at);
    if (!groupMap[dk]) {
      groupOrder.push(dk);
      groupMap[dk] = [];
    }
    groupMap[dk].push(entry);
  }

  // Sort each group ascending by logged_at
  for (const dk of groupOrder) {
    groupMap[dk].sort((a, b) => a.logged_at.localeCompare(b.logged_at));
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {groupOrder.map((dk) => (
        <div key={dk}>
          {/* Date heading */}
          <p
            className="type-label"
            style={{
              color: 'var(--md-sys-color-on-surface-variant)',
              fontWeight: 600,
              marginBottom: 'var(--space-xs)',
              marginTop: 0,
            }}
          >
            {_formatDateHeading(dk)}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {groupMap[dk].map((entry) => (
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
                      {entry.logged_at.includes('T') ? entry.logged_at.split('T')[1].slice(0, 5) : entry.logged_at}
                      {' '}&middot;{' '}{entry.meal_type}
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
                    onToggleStandard={onToggleStandard}
                    onCopy={onCopy}
                    onDeleteTrigger={onDeleteTrigger}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── EntriesPage ───────────────────────────────────────────────────────────────

export default function EntriesPage() {
  const navigate = useNavigate();

  // Sprint 08: date context — all copy operations default to this date
  const [selectedDate,    setSelectedDate]    = useState<string>(
    () => new Date().toLocaleDateString('en-CA'),  // YYYY-MM-DD
  );

  const [entries,         setEntries]         = useState<EntryRow[] | null>(null);
  const [isLoading,       setIsLoading]       = useState(true);
  const [error,           setError]           = useState<ApiError | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting,      setIsDeleting]      = useState(false);
  const [actionError,     setActionError]     = useState<ApiError | null>(null);
  const [searchQuery,     setSearchQuery]     = useState<string>('');

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
    // Sprint 08: pass selectedDate so the copy lands on the user's chosen day.
    const body = JSON.stringify({ logged_at: `${selectedDate}T12:00:00` });
    const res = await apiFetch<unknown>(`/food/entries/${id}/copy`, { method: 'POST', body });
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

        <Skeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
          <h1 className="type-display" style={{ margin: 0 }}>Entries</h1>
          {/* Sprint 08: date context picker — copies land on this date */}
          <label className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)', display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
            Date
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{
                padding: '4px 8px',
                border: '1px solid var(--md-sys-color-outline)',
                borderRadius: '4px',
                background: 'var(--md-sys-color-surface)',
                color: 'var(--md-sys-color-on-surface)',
                fontSize: '0.9rem',
              }}
            />
          </label>
        </div>
      </div>

      {actionError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={actionError} />
        </div>
      )}

      {/* Search input */}
      <div style={{ marginBottom: 'var(--space-sm)' }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search dishes\u2026"
          style={{
            width: '100%',
            padding: '8px 12px',
            background: 'var(--md-sys-color-surface)',
            border: '1px solid var(--md-sys-color-outline)',
            borderRadius: '4px',
            color: 'var(--md-sys-color-on-surface)',
            fontSize: '0.9rem',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {entries === null || entries.length === 0 ? (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No meal entries logged yet.
        </p>
      ) : (() => {
        const trimmed = searchQuery.trim().toLowerCase();
        const filtered = trimmed
          ? entries.filter((e) => e.dish_name.toLowerCase().includes(trimmed))
          : entries;
        return filtered.length === 0 ? (
          <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
            No entries match your search.
          </p>
        ) : (
          <GroupedEntries
            entries={filtered}
            onToggleStandard={handleToggleStandard}
            onCopy={handleCopy}
            onDeleteTrigger={handleDeleteTrigger}
            navigate={navigate}
          />
        );
      })()}
    </div>
  );
}
