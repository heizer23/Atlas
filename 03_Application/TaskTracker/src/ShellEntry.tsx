/**
 * TaskTracker ShellEntry — Sprint 05
 *
 * Pending tab: two sections (Open / Pending) with effort summaries.
 * Done tab: sorted by last-modified descending.
 * Create: custom form with labels + "Create as Open" / "Create as Pending" buttons.
 * Toggle buttons next to tab bar removed.
 *
 * Routes:
 *   /tasks  → Task list
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TaskLabel {
  id:   string;
  name: string;
}

interface TaskRow extends Row {
  id:            string;
  title:         string;
  description?:  string;
  status:        string;
  priority:      string;
  due_date?:     string;
  effort_hours?: number | null;
  created_at?:   string;
  completed_at?: string;
  labels?:       TaskLabel[];
}

interface LinkGroupItem {
  object_id: string;
  type:      string;
  title?:    string | null;
}

interface LinkGroup {
  group_key: string;
  label:     string;
  items:     LinkGroupItem[];
}

interface LabelRecord {
  id:   string;
  name: string;
}

interface AttachedLabel {
  object_id:   string;
  label_id:    string;
  label_name:  string;
  attached_at: string;
}

// ── Priority chip colours ─────────────────────────────────────────────────────

const PRIORITY_COLOUR: Record<string, string> = {
  high:   'var(--md-sys-color-error)',
  medium: '#b45309',
  low:    'var(--md-sys-color-on-surface-variant)',
};

const PRIORITY_SYMBOL: Record<string, string> = {
  high:   '↑',
  medium: '–',
  low:    '↓',
};

// ── Effort formatting ─────────────────────────────────────────────────────────

function formatEffort(hours: number): string {
  if (hours === 0) return '0 h';
  return Number.isInteger(hours) ? `${hours} h` : `${hours.toFixed(1)} h`;
}

// ── LinkModal ─────────────────────────────────────────────────────────────────

const LINK_TYPE_OPTIONS = [
  { value: 'SubTask',    label: 'SubTask' },
  { value: 'Related To', label: 'Related To' },
];

function LinkModal({
  task,
  allTasks,
  onClose,
}: {
  task:     TaskRow;
  allTasks: TaskRow[];
  onClose:  () => void;
}) {
  const [searchQuery,     setSearchQuery]     = useState('');
  const [selectedTarget,  setSelectedTarget]  = useState<TaskRow | null>(null);
  const [linkType,        setLinkType]        = useState('SubTask');
  const [saving,          setSaving]          = useState(false);
  const [errorMsg,        setErrorMsg]        = useState<string | null>(null);
  const [successMsg,      setSuccessMsg]      = useState<string | null>(null);

  const filtered = allTasks
    .filter(t => t.id !== task.id && t.title.toLowerCase().includes(searchQuery.toLowerCase()))
    .slice(0, 10);

  async function handleCreate() {
    if (!selectedTarget) return;
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    await apiFetch('/linking/objects', {
      method: 'POST',
      body: JSON.stringify({ object_id: task.id, object_type: 'task', workspace_id: null, title: task.title }),
    });
    await apiFetch('/linking/objects', {
      method: 'POST',
      body: JSON.stringify({ object_id: selectedTarget.id, object_type: 'task', workspace_id: null, title: selectedTarget.title }),
    });

    const res = await apiFetch<unknown>('/linking/links', {
      method: 'POST',
      body: JSON.stringify({
        source_object_id: task.id,
        target_object_id: selectedTarget.id,
        relation_input:   linkType,
        workspace_id:     null,
        created_by_type:  'user',
        created_by_id:    null,
      }),
    });
    setSaving(false);

    if (isApiError(res)) {
      setErrorMsg((res as { error: { message?: string } }).error?.message ?? 'Failed to create link');
    } else {
      setSuccessMsg(`Linked "${selectedTarget.title}" as ${linkType}`);
      setSelectedTarget(null);
      setSearchQuery('');
    }
  }

  const overlayStyle: React.CSSProperties = {
    position:       'fixed',
    inset:          0,
    background:     'rgba(0,0,0,0.4)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         1000,
  };

  const modalStyle: React.CSSProperties = {
    background:    'var(--md-sys-color-surface)',
    border:        '1px solid var(--md-sys-color-outline-variant)',
    borderRadius:  '12px',
    padding:       'var(--space-lg)',
    width:         '420px',
    maxWidth:      '90vw',
    display:       'flex',
    flexDirection: 'column',
    gap:           'var(--space-md)',
  };

  const inputStyle: React.CSSProperties = {
    width:        '100%',
    padding:      'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    background:   'var(--md-sys-color-surface)',
    color:        'var(--md-sys-color-on-surface)',
    fontSize:     '0.95rem',
    boxSizing:    'border-box',
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className="type-display" style={{ fontSize: '1.1rem', margin: 0 }}>
            Link: {task.title}
          </h2>
          <button className="btn-outlined" onClick={onClose} style={{ padding: '2px 10px' }}>✕</button>
        </div>

        {errorMsg && (
          <p style={{ color: 'var(--md-sys-color-error)', fontSize: '0.875rem', margin: 0 }}>{errorMsg}</p>
        )}
        {successMsg && (
          <p style={{ color: 'var(--md-sys-color-primary)', fontSize: '0.875rem', margin: 0 }}>{successMsg}</p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--md-sys-color-on-surface-variant)' }}>
            Search tasks
          </label>
          <input
            type="text"
            placeholder="Type to search…"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setSelectedTarget(null); }}
            style={inputStyle}
            autoFocus
          />
          {searchQuery && (
            <div style={{
              border:       '1px solid var(--md-sys-color-outline-variant)',
              borderRadius: '6px',
              overflow:     'hidden',
              maxHeight:    '200px',
              overflowY:    'auto',
            }}>
              {filtered.length === 0 ? (
                <p style={{ padding: 'var(--space-sm)', fontSize: '0.875rem', color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
                  No tasks found
                </p>
              ) : filtered.map(t => (
                <button
                  key={t.id}
                  onClick={() => { setSelectedTarget(t); setSearchQuery(t.title); }}
                  style={{
                    display:    'block',
                    width:      '100%',
                    textAlign:  'left',
                    padding:    'var(--space-xs) var(--space-sm)',
                    background: selectedTarget?.id === t.id ? 'var(--md-sys-color-primary-container)' : 'none',
                    border:     'none',
                    borderBottom: '1px solid var(--md-sys-color-outline-variant)',
                    cursor:     'pointer',
                    fontSize:   '0.9rem',
                    color:      'var(--md-sys-color-on-surface)',
                  }}
                >
                  {t.title}
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--md-sys-color-on-surface-variant)' }}>
            Link type
          </label>
          <select value={linkType} onChange={(e) => setLinkType(e.target.value)} style={inputStyle}>
            {LINK_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button
            className="btn-filled"
            onClick={handleCreate}
            disabled={saving || !selectedTarget}
          >
            {saving ? 'Creating…' : 'Create Link'}
          </button>
          <button className="btn-outlined" onClick={onClose} disabled={saving}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ThreeDotsMenu ─────────────────────────────────────────────────────────────

function ThreeDotsMenu({
  taskId,
  onDelete,
  onLink,
  onAddLabel,
}: {
  taskId:     string;
  onDelete:   (id: string) => void;
  onLink:     (id: string) => void;
  onAddLabel: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        title="Row actions"
      >
        &#8942;
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position:     'absolute',
            right:        0,
            top:          '100%',
            marginTop:    '4px',
            background:   'var(--md-sys-color-surface)',
            border:       '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: '8px',
            boxShadow:    '0 2px 12px rgba(0,0,0,0.15)',
            minWidth:     '160px',
            zIndex:       200,
            overflow:     'hidden',
          }}
        >
          <button
            role="menuitem"
            style={{
              display:    'block',
              width:      '100%',
              textAlign:  'left',
              padding:    'var(--space-sm) var(--space-md)',
              background: 'none',
              border:     'none',
              cursor:     'pointer',
              fontSize:   '0.9rem',
              color:      'var(--md-sys-color-on-surface)',
            }}
            onClick={(e) => { e.stopPropagation(); setOpen(false); onAddLabel(taskId); }}
          >
            Add label
          </button>

          <button
            role="menuitem"
            style={{
              display:     'block',
              width:       '100%',
              textAlign:   'left',
              padding:     'var(--space-sm) var(--space-md)',
              background:  'none',
              border:      'none',
              borderTop:   '1px solid var(--md-sys-color-outline-variant)',
              cursor:      'pointer',
              fontSize:    '0.9rem',
              color:       'var(--md-sys-color-on-surface)',
            }}
            onClick={(e) => { e.stopPropagation(); setOpen(false); onLink(taskId); }}
          >
            Link
          </button>

          <button
            role="menuitem"
            style={{
              display:     'block',
              width:       '100%',
              textAlign:   'left',
              padding:     'var(--space-sm) var(--space-md)',
              background:  'none',
              border:      'none',
              borderTop:   '1px solid var(--md-sys-color-outline-variant)',
              cursor:      'pointer',
              fontSize:    '0.9rem',
              color:       'var(--md-sys-color-error)',
            }}
            onClick={(e) => { e.stopPropagation(); setOpen(false); onDelete(taskId); }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ── LabelPopover ──────────────────────────────────────────────────────────────

function LabelPopover({
  taskId,
  onClose,
  onAttached,
}: {
  taskId:     string;
  onClose:    () => void;
  onAttached: () => void;
}) {
  const [query,        setQuery]        = useState('');
  const [suggestions,  setSuggestions]  = useState<LabelRecord[]>([]);
  const [attaching,    setAttaching]    = useState(false);
  const debounceRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef      = useRef<HTMLInputElement>(null);
  const containerRef  = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) { setSuggestions([]); return; }
    debounceRef.current = setTimeout(async () => {
      const res = await apiFetch<{ rows: { id: string; name: string }[] }>(`/tasks/labels/search?q=${encodeURIComponent(value)}`);
      if (!isApiError(res)) setSuggestions((res as { rows: { id: string; name: string }[] }).rows?.map(r => ({ id: r.id, name: r.name })) ?? []);
    }, 200);
  }

  async function attachLabel(labelName: string) {
    if (!labelName.trim() || attaching) return;
    setAttaching(true);
    const res = await apiFetch<unknown>(`/tasks/${taskId}/labels`, {
      method: 'POST',
      body: JSON.stringify({ label_name: labelName.trim() }),
    });
    setAttaching(false);
    if (!isApiError(res)) {
      onAttached();
      onClose();
    }
  }

  return (
    <div
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
      style={{
        position:     'absolute',
        right:        0,
        top:          '100%',
        marginTop:    '4px',
        background:   'var(--md-sys-color-surface)',
        border:       '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: '8px',
        boxShadow:    '0 2px 12px rgba(0,0,0,0.15)',
        width:        '240px',
        zIndex:       300,
        padding:      'var(--space-sm)',
      }}
    >
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && query.trim()) {
            e.preventDefault();
            attachLabel(query);
          }
        }}
        placeholder="Type to search or add…"
        disabled={attaching}
        style={{
          width:        '100%',
          padding:      'var(--space-xs) var(--space-sm)',
          borderRadius: '6px',
          border:       '1px solid var(--md-sys-color-outline-variant)',
          background:   'var(--md-sys-color-surface)',
          color:        'var(--md-sys-color-on-surface)',
          fontSize:     '0.9rem',
          boxSizing:    'border-box',
        }}
      />
      {suggestions.length > 0 && (
        <div style={{
          marginTop:    '4px',
          border:       '1px solid var(--md-sys-color-outline-variant)',
          borderRadius: '6px',
          overflow:     'hidden',
          maxHeight:    '160px',
          overflowY:    'auto',
        }}>
          {suggestions.map(s => (
            <button
              key={s.id}
              onClick={() => attachLabel(s.name)}
              style={{
                display:      'block',
                width:        '100%',
                textAlign:    'left',
                padding:      'var(--space-xs) var(--space-sm)',
                background:   'none',
                border:       'none',
                borderBottom: '1px solid var(--md-sys-color-outline-variant)',
                cursor:       'pointer',
                fontSize:     '0.875rem',
                color:        'var(--md-sys-color-on-surface)',
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── TaskCard ──────────────────────────────────────────────────────────────────
// pendingMode=true: toggle button moves tasks between open ↔ pending
// pendingMode=false (default): toggle button marks done ↔ open

function TaskCard({
  task,
  onOpen,
  onStatusToggle,
  onDelete,
  onLink,
  onAddLabel,
  pendingMode = false,
}: {
  task:           TaskRow;
  onOpen:         (task: TaskRow) => void;
  onStatusToggle: (id: string, newStatus: string) => void;
  onDelete:       (id: string) => void;
  onLink:         (id: string) => void;
  onAddLabel:     (id: string) => void;
  pendingMode?:   boolean;
}) {
  const [labelPopoverOpen, setLabelPopoverOpen] = useState(false);

  const effortLabel =
    task.effort_hours != null ? `${task.effort_hours.toFixed(1)} h` : '—';

  const priorityColour  = PRIORITY_COLOUR[task.priority] ?? 'var(--md-sys-color-on-surface-variant)';
  const prioritySymbol  = PRIORITY_SYMBOL[task.priority] ?? '–';
  const priorityFullName = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);

  const isDone    = task.status === 'done';
  const isPending = task.status === 'pending';

  // Determine toggle button appearance and action
  let toggleTitle: string;
  let toggleNewStatus: string;
  let toggleHighlighted: boolean;

  if (pendingMode) {
    if (isPending) {
      toggleTitle      = 'Mark as open';
      toggleNewStatus  = 'open';
      toggleHighlighted = true;
    } else {
      toggleTitle      = 'Mark as pending';
      toggleNewStatus  = 'pending';
      toggleHighlighted = false;
    }
  } else {
    if (isDone) {
      toggleTitle      = 'Mark as open';
      toggleNewStatus  = 'open';
      toggleHighlighted = true;
    } else {
      toggleTitle      = 'Mark complete';
      toggleNewStatus  = 'done';
      toggleHighlighted = false;
    }
  }

  function handleToggle(e: React.MouseEvent) {
    e.stopPropagation();
    onStatusToggle(task.id, toggleNewStatus);
  }

  return (
    <div
      onClick={() => onOpen(task)}
      style={{
        display:      'flex',
        alignItems:   'center',
        gap:          'var(--space-sm)',
        padding:      'var(--space-sm) var(--space-md)',
        background:   'var(--md-sys-color-surface)',
        border:       '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: '8px',
        cursor:       'pointer',
        minWidth:     0,
      }}
    >
      {/* Task name */}
      <span
        className="type-body"
        style={{
          flex:           1,
          overflow:       'hidden',
          textOverflow:   'ellipsis',
          whiteSpace:     'nowrap',
          fontWeight:     isDone ? 400 : 500,
          textDecoration: isDone ? 'line-through' : 'none',
          color: isDone
            ? 'var(--md-sys-color-on-surface-variant)'
            : 'var(--md-sys-color-on-surface)',
        }}
      >
        {task.title}
      </span>

      {/* Effort chip */}
      <span
        className="type-label"
        style={{
          flexShrink: 0,
          minWidth:   '44px',
          textAlign:  'right',
          color:      'var(--md-sys-color-on-surface-variant)',
          fontSize:   '0.8rem',
        }}
      >
        {effortLabel}
      </span>

      {/* Priority symbol */}
      <span
        className="type-label"
        title={priorityFullName}
        style={{
          flexShrink: 0,
          minWidth:   '24px',
          textAlign:  'center',
          fontSize:   '1rem',
          fontWeight: 600,
          color:      priorityColour,
          cursor:     'default',
        }}
      >
        {prioritySymbol}
      </span>

      {/* Status toggle button */}
      <button
        className="btn-outlined"
        onClick={handleToggle}
        style={{
          flexShrink:  0,
          fontSize:    '1rem',
          padding:     '3px 10px',
          minWidth:    '36px',
          color:       toggleHighlighted ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-on-surface-variant)',
          fontWeight:  toggleHighlighted ? 700 : 400,
          borderColor: toggleHighlighted ? 'var(--md-sys-color-primary)' : undefined,
        }}
        title={toggleTitle}
      >
        ✓
      </button>

      {/* Three-dots menu */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <ThreeDotsMenu
          taskId={task.id}
          onDelete={onDelete}
          onLink={onLink}
          onAddLabel={() => setLabelPopoverOpen(true)}
        />
        {labelPopoverOpen && (
          <LabelPopover
            taskId={task.id}
            onClose={() => setLabelPopoverOpen(false)}
            onAttached={() => { setLabelPopoverOpen(false); onAddLabel(task.id); }}
          />
        )}
      </div>
    </div>
  );
}

