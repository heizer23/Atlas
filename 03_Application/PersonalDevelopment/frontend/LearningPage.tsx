/**
 * PersonalDevelopment — LearningPage
 *
 * Main list view for training units. Fetches GET /tasks/training-units and
 * renders a card per unit with title, labels, priority, progress bar, and
 * last activity date. Rows are already sorted server-side.
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { TrainingUnitRow } from './types';

// ── Priority chip ─────────────────────────────────────────────────────────────

const PRIORITY_COLOUR: Record<string, string> = {
  high:   'var(--md-sys-color-error)',
  medium: '#b45309',
  low:    'var(--md-sys-color-on-surface-variant)',
};

// ── TrainingUnitCard ──────────────────────────────────────────────────────────

function TrainingUnitCard({
  unit,
  onClick,
}: {
  unit: TrainingUnitRow;
  onClick: () => void;
}) {
  const total     = unit.total_child_count ?? 0;
  const completed = unit.completed_child_count ?? 0;
  const progress  = total === 0 ? 0 : Math.round((completed / total) * 100);
  const isDone    = unit.status === 'done';

  const lastActivity = unit.last_child_completed_at
    ? new Date(unit.last_child_completed_at).toLocaleDateString()
    : null;

  const priorityColour = PRIORITY_COLOUR[unit.priority] ?? 'var(--md-sys-color-on-surface-variant)';

  return (
    <div
      onClick={onClick}
      style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           'var(--space-xs)',
        padding:       'var(--space-md)',
        background:    'var(--md-sys-color-surface)',
        border:        '1px solid var(--md-sys-color-outline-variant)',
        borderRadius:  '10px',
        cursor:        'pointer',
      }}
    >
      {/* Title row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <span
          className="type-body"
          style={{
            flex:           1,
            fontWeight:     500,
            textDecoration: isDone ? 'line-through' : 'none',
            color:          isDone
              ? 'var(--md-sys-color-on-surface-variant)'
              : 'var(--md-sys-color-on-surface)',
            overflow:       'hidden',
            textOverflow:   'ellipsis',
            whiteSpace:     'nowrap',
          }}
        >
          {unit.title}
        </span>

        {/* Status badge */}
        <span
          style={{
            fontSize:     '0.75rem',
            fontWeight:   600,
            padding:      '2px 8px',
            borderRadius: '10px',
            background:   isDone
              ? 'var(--md-sys-color-primary-container)'
              : 'var(--md-sys-color-surface-variant)',
            color: isDone
              ? 'var(--md-sys-color-on-primary-container)'
              : 'var(--md-sys-color-on-surface-variant)',
          }}
        >
          {unit.status.replace('_', ' ')}
        </span>

        {/* Priority */}
        <span
          style={{
            fontSize:   '0.8rem',
            fontWeight: 600,
            color:      priorityColour,
            flexShrink: 0,
          }}
          title={unit.priority}
        >
          {unit.priority === 'high' ? '↑' : unit.priority === 'low' ? '↓' : '–'}
        </span>
      </div>

      {/* Labels */}
      {unit.labels && unit.labels.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {unit.labels.map((l) => (
            <span
              key={l.id}
              style={{
                fontSize:     '0.75rem',
                padding:      '2px 8px',
                borderRadius: '10px',
                background:   'var(--md-sys-color-secondary-container)',
                color:        'var(--md-sys-color-on-secondary-container)',
              }}
            >
              {l.name}
            </span>
          ))}
        </div>
      )}

      {/* Progress bar */}
      {total > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
              {completed} / {total} sessions
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
              {progress}%
            </span>
          </div>
          <div
            style={{
              height:       '6px',
              borderRadius: '3px',
              background:   'var(--md-sys-color-surface-variant)',
              overflow:     'hidden',
            }}
          >
            <div
              style={{
                height:     '100%',
                width:      `${progress}%`,
                background: isDone
                  ? 'var(--md-sys-color-primary)'
                  : 'var(--md-sys-color-tertiary)',
                borderRadius: '3px',
                transition:   'width 0.3s ease',
              }}
            />
          </div>
        </div>
      )}

      {/* Last activity */}
      {lastActivity && (
        <span style={{ fontSize: '0.75rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
          Last activity: {lastActivity}
        </span>
      )}
    </div>
  );
}

// ── LearningPage ──────────────────────────────────────────────────────────────

export default function LearningPage() {
  const navigate = useNavigate();
  const [units,     setUnits]     = useState<TrainingUnitRow[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState<ApiError | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      const res = await apiFetch<{ rows: TrainingUnitRow[] }>('/tasks/training-units');
      setIsLoading(false);
      if (isApiError(res)) {
        setError(res);
      } else {
        setUnits((res as { rows: TrainingUnitRow[] }).rows ?? []);
      }
    }
    load();
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <button
          className="icon-btn filled"
          aria-label="New training unit"
          onClick={() => navigate('/learning/new')}
        >
          <span className="material-symbols-rounded">add</span>
        </button>
      </div>

      {isLoading ? (
        <Skeleton />
      ) : error ? (
        <ErrorCard error={error} />
      ) : units && units.length === 0 ? (
        <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
          No training units yet. Create one to get started.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {(units ?? []).map((unit) => (
            <TrainingUnitCard
              key={unit.id}
              unit={unit}
              onClick={() => navigate(`/learning/${unit.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
