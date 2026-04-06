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

interface TaskRow extends Row {
  id:           string;
  title:        string;
  description?: string;
  status:       string;
  priority:     string;
  due_date?:    string;
  effort_hours?: number | null;
  created_at?:  string;
}

// ── Form field definitions ────────────────────────────────────────────────────

const TASK_FIELDS: FormField[] = [
  { key: 'title',        label: 'Title',       type: 'string', required: true, placeholder: 'Task title' },
  { key: 'description',  label: 'Description', type: 'string' },
  { key: 'priority',     label: 'Priority',    type: 'enum',   required: true,
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

// ── ThreeDotsMenu ─────────────────────────────────────────────────────────────

function ThreeDotsMenu({
  taskId,
  onMarkComplete,
  onDelete,
}: {
  taskId:         string;
  onMarkComplete: (id: string) => void;
  onDelete:       (id: string) => void;
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
            onClick={(e) => { e.stopPropagation(); setOpen(false); onMarkComplete(taskId); }}
          >
            Mark complete
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
}: {
  task:           TaskRow;
  onOpen:         (task: TaskRow) => void;
  onMarkComplete: (id: string) => void;
  onDelete:       (id: string) => void;
}) {
  const effortLabel =
    task.effort_hours != null ? `${task.effort_hours.toFixed(1)} h` : '—';

  const priorityColour = PRIORITY_COLOUR[task.priority] ?? 'var(--md-sys-color-on-surface-variant)';
  const priorityLabel  = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);

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
          fontWeight: task.status === 'done' ? 400 : 500,
          textDecoration: task.status === 'done' ? 'line-through' : 'none',
          color: task.status === 'done'
            ? 'var(--md-sys-color-on-surface-variant)'
            : 'var(--md-sys-color-on-surface)',
        }}
      >
        {task.title}
      </span>

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

      {/* Three-dots menu — never truncates */}
      <ThreeDotsMenu
        taskId={task.id}
        onMarkComplete={onMarkComplete}
        onDelete={onDelete}
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

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
          <button className="btn-primary" onClick={handleSave} disabled={saving || !title.trim()}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button className="btn-outlined" onClick={onBack} disabled={saving}>
            Cancel
          </button>
        </div>

      </div>
    </div>
  );
}

// ── TasksPage ─────────────────────────────────────────────────────────────────

function TasksPage() {
  const [tasks,       setTasks]       = useState<TaskRow[] | null>(null);
  const [isLoading,   setIsLoading]   = useState(true);
  const [error,       setError]       = useState<ApiError | null>(null);
  const [selected,    setSelected]    = useState<TaskRow | null>(null);
  const [creating,    setCreating]    = useState(false);
  const [actionError, setActionError] = useState<ApiError | null>(null);

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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onOpen={setSelected}
              onMarkComplete={handleMarkComplete}
              onDelete={handleDelete}
            />
          ))}
        </div>
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