// ── Shared label section used in both Detail and Create forms ─────────────────

function LabelSection({
  taskId,
  attachedLabels,
  onAttached,
  onDetached,
}: {
  taskId:         string;
  attachedLabels: AttachedLabel[];
  onAttached:     (label: AttachedLabel) => void;
  onDetached:     (labelId: string) => void;
}) {
  const [labelQuery,       setLabelQuery]       = useState('');
  const [labelSuggestions, setLabelSuggestions] = useState<LabelRecord[]>([]);
  const [labelAttaching,   setLabelAttaching]   = useState(false);
  const labelDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const inputStyle: React.CSSProperties = {
    width:        '100%',
    padding:      'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    background:   'var(--md-sys-color-surface)',
    color:        'var(--md-sys-color-on-surface)',
    fontSize:     '0.95rem',
    boxSizing:    'border-box',
  };

  function handleLabelQueryChange(value: string) {
    setLabelQuery(value);
    if (labelDebounceRef.current) clearTimeout(labelDebounceRef.current);
    if (!value.trim()) { setLabelSuggestions([]); return; }
    labelDebounceRef.current = setTimeout(async () => {
      const res = await apiFetch<{ rows: { id: string; name: string }[] }>(`/tasks/labels/search?q=${encodeURIComponent(value)}`);
      if (!isApiError(res)) setLabelSuggestions((res as { rows: { id: string; name: string }[] }).rows?.map(r => ({ id: r.id, name: r.name })) ?? []);
    }, 200);
  }

  async function handleAttachLabel(labelName: string) {
    if (!labelName.trim() || labelAttaching) return;
    setLabelAttaching(true);
    const res = await apiFetch<AttachedLabel>(`/tasks/${taskId}/labels`, {
      method: 'POST',
      body: JSON.stringify({ label_name: labelName.trim() }),
    });
    setLabelAttaching(false);
    if (!isApiError(res)) {
      const attached = res as AttachedLabel;
      onAttached(attached);
    }
    setLabelQuery('');
    setLabelSuggestions([]);
  }

  async function handleDetachLabel(labelId: string) {
    const res = await apiFetch<unknown>(`/tasks/${taskId}/labels/${labelId}`, { method: 'DELETE' });
    if (!isApiError(res)) onDetached(labelId);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: '4px' }}>
        Labels
      </label>

      {attachedLabels.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
          {attachedLabels.map(label => (
            <span
              key={label.label_id}
              style={{
                display:     'inline-flex',
                alignItems:  'center',
                gap:         '4px',
                padding:     '3px 10px',
                borderRadius: '12px',
                background:  'var(--md-sys-color-secondary-container)',
                color:       'var(--md-sys-color-on-secondary-container)',
                fontSize:    '0.8rem',
                fontWeight:  500,
              }}
            >
              {label.label_name}
              <button
                onClick={() => handleDetachLabel(label.label_id)}
                style={{
                  background: 'none',
                  border:     'none',
                  cursor:     'pointer',
                  padding:    '0',
                  lineHeight: 1,
                  color:      'var(--md-sys-color-on-secondary-container)',
                  fontSize:   '0.75rem',
                }}
                title={`Remove label ${label.label_name}`}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div style={{ position: 'relative' }}>
        <input
          type="text"
          value={labelQuery}
          onChange={(e) => handleLabelQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && labelQuery.trim()) {
              e.preventDefault();
              handleAttachLabel(labelQuery);
            }
          }}
          placeholder="Type to search or add label…"
          style={inputStyle}
          disabled={labelAttaching}
        />
        {labelSuggestions.length > 0 && (
          <div style={{
            position:     'absolute',
            top:          '100%',
            left:         0,
            right:        0,
            zIndex:       100,
            background:   'var(--md-sys-color-surface)',
            border:       '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: '6px',
            boxShadow:    '0 2px 8px rgba(0,0,0,0.12)',
            maxHeight:    '180px',
            overflowY:    'auto',
          }}>
            {labelSuggestions.map(s => (
              <button
                key={s.id}
                onClick={() => handleAttachLabel(s.name)}
                style={{
                  display:      'block',
                  width:        '100%',
                  textAlign:    'left',
                  padding:      'var(--space-xs) var(--space-sm)',
                  background:   'none',
                  border:       'none',
                  borderBottom: '1px solid var(--md-sys-color-outline-variant)',
                  cursor:       'pointer',
                  fontSize:     '0.9rem',
                  color:        'var(--md-sys-color-on-surface)',
                }}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}
      </div>
      <p style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)', margin: '4px 0 0' }}>
        Select a suggestion or press Enter to create and attach a new label.
      </p>
    </div>
  );
}

// ── TaskDetailEdit ────────────────────────────────────────────────────────────

function TaskDetailEdit({
  task,
  onBack,
  onSaved,
}: {
  task:    TaskRow;
  onBack:  () => void;
  onSaved: (updated: TaskRow) => void;
}) {
  const [title,       setTitle]       = useState(task.title ?? '');
  const [description, setDescription] = useState(task.description ?? '');
  const [status,      setStatus]      = useState(task.status ?? 'open');
  const [priority,    setPriority]    = useState(task.priority ?? 'medium');
  const [dueDate,     setDueDate]     = useState(task.due_date ?? '');
  const [effortHours, setEffortHours] = useState(
    task.effort_hours != null ? String(task.effort_hours) : ''
  );
  const [saving,          setSaving]          = useState(false);
  const [saveError,       setSaveError]       = useState<ApiError | null>(null);
  const [linkGroups,      setLinkGroups]      = useState<LinkGroup[]>([]);
  const [attachedLabels,  setAttachedLabels]  = useState<AttachedLabel[]>([]);

  useEffect(() => {
    apiFetch<{ object_id: string; groups: LinkGroup[] }>(`/linking/objects/${task.id}/links`)
      .then(res => {
        if (!isApiError(res)) setLinkGroups((res as { groups: LinkGroup[] }).groups ?? []);
      });
  }, [task.id]);

  useEffect(() => {
    apiFetch<{ rows: { id: string; name: string; attached_at: string }[] }>(`/tasks/${task.id}/labels`)
      .then(res => {
        if (!isApiError(res)) setAttachedLabels((res as { rows: { id: string; name: string; attached_at: string }[] }).rows?.map(r => ({ label_id: r.id, label_name: r.name, attached_at: r.attached_at })) ?? []);
      });
  }, [task.id]);

  async function handleSave() {
    if (!title.trim()) return;
    setSaving(true);
    setSaveError(null);

    const effortValue = effortHours.trim() === '' ? null : parseFloat(effortHours);

    const body = {
      title:        title.trim(),
      description:  description.trim() || null,
      status,
      priority,
      due_date:     dueDate || null,
      effort_hours: effortValue,
    };

    const res = await apiFetch<{ meta: object; schema: object[]; rows: TaskRow[] }>(
      `/tasks/${task.id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    );
    setSaving(false);

    if (isApiError(res)) {
      setSaveError(res);
    } else {
      const dataset = res as { rows: TaskRow[] };
      const updated = dataset.rows?.[0];
      if (updated) onSaved(updated);
    }
  }

  const inputStyle: React.CSSProperties = {
    width:        '100%',
    padding:      'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    background:   'var(--md-sys-color-surface)',
    color:        'var(--md-sys-color-on-surface)',
    fontSize:     '0.95rem',
    boxSizing:    'border-box',
  };

  const labelStyle: React.CSSProperties = {
    display:      'block',
    fontSize:     '0.8rem',
    fontWeight:   600,
    color:        'var(--md-sys-color-on-surface-variant)',
    marginBottom: '4px',
  };

  const fieldStyle: React.CSSProperties = {
    display:       'flex',
    flexDirection: 'column',
    gap:           '4px',
  };

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="icon-btn" aria-label="Back" onClick={onBack}>
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <h1 className="type-headline">Edit Task</h1>
      </div>

      {saveError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={saveError} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

        <div style={fieldStyle}>
          <label style={labelStyle}>Title *</label>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={inputStyle}>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="pending">Pending</option>
            <option value="done">Done</option>
          </select>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} style={inputStyle}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Due Date</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} style={inputStyle} />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Effort (h)</label>
          <input
            type="number"
            value={effortHours}
            onChange={(e) => setEffortHours(e.target.value)}
            min={0}
            step={0.5}
            placeholder="e.g. 1.5"
            style={inputStyle}
          />
        </div>

        <LabelSection
          taskId={task.id}
          attachedLabels={attachedLabels}
          onAttached={(label) =>
            setAttachedLabels(prev =>
              prev.some(l => l.label_id === label.label_id) ? prev : [...prev, label]
            )
          }
          onDetached={(labelId) =>
            setAttachedLabels(prev => prev.filter(l => l.label_id !== labelId))
          }
        />

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
          <button className="btn-filled" onClick={handleSave} disabled={saving || !title.trim()}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button className="btn-outlined" onClick={onBack} disabled={saving}>
            Cancel
          </button>
        </div>

        {linkGroups.length > 0 && (
          <div style={{ marginTop: 'var(--space-lg)', borderTop: '1px solid var(--md-sys-color-outline-variant)', paddingTop: 'var(--space-md)' }}>
            <h2 className="type-display" style={{ fontSize: '1rem', marginBottom: 'var(--space-sm)' }}>
              Linked Objects
            </h2>
            {linkGroups.map(group => (
              <div key={group.group_key} style={{ marginBottom: 'var(--space-sm)' }}>
                <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: '4px' }}>
                  {group.label}
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {group.items.map(item => (
                    <div
                      key={item.object_id}
                      style={{
                        padding:      'var(--space-xs) var(--space-sm)',
                        background:   'var(--md-sys-color-surface-variant)',
                        borderRadius: '6px',
                        fontSize:     '0.9rem',
                        color:        'var(--md-sys-color-on-surface)',
                      }}
                    >
                      {item.title ?? item.object_id}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}

// ── TaskCreatePanel ───────────────────────────────────────────────────────────
// Custom create form with labels + two submit buttons (Create as Open / Pending).
// Labels are attached immediately after the task is created.

function TaskCreatePanel({
  onCancel,
  onCreated,
}: {
  onCancel:  () => void;
  onCreated: (status: 'open' | 'pending') => void;
}) {
  const [title,        setTitle]        = useState('');
  const [description,  setDescription]  = useState('');
  const [priority,     setPriority]     = useState('medium');
  const [dueDate,      setDueDate]      = useState('');
  const [effortHours,  setEffortHours]  = useState('');
  const [pendingLabels, setPendingLabels] = useState<string[]>([]);
  const [labelQuery,   setLabelQuery]   = useState('');
  const [labelSugs,    setLabelSugs]    = useState<LabelRecord[]>([]);
  const [saving,       setSaving]       = useState(false);
  const [saveError,    setSaveError]    = useState<ApiError | null>(null);
  const labelDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleLabelQueryChange(value: string) {
    setLabelQuery(value);
    if (labelDebounceRef.current) clearTimeout(labelDebounceRef.current);
    if (!value.trim()) { setLabelSugs([]); return; }
    labelDebounceRef.current = setTimeout(async () => {
      const res = await apiFetch<{ rows: { id: string; name: string }[] }>(`/tasks/labels/search?q=${encodeURIComponent(value)}`);
      if (!isApiError(res)) setLabelSugs((res as { rows: { id: string; name: string }[] }).rows?.map(r => ({ id: r.id, name: r.name })) ?? []);
    }, 200);
  }

  function addPendingLabel(name: string) {
    const trimmed = name.trim();
    if (trimmed && !pendingLabels.includes(trimmed)) {
      setPendingLabels(prev => [...prev, trimmed]);
    }
    setLabelQuery('');
    setLabelSugs([]);
  }

  function removePendingLabel(name: string) {
    setPendingLabels(prev => prev.filter(l => l !== name));
  }

  async function handleSubmit(status: 'open' | 'pending') {
    if (!title.trim() || saving) return;
    setSaving(true);
    setSaveError(null);

    const effortValue = effortHours.trim() === '' ? null : parseFloat(effortHours);

    const res = await apiFetch<{ rows: TaskRow[] }>('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title:        title.trim(),
        description:  description.trim() || null,
        status,
        priority,
        due_date:     dueDate || null,
        effort_hours: effortValue,
      }),
    });

    if (isApiError(res)) {
      setSaving(false);
      setSaveError(res);
      return;
    }

    const newTask = (res as { rows: TaskRow[] }).rows?.[0];

    if (newTask && pendingLabels.length > 0) {
      await apiFetch(`/tasks/${newTask.id}/labels`, {
        method: 'PUT',
        body: JSON.stringify({ labels: pendingLabels }),
      });
    }

    setSaving(false);
    onCreated(status);
  }

  const inputStyle: React.CSSProperties = {
    width:        '100%',
    padding:      'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    background:   'var(--md-sys-color-surface)',
    color:        'var(--md-sys-color-on-surface)',
    fontSize:     '0.95rem',
    boxSizing:    'border-box',
  };

  const labelStyle: React.CSSProperties = {
    display:      'block',
    fontSize:     '0.8rem',
    fontWeight:   600,
    color:        'var(--md-sys-color-on-surface-variant)',
    marginBottom: '4px',
  };

  const fieldStyle: React.CSSProperties = {
    display:       'flex',
    flexDirection: 'column',
    gap:           '4px',
  };

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="icon-btn" aria-label="Cancel" onClick={onCancel}>
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginLeft: 'var(--space-sm)' }}>
          <button
            className="btn-filled"
            onClick={() => handleSubmit('open')}
            disabled={saving || !title.trim()}
          >
            {saving ? 'Creating…' : 'Create as Open'}
          </button>
          <button
            className="btn-outlined"
            onClick={() => handleSubmit('pending')}
            disabled={saving || !title.trim()}
          >
            Create as Pending
          </button>
          <button className="btn-outlined" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
        </div>
      </div>

      {saveError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={saveError} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

        <div style={fieldStyle}>
          <label style={labelStyle}>Title *</label>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} placeholder="Task title" />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} style={inputStyle}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Due Date</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} style={inputStyle} />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Effort (h)</label>
          <input
            type="number"
            value={effortHours}
            onChange={(e) => setEffortHours(e.target.value)}
            min={0}
            step={0.5}
            placeholder="e.g. 1.5"
            style={inputStyle}
          />
        </div>

        {/* ── Labels ─────────────────────────────────────────────────────── */}
        <div style={fieldStyle}>
          <label style={labelStyle}>Labels</label>

          {pendingLabels.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
              {pendingLabels.map(name => (
                <span
                  key={name}
                  style={{
                    display:      'inline-flex',
                    alignItems:   'center',
                    gap:          '4px',
                    padding:      '3px 10px',
                    borderRadius: '12px',
                    background:   'var(--md-sys-color-secondary-container)',
                    color:        'var(--md-sys-color-on-secondary-container)',
                    fontSize:     '0.8rem',
                    fontWeight:   500,
                  }}
                >
                  {name}
                  <button
                    onClick={() => removePendingLabel(name)}
                    style={{
                      background: 'none',
                      border:     'none',
                      cursor:     'pointer',
                      padding:    '0',
                      lineHeight: 1,
                      color:      'var(--md-sys-color-on-secondary-container)',
                      fontSize:   '0.75rem',
                    }}
                    title={`Remove ${name}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}

          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={labelQuery}
              onChange={(e) => handleLabelQueryChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && labelQuery.trim()) {
                  e.preventDefault();
                  addPendingLabel(labelQuery);
                }
              }}
              placeholder="Type to search or add label…"
              style={inputStyle}
            />
            {labelSugs.length > 0 && (
              <div style={{
                position:     'absolute',
                top:          '100%',
                left:         0,
                right:        0,
                zIndex:       100,
                background:   'var(--md-sys-color-surface)',
                border:       '1px solid var(--md-sys-color-outline-variant)',
                borderRadius: '6px',
                boxShadow:    '0 2px 8px rgba(0,0,0,0.12)',
                maxHeight:    '180px',
                overflowY:    'auto',
              }}>
                {labelSugs.map(s => (
                  <button
                    key={s.id}
                    onClick={() => addPendingLabel(s.name)}
                    style={{
                      display:      'block',
                      width:        '100%',
                      textAlign:    'left',
                      padding:      'var(--space-xs) var(--space-sm)',
                      background:   'none',
                      border:       'none',
                      borderBottom: '1px solid var(--md-sys-color-outline-variant)',
                      cursor:       'pointer',
                      fontSize:     '0.9rem',
                      color:        'var(--md-sys-color-on-surface)',
                    }}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)', margin: '4px 0 0' }}>
            Select a suggestion or press Enter to add a label.
          </p>
        </div>


      </div>
    </div>
  );
}

// ── TaskGroupedList ───────────────────────────────────────────────────────────

function TaskGroupedList({
  tasks,
  onOpen,
  onStatusToggle,
  onDelete,
  onLink,
  onAddLabel,
  pendingMode = false,
}: {
  tasks:          TaskRow[];
  onOpen:         (task: TaskRow) => void;
  onStatusToggle: (id: string, newStatus: string) => void;
  onDelete:       (id: string) => void;
  onLink:         (id: string) => void;
  onAddLabel:     (id: string) => void;
  pendingMode?:   boolean;
}) {
  const groupMap = new Map<string, TaskRow[]>();
  const unlabeled: TaskRow[] = [];

  for (const task of tasks) {
    const primary = task.labels?.[0]?.name;
    if (primary) {
      if (!groupMap.has(primary)) groupMap.set(primary, []);
      groupMap.get(primary)!.push(task);
    } else {
      unlabeled.push(task);
    }
  }

  const sortedNames = Array.from(groupMap.keys()).sort((a, b) => a.localeCompare(b));

  const groups: { name: string; tasks: TaskRow[] }[] = [
    ...sortedNames.map(name => ({ name, tasks: groupMap.get(name)! })),
    ...(unlabeled.length > 0 ? [{ name: 'Unlabeled', tasks: unlabeled }] : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {groups.map(group => (
        <div key={group.name}>
          <p className="section-label" style={{ marginBottom: 'var(--space-xs)' }}>
            {group.name}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {group.tasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onOpen={onOpen}
                onStatusToggle={onStatusToggle}
                onDelete={onDelete}
                onLink={onLink}
                onAddLabel={onAddLabel}
                pendingMode={pendingMode}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── LabelFilterBar ────────────────────────────────────────────────────────────
// Horizontal filter bar rendered above the task list.
// When labels is empty, renders nothing.

function LabelFilterBar({
  labels,
  selectedIds,
  onChange,
}: {
  labels:      TaskLabel[];
  selectedIds: Set<string>;
  onChange:    (ids: Set<string>) => void;
}) {
  if (labels.length === 0) return null;

  const allSelected = selectedIds.size === labels.length;

  function handleAllToggle() {
    if (allSelected) {
      onChange(new Set());
    } else {
      onChange(new Set(labels.map(l => l.id)));
    }
  }

  function handleLabelToggle(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onChange(next);
  }

  const barStyle: React.CSSProperties = {
    display:    'flex',
    flexWrap:   'wrap',
    gap:        '6px',
    padding:    'var(--space-sm) 0',
    marginBottom: 'var(--space-sm)',
  };

  const btnBase: React.CSSProperties = {
    padding:      '3px 10px',
    borderRadius: '12px',
    fontSize:     '0.8rem',
    fontWeight:   500,
    cursor:       'pointer',
    border:       '1px solid var(--md-sys-color-outline-variant)',
  };

  const btnSelected: React.CSSProperties = {
    ...btnBase,
    background: 'var(--md-sys-color-secondary-container)',
    color:      'var(--md-sys-color-on-secondary-container)',
    borderColor: 'var(--md-sys-color-secondary-container)',
  };

  const btnDeselected: React.CSSProperties = {
    ...btnBase,
    background: 'none',
    color:      'var(--md-sys-color-on-surface-variant)',
  };

  return (
    <div style={barStyle}>
      <button
        style={allSelected ? btnSelected : btnDeselected}
        onClick={handleAllToggle}
        title={allSelected ? 'Deselect all labels' : 'Select all labels'}
      >
        All
      </button>
      {labels.map(label => (
        <button
          key={label.id}
          style={selectedIds.has(label.id) ? btnSelected : btnDeselected}
          onClick={() => handleLabelToggle(label.id)}
          title={selectedIds.has(label.id) ? `Deselect "${label.name}"` : `Select "${label.name}"`}
        >
          {label.name}
        </button>
      ))}
    </div>
  );
}

// ── View types ────────────────────────────────────────────────────────────────

type ViewTab = 'active' | 'pending' | 'done';

function viewFetchUrl(view: ViewTab): string {
  if (view === 'active')  return '/tasks?view=active';
  if (view === 'pending') return '/tasks?view=pending_board';
  return '/tasks?status=done';
}

// ── TasksPage ─────────────────────────────────────────────────────────────────

function TasksPage() {
  const location = useLocation();
  const view: ViewTab =
    location.pathname === '/tasks/pending' ? 'pending' :
    location.pathname === '/tasks/done'    ? 'done'    : 'active';

  const [tasks,            setTasks]            = useState<TaskRow[] | null>(null);
  const [isLoading,        setIsLoading]        = useState(true);
  const [error,            setError]            = useState<ApiError | null>(null);
  const [selected,         setSelected]         = useState<TaskRow | null>(null);
  const [creating,         setCreating]         = useState(false);
  const [actionError,      setActionError]      = useState<ApiError | null>(null);
  const [linkingTask,      setLinkingTask]      = useState<TaskRow | null>(null);
  const [availableLabels,  setAvailableLabels]  = useState<TaskLabel[]>([]);
  const [selectedLabelIds, setSelectedLabelIds] = useState<Set<string>>(new Set());

  // Track whether selectedLabelIds has been initialised from PreferenceStore.
  // We use a ref so that the save effect can skip the first render.
  const labelIdsInitialised = useRef(false);

  const fetchTasks = useCallback(async (currentView: ViewTab) => {
    setIsLoading(true);
    const res = await apiFetch<{ meta: object; schema: object[]; rows: TaskRow[] }>(viewFetchUrl(currentView));
    setIsLoading(false);
    if (isApiError(res)) {
      setError(res);
    } else {
      const dataset = res as { rows: TaskRow[] };
      setTasks(dataset.rows ?? []);
    }
  }, []);

  useEffect(() => {
    fetchTasks(view);
  }, [fetchTasks, view]);

  // ── Load available labels once on mount ──────────────────────────────────────
  useEffect(() => {
    async function loadAvailableLabels() {
      const res = await apiFetch<{ rows: TaskLabel[] }>('/tasks/labels/used');
      if (!isApiError(res)) {
        const dataset = res as { rows: TaskLabel[] };
        setAvailableLabels(dataset.rows ?? []);
      }
      // On error: leave availableLabels as [] — filter bar will not be shown
    }
    loadAvailableLabels();
  }, []);

  // ── Load filter preference once availableLabels are known ────────────────────
  // Runs when availableLabels first becomes non-empty (or stays empty — handled by no-op).
  useEffect(() => {
    if (availableLabels.length === 0) return;

    async function loadFilterPreference() {
      const res = await apiFetch<{ rows: Array<{ value: string }> }>('/tasks/preferences/label_filter');
      const availableIds = new Set(availableLabels.map(l => l.id));

      if (!isApiError(res)) {
        const dataset = res as { rows: Array<{ value: string }> };
        const row = dataset.rows?.[0];
        if (row) {
          try {
            // PreferenceStore returns value as JSON.dumps(value_json) — must parse
            const stored: unknown = JSON.parse(row.value);
            if (Array.isArray(stored)) {
              // Intersect stored IDs with currently available labels to drop stale IDs
              const valid = (stored as string[]).filter(id => availableIds.has(id));
              labelIdsInitialised.current = true;
              setSelectedLabelIds(new Set(valid));
              return;
            }
          } catch {
            // Fall through to default
          }
        }
      }
      // 404, parse error, or unexpected shape — default to all labels selected
      labelIdsInitialised.current = true;
      setSelectedLabelIds(new Set(availableIds));
    }

    loadFilterPreference();
  }, [availableLabels]);

  // ── Save filter preference whenever selectedLabelIds changes ─────────────────
  // Skips the initial render and the mount-load; only fires after user changes.
  useEffect(() => {
    if (!labelIdsInitialised.current) return;
    apiFetch('/tasks/preferences/label_filter', {
      method: 'PUT',
      body: JSON.stringify({ label_ids: Array.from(selectedLabelIds) }),
    });
    // Fire-and-forget; errors are not surfaced to the user
  }, [selectedLabelIds]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleStatusToggle(id: string, newStatus: string) {
    setActionError(null);
    const res = await apiFetch<{ rows: TaskRow[] }>(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus }),
    });
    if (isApiError(res)) {
      setActionError(res);
    } else {
      fetchTasks(view);
    }
  }

  async function handleDelete(id: string) {
    setActionError(null);
    const res = await apiFetch<unknown>(`/tasks/${id}`, { method: 'DELETE' });
    if (isApiError(res)) {
      setActionError(res);
    } else {
      setTasks((prev) => prev ? prev.filter((t) => t.id !== id) : prev);
    }
  }

  function handleLink(id: string) {
    const task = tasks?.find(t => t.id === id) ?? null;
    setLinkingTask(task);
  }

  function handleSaved(updated: TaskRow) {
    setTasks((prev) => prev ? prev.map((t) => t.id === updated.id ? updated : t) : prev);
    setSelected(null);
  }

  function handleAddLabel(_id: string) {
    fetchTasks(view);
  }

  function handleCreated(_status: 'open' | 'pending') {
    setCreating(false);
    // Switch to the matching tab so the new task is visible
    fetchTasks(view);
  }

  // ── Render pending tab ───────────────────────────────────────────────────────

  function renderPendingTab(filteredTasks: TaskRow[]) {
    const pendingTasks = filteredTasks.filter(t => t.status === 'pending');

    const cardHandlers = {
      onOpen:         setSelected,
      onStatusToggle: handleStatusToggle,
      onDelete:       handleDelete,
      onLink:         handleLink,
      onAddLabel:     handleAddLabel,
    };

    if (pendingTasks.length === 0) {
      return (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No pending tasks.
        </p>
      );
    }

    return (
      <TaskGroupedList tasks={pendingTasks} {...cardHandlers} pendingMode />
    );
  }

  // ── Early returns ────────────────────────────────────────────────────────────

  if (selected) {
    return (
      <TaskDetailEdit
        task={selected}
        onBack={() => setSelected(null)}
        onSaved={handleSaved}
      />
    );
  }

  if (creating) {
    return (
      <TaskCreatePanel
        onCancel={() => setCreating(false)}
        onCreated={handleCreated}
      />
    );
  }

  // ── Main list render ─────────────────────────────────────────────────────────

  // Compute client-side label filter.
  // States:
  //   availableLabels empty       → show all tasks (no filter bar)
  //   all selected                → show all tasks
  //   none selected               → show empty list
  //   subset selected             → show tasks that have at least one selected label
  const allLabelsSelected = availableLabels.length === 0 || selectedLabelIds.size === availableLabels.length;
  const noLabelsSelected  = availableLabels.length > 0 && selectedLabelIds.size === 0;

  const displayedTasks: TaskRow[] = (() => {
    if (!tasks) return [];
    if (noLabelsSelected)  return [];
    if (allLabelsSelected) return tasks;
    return tasks.filter(t => t.labels?.some(l => selectedLabelIds.has(l.id)));
  })();

  return (
    <div className="page">
      {/* Page header */}
      <div className="page-header">
        <button className="icon-btn filled" aria-label="New task" onClick={() => setCreating(true)}>
          <span className="material-symbols-rounded">add</span>
        </button>
      </div>

      {actionError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={actionError} />
        </div>
      )}

      {/* Label filter bar — only shown when not loading and labels exist */}
      {!isLoading && !error && (
        <LabelFilterBar
          labels={availableLabels}
          selectedIds={selectedLabelIds}
          onChange={setSelectedLabelIds}
        />
      )}

      {isLoading ? (
        <Skeleton />
      ) : error ? (
        <ErrorCard error={error} />
      ) : view === 'pending' ? (
        renderPendingTab(displayedTasks)
      ) : view === 'active' ? (
        (() => {
          const activeOnlyTasks = displayedTasks.filter(t => t.status !== 'done');
          const todayDoneTasks  = displayedTasks.filter(t => t.status === 'done');
          const hasActive = activeOnlyTasks.length > 0;
          const hasDone   = todayDoneTasks.length > 0;
          if (!hasActive && !hasDone) {
            return (
              <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
                No tasks in this view.
              </p>
            );
          }
          return (
            <>
              {hasActive && (
                <TaskGroupedList
                  tasks={activeOnlyTasks}
                  onOpen={setSelected}
                  onStatusToggle={handleStatusToggle}
                  onDelete={handleDelete}
                  onLink={handleLink}
                  onAddLabel={handleAddLabel}
                />
              )}
              {hasDone && (
                <div style={{ marginTop: hasActive ? 'var(--space-lg)' : 0 }}>
                  <div className="section-header">
                    <span className="section-label">Done</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                    {todayDoneTasks.map(task => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        onOpen={setSelected}
                        onStatusToggle={handleStatusToggle}
                        onDelete={handleDelete}
                        onLink={handleLink}
                        onAddLabel={handleAddLabel}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          );
        })()
      ) : displayedTasks.length === 0 ? (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No tasks in this view.
        </p>
      ) : (
        // Done tab — group by completion date descending
        (() => {
          const today     = new Date().toISOString().slice(0, 10);
          const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

          function dayLabel(dateStr: string): string {
            if (dateStr === today)     return 'Today';
            if (dateStr === yesterday) return 'Yesterday';
            return new Date(dateStr + 'T00:00:00').toLocaleDateString(undefined, {
              weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
            });
          }

          // Group by date of completed_at (fall back to created_at date)
          const byDay = new Map<string, TaskRow[]>();
          for (const task of displayedTasks) {
            const raw  = task.completed_at ?? task.created_at ?? '';
            const date = raw.slice(0, 10);
            const key  = date || 'Unknown';
            if (!byDay.has(key)) byDay.set(key, []);
            byDay.get(key)!.push(task);
          }

          // Sort day keys descending
          const sortedKeys = Array.from(byDay.keys()).sort((a, b) => b.localeCompare(a));

          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
              {sortedKeys.map(key => (
                <div key={key}>
                  <p className="section-label" style={{ marginBottom: 'var(--space-xs)' }}>
                    {key === 'Unknown' ? 'Unknown date' : dayLabel(key)}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                    {byDay.get(key)!.map(task => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        onOpen={setSelected}
                        onStatusToggle={handleStatusToggle}
                        onDelete={handleDelete}
                        onLink={handleLink}
                        onAddLabel={handleAddLabel}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          );
        })()
      )}

      {linkingTask && (
        <LinkModal
          task={linkingTask}
          allTasks={tasks ?? []}
          onClose={() => setLinkingTask(null)}
        />
      )}
    </div>
  );
}

// ── Shell entry point ─────────────────────────────────────────────────────────

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/*" element={<TasksPage />} />
    </Routes>
  );
}
