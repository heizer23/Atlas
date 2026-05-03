/**
 * PersonalDevelopment — UnitDetailPage
 *
 * Detail view for a single training_unit task.
 * Shows:
 *  - Unit title, status, priority, labels
 *  - Potential subtasks parsed from description (unchecked/activated)
 *  - Child training_session tasks with inline duration editing
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { TrainingUnitRow, ChildTaskRow, UncheckedSubtask, ActivatedSubtask } from './types';
import { parseSubtasks, activateSubtaskLine } from './markdownSubtasks';

// ── PotentialSubtaskList ───────────────────────────────────────────────────────

function PotentialSubtaskList({
  unchecked,
  activated,
  onActivate,
  activating,
}: {
  unchecked:  UncheckedSubtask[];
  activated:  ActivatedSubtask[];
  onActivate: (lineText: string) => Promise<void>;
  activating: string | null;
}) {
  if (unchecked.length === 0 && activated.length === 0) {
    return (
      <p style={{ fontSize: '0.875rem', color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
        No potential subtasks defined. Add a "## Potential Subtasks" section to the description.
      </p>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {activated.map((item) => (
        <div
          key={item.taskId}
          style={{
            display:      'flex',
            alignItems:   'center',
            gap:          'var(--space-sm)',
            padding:      'var(--space-xs) var(--space-sm)',
            background:   'var(--md-sys-color-surface-variant)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: 'var(--md-sys-color-primary)', fontSize: '1rem' }}>✓</span>
          <span style={{
            flex:           1,
            fontSize:       '0.9rem',
            textDecoration: 'line-through',
            color:          'var(--md-sys-color-on-surface-variant)',
          }}>
            {item.lineText}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
            task created
          </span>
        </div>
      ))}

      {unchecked.map((item) => (
        <div
          key={item.lineText}
          style={{
            display:      'flex',
            alignItems:   'center',
            gap:          'var(--space-sm)',
            padding:      'var(--space-xs) var(--space-sm)',
            background:   'var(--md-sys-color-surface)',
            border:       '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: 'var(--md-sys-color-outline)', fontSize: '1rem' }}>☐</span>
          <span style={{ flex: 1, fontSize: '0.9rem', color: 'var(--md-sys-color-on-surface)' }}>
            {item.lineText}
          </span>
          {activating === item.lineText ? (
            <span style={{ fontSize: '0.8rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
              Creating…
            </span>
          ) : (
            <button
              className="btn-outlined"
              style={{ fontSize: '0.8rem', padding: '3px 10px' }}
              onClick={() => onActivate(item.lineText)}
            >
              Create task
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// ── ChildTaskList ─────────────────────────────────────────────────────────────

function ChildTaskList({
  tasks,
  onDurationChange,
}: {
  tasks:            ChildTaskRow[];
  onDurationChange: (taskId: string, minutes: number | null) => Promise<void>;
}) {
  const [editing, setEditing]   = useState<Record<string, string>>({});
  const [saving,  setSaving]    = useState<string | null>(null);

  if (tasks.length === 0) {
    return (
      <p style={{ fontSize: '0.875rem', color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>
        No active sessions yet. Activate a potential subtask to create one.
      </p>
    );
  }

  function handleDurationInput(taskId: string, value: string) {
    setEditing((prev) => ({ ...prev, [taskId]: value }));
  }

  async function handleDurationBlur(task: ChildTaskRow) {
    const raw = editing[task.id];
    if (raw === undefined) return; // not edited

    const parsed = raw.trim() === '' ? null : parseInt(raw, 10);
    if (parsed !== null && (isNaN(parsed) || parsed < 0)) return; // invalid — do nothing

    // Only save if value actually changed
    const current = task.actual_duration_minutes;
    if (parsed === current) {
      setEditing((prev) => { const n = { ...prev }; delete n[task.id]; return n; });
      return;
    }

    setSaving(task.id);
    await onDurationChange(task.id, parsed);
    setSaving(null);
    setEditing((prev) => { const n = { ...prev }; delete n[task.id]; return n; });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {tasks.map((task) => {
        const isDone        = task.status === 'done';
        const editingValue  = editing[task.id];
        const displayValue  = editingValue !== undefined
          ? editingValue
          : (task.actual_duration_minutes != null ? String(task.actual_duration_minutes) : '');

        return (
          <div
            key={task.id}
            style={{
              display:      'flex',
              alignItems:   'center',
              gap:          'var(--space-sm)',
              padding:      'var(--space-xs) var(--space-sm)',
              background:   'var(--md-sys-color-surface)',
              border:       '1px solid var(--md-sys-color-outline-variant)',
              borderRadius: '6px',
            }}
          >
            {/* Status indicator */}
            <span style={{
              fontSize:   '0.75rem',
              fontWeight: 600,
              padding:    '2px 6px',
              borderRadius: '8px',
              background: isDone
                ? 'var(--md-sys-color-primary-container)'
                : 'var(--md-sys-color-surface-variant)',
              color: isDone
                ? 'var(--md-sys-color-on-primary-container)'
                : 'var(--md-sys-color-on-surface-variant)',
              flexShrink: 0,
            }}>
              {task.status.replace('_', ' ')}
            </span>

            {/* Title */}
            <span style={{
              flex:           1,
              fontSize:       '0.9rem',
              color:          isDone
                ? 'var(--md-sys-color-on-surface-variant)'
                : 'var(--md-sys-color-on-surface)',
              textDecoration: isDone ? 'line-through' : 'none',
              overflow:       'hidden',
              textOverflow:   'ellipsis',
              whiteSpace:     'nowrap',
            }}>
              {task.title}
            </span>

            {/* Duration input */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
              <input
                type="number"
                min={0}
                value={displayValue}
                onChange={(e) => handleDurationInput(task.id, e.target.value)}
                onBlur={() => handleDurationBlur(task)}
                placeholder="min"
                disabled={saving === task.id}
                style={{
                  width:        '60px',
                  padding:      '2px 6px',
                  borderRadius: '4px',
                  border:       '1px solid var(--md-sys-color-outline-variant)',
                  background:   'var(--md-sys-color-surface)',
                  color:        'var(--md-sys-color-on-surface)',
                  fontSize:     '0.85rem',
                  textAlign:    'right',
                }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
                {saving === task.id ? '…' : 'min'}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── UnitDetailPage ────────────────────────────────────────────────────────────

export default function UnitDetailPage() {
  const { unitId }    = useParams<{ unitId: string }>();
  const navigate      = useNavigate();

  const [unit,          setUnit]          = useState<TrainingUnitRow | null>(null);
  const [children,      setChildren]      = useState<ChildTaskRow[]>([]);
  const [isLoading,     setIsLoading]     = useState(true);
  const [error,         setError]         = useState<ApiError | null>(null);
  const [activating,    setActivating]    = useState<string | null>(null);
  const [activateError, setActivateError] = useState<string | null>(null);

  const loadUnit = useCallback(async () => {
    if (!unitId) return;

    setIsLoading(true);
    setError(null);

    // Fetch training unit list and find the one we want
    const unitsRes = await apiFetch<{ rows: TrainingUnitRow[] }>('/tasks/training-units');
    if (isApiError(unitsRes)) {
      setError(unitsRes);
      setIsLoading(false);
      return;
    }
    const units = (unitsRes as { rows: TrainingUnitRow[] }).rows ?? [];
    const found = units.find((u) => u.id === unitId) ?? null;
    setUnit(found);

    // Fetch child training_session tasks
    const childRes = await apiFetch<{ rows: ChildTaskRow[] }>(
      `/tasks?task_type=training_session&parent_task_id=${encodeURIComponent(unitId)}`,
    );
    if (!isApiError(childRes)) {
      setChildren((childRes as { rows: ChildTaskRow[] }).rows ?? []);
    }

    setIsLoading(false);
  }, [unitId]);

  useEffect(() => {
    loadUnit();
  }, [loadUnit]);

  async function handleActivate(lineText: string) {
    if (!unit || activating) return;
    setActivating(lineText);
    setActivateError(null);

    // 1. Create the training_session task
    const createRes = await apiFetch<{ rows: { id: string }[] }>('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title:          lineText,
        task_type:      'training_session',
        parent_task_id: unit.id,
        status:         'open',
        priority:       unit.priority,
      }),
    });

    if (isApiError(createRes)) {
      setActivateError('Failed to create task. Please try again.');
      setActivating(null);
      return;
    }

    const newTask = (createRes as { rows: { id: string }[] }).rows?.[0];

    // 2. Inherit labels from parent (fire-and-forget on failure, surfaced separately)
    if (newTask && unit.labels.length > 0) {
      await apiFetch(`/tasks/${newTask.id}/labels`, {
        method: 'PUT',
        body: JSON.stringify({ labels: unit.labels.map((l) => l.name) }),
      });
    }

    // 3. Update parent description to mark line as activated
    if (newTask && unit.description !== null) {
      const updatedDesc = activateSubtaskLine(unit.description ?? '', lineText, newTask.id);
      const patchRes = await apiFetch(`/tasks/${unit.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ description: updatedDesc }),
      });
      if (isApiError(patchRes)) {
        // Task created but description not updated — surface warning
        setActivateError(
          'Task created, but the description could not be updated. Reload to see the task.',
        );
      }
    }

    setActivating(null);
    // Reload to reflect changes
    await loadUnit();
  }

  async function handleDurationChange(taskId: string, minutes: number | null) {
    await apiFetch(`/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ actual_duration_minutes: minutes }),
    });
    // Update local state optimistically
    setChildren((prev) =>
      prev.map((t) =>
        t.id === taskId ? { ...t, actual_duration_minutes: minutes } : t,
      ),
    );
  }

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

  if (!unit) {
    return (
      <div className="page">
        <div className="page-toolbar">
          <button className="icon-btn" aria-label="Back" onClick={() => navigate('/learning')}>
            <span className="material-symbols-rounded">arrow_back</span>
          </button>
          <h1 className="type-headline">Unit not found</h1>
        </div>
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          This training unit could not be found.
        </p>
      </div>
    );
  }

  const { unchecked, activated } = parseSubtasks(unit.description);

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="icon-btn" aria-label="Back" onClick={() => navigate('/learning')}>
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <h1 className="type-headline" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {unit.title}
        </h1>
      </div>

      {/* Unit metadata */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', marginBottom: 'var(--space-md)' }}>
        <span style={{
          fontSize:     '0.8rem',
          fontWeight:   600,
          padding:      '3px 10px',
          borderRadius: '10px',
          background:   unit.status === 'done'
            ? 'var(--md-sys-color-primary-container)'
            : 'var(--md-sys-color-surface-variant)',
          color: unit.status === 'done'
            ? 'var(--md-sys-color-on-primary-container)'
            : 'var(--md-sys-color-on-surface-variant)',
        }}>
          {unit.status.replace('_', ' ')}
        </span>
        <span style={{
          fontSize:     '0.8rem',
          fontWeight:   600,
          padding:      '3px 10px',
          borderRadius: '10px',
          background:   'var(--md-sys-color-surface-variant)',
          color:        'var(--md-sys-color-on-surface-variant)',
        }}>
          {unit.priority} priority
        </span>
        {unit.labels.map((l) => (
          <span
            key={l.id}
            style={{
              fontSize:     '0.8rem',
              padding:      '3px 10px',
              borderRadius: '10px',
              background:   'var(--md-sys-color-secondary-container)',
              color:        'var(--md-sys-color-on-secondary-container)',
            }}
          >
            {l.name}
          </span>
        ))}
      </div>

      {/* Progress summary */}
      {unit.total_child_count > 0 && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
              Progress: {unit.completed_child_count} / {unit.total_child_count} sessions done
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
              {Math.round((unit.completed_child_count / unit.total_child_count) * 100)}%
            </span>
          </div>
          <div style={{ height: '8px', borderRadius: '4px', background: 'var(--md-sys-color-surface-variant)', overflow: 'hidden' }}>
            <div style={{
              height:     '100%',
              width:      `${Math.round((unit.completed_child_count / unit.total_child_count) * 100)}%`,
              background: 'var(--md-sys-color-tertiary)',
              borderRadius: '4px',
            }} />
          </div>
        </div>
      )}

      {/* Potential subtasks section */}
      <div style={{ marginBottom: 'var(--space-lg)' }}>
        <h2 className="type-display" style={{ fontSize: '1rem', marginBottom: 'var(--space-sm)' }}>
          Potential Subtasks
        </h2>

        {activateError && (
          <p style={{ fontSize: '0.875rem', color: 'var(--md-sys-color-error)', marginBottom: 'var(--space-sm)' }}>
            {activateError}
          </p>
        )}

        <PotentialSubtaskList
          unchecked={unchecked}
          activated={activated}
          onActivate={handleActivate}
          activating={activating}
        />
      </div>

      {/* Child tasks section */}
      <div>
        <h2 className="type-display" style={{ fontSize: '1rem', marginBottom: 'var(--space-sm)' }}>
          Sessions
        </h2>
        <ChildTaskList
          tasks={children}
          onDurationChange={handleDurationChange}
        />
      </div>
    </div>
  );
}
