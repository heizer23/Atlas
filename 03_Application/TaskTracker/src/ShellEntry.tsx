/**
 * TaskTracker ShellEntry — Sprint 02
 *
 * Replaces platform TableView+DetailView with:
 *  - TaskRow card list with ThreeDotsMenu (mark-complete / delete)
 *  - TaskDetailEdit — fully editable task detail (app-local, not platform DetailView)
 *
 * effort_hours added throughout: create form, card chip, detail edit.
 *
 * Routes:
 *   /tasks  → Task list with create form
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import CreateForm from '@platform-ui/components/CreateForm';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, FormField, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TaskLabel {
  id:   string;
  name: string;
}

interface TaskRow extends Row {
  id:           string;
  title:        string;
  description?: string;
  status:       string;
  priority:     string;
  due_date?:    string;
  effort_hours?: number | null;
  created_at?:  string;
  labels?:      TaskLabel[];
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

// ── Form field definitions ────────────────────────────────────────────────────

const TASK_FIELDS: FormField[] = [
  { key: 'title',        label: 'Title',       type: 'string', required: true, placeholder: 'Task title' },
  { key: 'description',  label: 'Description', type: 'string' },
  { key: 'priority',     label: 'Priority',    type: 'enum',   required: true,
    initialValue: 'medium',
    options: [
      { value: 'low',    label: 'Low' },
      { value: 'medium', label: 'Medium' },
      { value: 'high',   label: 'High' },
    ],
  },
  { key: 'due_date',     label: 'Due Date',    type: 'date' },
  { key: 'effort_hours', label: 'Effort (h)',  type: 'number', placeholder: 'e.g. 1.5' },
];

// ── Priority chip colours ─────────────────────────────────────────────────────

const PRIORITY_COLOUR: Record<string, string> = {
  high:   'var(--md-sys-color-error)',
  medium: '#b45309',   // amber-700 — warning tone
  low:    'var(--md-sys-color-on-surface-variant)',
};

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

    // Register both objects (upsert — safe to call multiple times)
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
    background:   'var(--md-sys-color-surface)',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    borderRadius: '12px',
    padding:      'var(--space-lg)',
    width:        '420px',
    maxWidth:     '90vw',
    display:      'flex',
    flexDirection:'column',
    gap:          'var(--space-md)',
  };

  const inputStyle: React.CSSProperties = {
    width:       '100%',
    padding:     'var(--space-xs) var(--space-sm)',
    borderRadius:'6px',
    border:      '1px solid var(--md-sys-color-outline-variant)',
    background:  'var(--md-sys-color-surface)',
    color:       'var(--md-sys-color-on-surface)',
    fontSize:    '0.95rem',
    boxSizing:   'border-box',
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
            className="btn-primary"
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
}: {
  taskId:  string;
  onDelete: (id: string) => void;
  onLink:   (id: string) => void;
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
            onClick={(e) => { e.stopPropagation(); setOpen(false); onLink(taskId); }}
          >
            Link
          </button>

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
            onClick={(e) => { e.stopPropagation(); setOpen(false); onDelete(taskId); }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ── TaskCard ──────────────────────────────────────────────────────────────────

function TaskCard({
  task,
  onOpen,
  onMarkComplete,
  onDelete,
  onLink,
}: {
  task:           TaskRow;
  onOpen:         (task: TaskRow) => void;
  onMarkComplete: (id: string) => void;
  onDelete:       (id: string) => void;
  onLink:         (id: string) => void;
}) {
  const labels = task.labels ?? [];

  const effortLabel =
    task.effort_hours != null ? `${task.effort_hours.toFixed(1)} h` : '—';

  const priorityColour = PRIORITY_COLOUR[task.priority] ?? 'var(--md-sys-color-on-surface-variant)';
  const priorityLabel  = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);

  const isDone = task.status === 'done';

  return (
    <div
      onClick={() => onOpen(task)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-sm)',
        padding: 'var(--space-sm) var(--space-md)',
        background: 'var(--md-sys-color-surface)',
        border: '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: '8px',
        cursor: 'pointer',
        minWidth: 0,
      }}
    >
      {/* Task name — flex:1, truncates */}
      <span
        className="type-body"
        style={{
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontWeight: isDone ? 400 : 500,
          textDecoration: isDone ? 'line-through' : 'none',
          color: isDone
            ? 'var(--md-sys-color-on-surface-variant)'
            : 'var(--md-sys-color-on-surface)',
        }}
      >
        {task.title}
      </span>

      {/* Label chips — all labels shown */}
      {labels.map(label => (
        <span
          key={label.id}
          className="type-label"
          style={{
            flexShrink: 0,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
            borderRadius: '12px',
            background: 'var(--md-sys-color-secondary-container)',
            color: 'var(--md-sys-color-on-secondary-container)',
            fontSize: '0.75rem',
            fontWeight: 500,
          }}
        >
          {label.name}
        </span>
      ))}

      {/* Effort chip — fixed width */}
      <span
        className="type-label"
        style={{
          flexShrink: 0,
          minWidth: '44px',
          textAlign: 'right',
          color: 'var(--md-sys-color-on-surface-variant)',
          fontSize: '0.8rem',
        }}
      >
        {effortLabel}
      </span>

      {/* Priority chip — fixed width */}
      <span
        className="type-label"
        style={{
          flexShrink: 0,
          minWidth: '52px',
          textAlign: 'center',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: priorityColour,
        }}
      >
        {priorityLabel}
      </span>

      {/* Mark Complete — primary action, always visible */}
      <button
        className="btn-outlined"
        disabled={isDone}
        onClick={(e) => { e.stopPropagation(); if (!isDone) onMarkComplete(task.id); }}
        style={{
          flexShrink: 0,
          fontSize: '0.8rem',
          padding: '3px 10px',
          opacity: isDone ? 0.45 : 1,
          cursor: isDone ? 'default' : 'pointer',
        }}
        title={isDone ? 'Already completed' : 'Mark complete'}
      >
        {isDone ? 'Done' : 'Complete'}
      </button>

      {/* Three-dots menu — secondary actions only */}
      <ThreeDotsMenu
        taskId={task.id}
        onDelete={onDelete}
        onLink={onLink}
      />
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
  const [title,        setTitle]        = useState(task.title ?? '');
  const [description,  setDescription]  = useState(task.description ?? '');
  const [status,       setStatus]       = useState(task.status ?? 'open');
  const [priority,     setPriority]     = useState(task.priority ?? 'medium');
  const [dueDate,      setDueDate]      = useState(task.due_date ?? '');
  const [effortHours,  setEffortHours]  = useState(
    task.effort_hours != null ? String(task.effort_hours) : ''
  );
  const [saving,       setSaving]       = useState(false);
  const [saveError,    setSaveError]    = useState<ApiError | null>(null);
  const [linkGroups,   setLinkGroups]   = useState<LinkGroup[]>([]);

  // Label state
  const [attachedLabels,   setAttachedLabels]   = useState<AttachedLabel[]>([]);
  const [labelQuery,       setLabelQuery]       = useState('');
  const [labelSuggestions, setLabelSuggestions] = useState<LabelRecord[]>([]);
  const [labelAttaching,   setLabelAttaching]   = useState(false);
  const labelDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    apiFetch<{ object_id: string; groups: LinkGroup[] }>(`/linking/objects/${task.id}/links`)
      .then(res => {
        if (!isApiError(res)) setLinkGroups((res as { groups: LinkGroup[] }).groups ?? []);
      });
  }, [task.id]);

  useEffect(() => {
    apiFetch<{ labels: AttachedLabel[] }>(`/tasks/${task.id}/labels`)
      .then(res => {
        if (!isApiError(res)) setAttachedLabels((res as { labels: AttachedLabel[] }).labels ?? []);
      });
  }, [task.id]);

  function handleLabelQueryChange(value: string) {
    setLabelQuery(value);
    if (labelDebounceRef.current) clearTimeout(labelDebounceRef.current);
    if (!value.trim()) { setLabelSuggestions([]); return; }
    labelDebounceRef.current = setTimeout(async () => {
      const res = await apiFetch<{ labels: LabelRecord[] }>(`/tasks/labels/search?q=${encodeURIComponent(value)}`);
      if (!isApiError(res)) setLabelSuggestions((res as { labels: LabelRecord[] }).labels ?? []);
    }, 200);
  }

  async function handleAttachLabel(labelName: string) {
    if (!labelName.trim() || labelAttaching) return;
    setLabelAttaching(true);
    const res = await apiFetch<AttachedLabel>(`/tasks/${task.id}/labels`, {
      method: 'POST',
      body: JSON.stringify({ label_name: labelName.trim() }),
    });
    setLabelAttaching(false);
    if (!isApiError(res)) {
      const attached = res as AttachedLabel;
      setAttachedLabels(prev =>
        prev.some(l => l.label_id === attached.label_id) ? prev : [...prev, attached]
      );
    }
    setLabelQuery('');
    setLabelSuggestions([]);
  }

  async function handleDetachLabel(labelId: string) {
    const res = await apiFetch<unknown>(`/tasks/${task.id}/labels/${labelId}`, { method: 'DELETE' });
    if (!isApiError(res)) {
      setAttachedLabels(prev => prev.filter(l => l.label_id !== labelId));
    }
  }

  async function handleSave() {
    if (!title.trim()) return;
    setSaving(true);
    setSaveError(null);

    // Always include effort_hours in the body so the backend model_fields_set
    // sees it and can clear the column when the field was explicitly emptied.
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
    width: '100%',
    padding: 'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border: '1px solid var(--md-sys-color-outline-variant)',
    background: 'var(--md-sys-color-surface)',
    color: 'var(--md-sys-color-on-surface)',
    fontSize: '0.95rem',
    boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '0.8rem',
    fontWeight: 600,
    color: 'var(--md-sys-color-on-surface-variant)',
    marginBottom: '4px',
  };

  const fieldStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  return (
    <div className="page">
      <div className="page-header" style={{ marginBottom: 'var(--space-md)' }}>
        <h1 className="type-display">Edit Task</h1>
      </div>

      {saveError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={saveError} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

        <div style={fieldStyle}>
          <label style={labelStyle}>Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={inputStyle}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: 'vertical' }}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={inputStyle}>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
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
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            style={inputStyle}
          />
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

          {/* Attached label chips */}
          {attachedLabels.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
              {attachedLabels.map(label => (
                <span
                  key={label.label_id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 10px',
                    borderRadius: '12px',
                    background: 'var(--md-sys-color-secondary-container)',
                    color: 'var(--md-sys-color-on-secondary-container)',
                    fontSize: '0.8rem',
                    fontWeight: 500,
                  }}
                >
                  {label.label_name}
                  <button
                    onClick={() => handleDetachLabel(label.label_id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '0',
                      lineHeight: 1,
                      color: 'var(--md-sys-color-on-secondary-container)',
                      fontSize: '0.75rem',
                    }}
                    title={`Remove label ${label.label_name}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Typeahead input */}
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
                      display:    'block',
                      width:      '100%',
                      textAlign:  'left',
                      padding:    'var(--space-xs) var(--space-sm)',
                      background: 'none',
                      border:     'none',
                      borderBottom: '1px solid var(--md-sys-color-outline-variant)',
                      cursor:     'pointer',
                      fontSize:   '0.9rem',
                      color:      'var(--md-sys-color-on-surface)',
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

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
          <button className="btn-primary" onClick={handleSave} disabled={saving || !title.trim()}>
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

// ── TaskGroupedList ───────────────────────────────────────────────────────────
// Groups tasks by their first label (primary label).
// Unlabeled tasks appear under "Unlabeled" at the end.
// Groups within named labels are sorted alphabetically.

function TaskGroupedList({
  tasks,
  onOpen,
  onMarkComplete,
  onDelete,
  onLink,
}: {
  tasks:          TaskRow[];
  onOpen:         (task: TaskRow) => void;
  onMarkComplete: (id: string) => void;
  onDelete:       (id: string) => void;
  onLink:         (id: string) => void;
}) {
  // Build groups: {labelName -> TaskRow[]}
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

  // Sort named groups alphabetically
  const sortedNames = Array.from(groupMap.keys()).sort((a, b) => a.localeCompare(b));

  const groups: { name: string; tasks: TaskRow[] }[] = [
    ...sortedNames.map(name => ({ name, tasks: groupMap.get(name)! })),
    ...(unlabeled.length > 0 ? [{ name: 'Unlabeled', tasks: unlabeled }] : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {groups.map(group => (
        <div key={group.name}>
          <p
            className="type-label"
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: 'var(--md-sys-color-on-surface-variant)',
              marginBottom: 'var(--space-xs)',
            }}
          >
            {group.name}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {group.tasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onOpen={onOpen}
                onMarkComplete={onMarkComplete}
                onDelete={onDelete}
                onLink={onLink}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


// ── TasksPage ─────────────────────────────────────────────────────────────────

function TasksPage() {
  const [tasks,        setTasks]        = useState<TaskRow[] | null>(null);
  const [isLoading,    setIsLoading]    = useState(true);
  const [error,        setError]        = useState<ApiError | null>(null);
  const [selected,     setSelected]     = useState<TaskRow | null>(null);
  const [creating,     setCreating]     = useState(false);
  const [actionError,  setActionError]  = useState<ApiError | null>(null);
  const [linkingTask,  setLinkingTask]  = useState<TaskRow | null>(null);

  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    const res = await apiFetch<{ meta: object; schema: object[]; rows: TaskRow[] }>('/tasks');
    setIsLoading(false);
    if (isApiError(res)) {
      setError(res);
    } else {
      const dataset = res as { rows: TaskRow[] };
      setTasks(dataset.rows ?? []);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleMarkComplete(id: string) {
    setActionError(null);
    const res = await apiFetch<{ rows: TaskRow[] }>(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'done' }),
    });
    if (isApiError(res)) {
      setActionError(res);
    } else {
      // Optimistic update — replace task in local state
      const updated = (res as { rows: TaskRow[] }).rows?.[0];
      if (updated) {
        setTasks((prev) => prev ? prev.map((t) => t.id === id ? updated : t) : prev);
      }
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

  async function handleCreate(data: Record<string, string>) {
    const body: Record<string, unknown> = { ...data };
    // Coerce effort_hours to float if present and non-empty
    if (typeof body.effort_hours === 'string') {
      body.effort_hours = body.effort_hours.trim() === '' ? null : parseFloat(body.effort_hours as string);
    }
    const res = await apiFetch<unknown>('/tasks', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (isApiError(res)) return res;
    setCreating(false);
    fetchTasks();
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Tasks</h1>
        </div>
        <Skeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Tasks</h1>
        </div>
        <ErrorCard error={error} />
      </div>
    );
  }

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
      <div className="page">
        <CreateForm
          title="New Task"
          fields={TASK_FIELDS}
          submitLabel="Create"
          onCancel={() => setCreating(false)}
          onSubmit={handleCreate}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="type-display">Tasks</h1>
        <button className="btn-primary" onClick={() => setCreating(true)}>
          New Task
        </button>
      </div>

      {actionError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={actionError} />
        </div>
      )}

      {tasks === null || tasks.length === 0 ? (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No tasks yet. Create one to get started.
        </p>
      ) : (
        <TaskGroupedList
          tasks={tasks}
          onOpen={setSelected}
          onMarkComplete={handleMarkComplete}
          onDelete={handleDelete}
          onLink={handleLink}
        />
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
