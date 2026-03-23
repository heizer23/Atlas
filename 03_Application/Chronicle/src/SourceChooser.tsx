/**
 * SourceChooser — lists available (application, source_label) pairs.
 * Shows a checkmark for selected sources.
 * Calls onToggle when a source row is clicked.
 */

import type { SourceListRow } from './types';

interface Props {
  sources:  SourceListRow[];
  onToggle: (application: string, source_label: string, selected: boolean) => void;
}

export default function SourceChooser({ sources, onToggle }: Props) {
  if (sources.length === 0) {
    return (
      <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
        No sources available.
      </p>
    );
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {sources.map((s) => {
        const key = `${s.application}::${s.source_label}`;
        return (
          <li key={key}>
            <button
              onClick={() => onToggle(s.application, s.source_label, !s.selected)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                width: '100%',
                padding: 'var(--space-xs) var(--space-sm)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                borderRadius: '4px',
              }}
              className="type-body"
            >
              <span
                aria-hidden="true"
                style={{
                  width: '1.2em',
                  textAlign: 'center',
                  color: s.selected ? 'var(--md-sys-color-primary)' : 'transparent',
                  userSelect: 'none',
                }}
              >
                ✓
              </span>
              <span>
                <span style={{ fontWeight: 500 }}>{s.source_label}</span>
                <span
                  style={{
                    marginLeft: 'var(--space-xs)',
                    fontSize: '0.8em',
                    color: 'var(--md-sys-color-on-surface-variant)',
                  }}
                >
                  ({s.application})
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
