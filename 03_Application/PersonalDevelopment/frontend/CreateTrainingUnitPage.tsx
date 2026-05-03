/**
 * PersonalDevelopment — CreateTrainingUnitPage
 *
 * Form to create a new training_unit task.
 * Fields: title (required), description (with ## Potential Subtasks guidance),
 * priority, and labels.
 * On success: navigates to /learning.
 */

import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';

const SUBTASKS_TEMPLATE = '\n\n## Potential Subtasks\n- [ ] ';

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

export default function CreateTrainingUnitPage() {
  const navigate = useNavigate();

  const [title,         setTitle]         = useState('');
  const [description,   setDescription]   = useState('');
  const [priority,      setPriority]      = useState('medium');
  const [labelInput,    setLabelInput]    = useState('');
  const [labelList,     setLabelList]     = useState<string[]>([]);
  const [labelSugs,     setLabelSugs]     = useState<{ id: string; name: string }[]>([]);
  const [saving,        setSaving]        = useState(false);
  const [saveError,     setSaveError]     = useState<ApiError | null>(null);
  const labelDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleLabelInputChange(value: string) {
    setLabelInput(value);
    if (labelDebounceRef.current) clearTimeout(labelDebounceRef.current);
    if (!value.trim()) { setLabelSugs([]); return; }
    labelDebounceRef.current = setTimeout(async () => {
      const res = await apiFetch<{ rows: { id: string; name: string }[] }>(
        `/tasks/labels/search?q=${encodeURIComponent(value)}`,
      );
      if (!isApiError(res)) {
        setLabelSugs((res as { rows: { id: string; name: string }[] }).rows ?? []);
      }
    }, 200);
  }

  function addLabel(name: string) {
    const trimmed = name.trim();
    if (trimmed && !labelList.includes(trimmed)) {
      setLabelList((prev) => [...prev, trimmed]);
    }
    setLabelInput('');
    setLabelSugs([]);
  }

  function removeLabel(name: string) {
    setLabelList((prev) => prev.filter((l) => l !== name));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    setSaveError(null);

    const res = await apiFetch<{ rows: { id: string }[] }>('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title:       title.trim(),
        description: description.trim() || null,
        task_type:   'training_unit',
        status:      'open',
        priority,
      }),
    });

    if (isApiError(res)) {
      setSaving(false);
      setSaveError(res);
      return;
    }

    const newTask = (res as { rows: { id: string }[] }).rows?.[0];

    if (newTask && labelList.length > 0) {
      await apiFetch(`/tasks/${newTask.id}/labels`, {
        method: 'PUT',
        body: JSON.stringify({ labels: labelList }),
      });
    }

    setSaving(false);
    navigate('/learning');
  }

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="icon-btn" aria-label="Cancel" onClick={() => navigate('/learning')}>
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <h1 className="type-headline">New Training Unit</h1>
      </div>

      {saveError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={saveError} />
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

        <div style={fieldStyle}>
          <label style={labelStyle}>Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Learn Rust"
            style={inputStyle}
            autoFocus
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            placeholder={`Optional description.\n\nTo define potential subtasks, add:\n\n## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2`}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace' }}
          />
          {!description.includes('## Potential Subtasks') && (
            <button
              type="button"
              className="btn-outlined"
              style={{ alignSelf: 'flex-start', fontSize: '0.8rem', padding: '3px 10px' }}
              onClick={() => setDescription((prev) => prev + SUBTASKS_TEMPLATE)}
            >
              + Add Potential Subtasks section
            </button>
          )}
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} style={inputStyle}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        {/* Labels */}
        <div style={fieldStyle}>
          <label style={labelStyle}>Labels</label>

          {labelList.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
              {labelList.map((name) => (
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
                    type="button"
                    onClick={() => removeLabel(name)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1, color: 'inherit', fontSize: '0.75rem' }}
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
              value={labelInput}
              onChange={(e) => handleLabelInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (labelInput.trim()) addLabel(labelInput);
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
                maxHeight:    '160px',
                overflowY:    'auto',
              }}>
                {labelSugs.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => addLabel(s.name)}
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
            Press Enter to add a label, or select a suggestion.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
          <button type="submit" className="btn-filled" disabled={saving || !title.trim()}>
            {saving ? 'Creating…' : 'Create Training Unit'}
          </button>
          <button type="button" className="btn-outlined" onClick={() => navigate('/learning')} disabled={saving}>
            Cancel
          </button>
        </div>

      </form>
    </div>
  );
}
