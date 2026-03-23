/**
 * SourceChooser — grouped, collapsible source selector.
 *
 * Groups sources by the `application` field, preserving the SQL-defined order
 * returned by GET /calendar/sources. No client-side re-sorting.
 *
 * Groups are collapsed by default. Expand/collapse is local UI state — no
 * persistence and no API call.
 *
 * Each source row shows a checkbox-style indicator for selected state.
 * Clicking a source row calls onToggle with !selected.
 *
 * If selectedCount >= maxSelected and a source is not currently selected,
 * that row is visually disabled and non-interactive.
 *
 * No group-level selection (checking an entire group at once).
 */

import { useState } from 'react';
import type { SourceListRow } from './types';

// ── Public props contract ──────────────────────────────────────────────────────

export interface SourceChooserProps {
  sources:       SourceListRow[];
  onToggle:      (application: string, source_label: string, selected: boolean) => void;
  selectedCount: number;
  maxSelected:   number;
}

// ── Private types ──────────────────────────────────────────────────────────────

interface SourceGroup {
  application: string;
  sources:     SourceListRow[];
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function SourceChooser({
  sources,
  onToggle,
  selectedCount,
  maxSelected,
}: SourceChooserProps) {
  // Each group is identified by application name. All groups start collapsed.
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  if (sources.length === 0) {
    return (
      <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
        No sources available.
      </p>
    );
  }

  // Group sources by application, preserving SQL-defined order.
  // We use a Map (insertion-ordered) to maintain the first-seen application order.
  const groupMap = new Map<string, SourceListRow[]>();
  for (const src of sources) {
    if (!groupMap.has(src.application)) {
      groupMap.set(src.application, []);
    }
    groupMap.get(src.application)!.push(src);
  }

  const groups: SourceGroup[] = Array.from(groupMap.entries()).map(([application, srcs]) => ({
    application,
    sources: srcs,
  }));

  function toggleGroup(application: string) {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(application)) {
        next.delete(application);
      } else {
        next.add(application);
      }
      return next;
    });
  }

  const atLimit = selectedCount >= maxSelected;

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {groups.map((group) => {
        const isExpanded = expandedGroups.has(group.application);
        return (
          <li key={group.application}>
            {/* Group header — expand/collapse trigger */}
            <button
              onClick={() => toggleGroup(group.application)}
              style={{
                display:        'flex',
                alignItems:     'center',
                gap:            'var(--space-xs)',
                width:          '100%',
                padding:        'var(--space-xs) var(--space-sm)',
                background:     'none',
                border:         'none',
                cursor:         'pointer',
                textAlign:      'left',
                borderRadius:   4,
                fontWeight:     600,
              }}
              className="type-body"
              aria-expanded={isExpanded}
            >
              {/* Expand/collapse indicator — distinct from source checkbox */}
              <span
                aria-hidden="true"
                style={{
                  display:     'inline-block',
                  width:       '0.7em',
                  fontSize:    '0.7em',
                  transform:   isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition:  'transform 0.15s',
                  userSelect:  'none',
                  flexShrink:  0,
                }}
              >
                ▶
              </span>
              <span>{group.application}</span>
            </button>

            {/* Source rows — only visible when group is expanded */}
            {isExpanded && (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {group.sources.map((src) => {
                  const srcKey  = `${src.application}::${src.source_label}`;
                  const blocked = atLimit && !src.selected;

                  return (
                    <li key={srcKey}>
                      <button
                        onClick={() => {
                          if (blocked) return;
                          onToggle(src.application, src.source_label, !src.selected);
                        }}
                        disabled={blocked}
                        style={{
                          display:      'flex',
                          alignItems:   'center',
                          gap:          'var(--space-sm)',
                          width:        '100%',
                          padding:      'var(--space-xs) var(--space-sm)',
                          paddingLeft:  'calc(var(--space-sm) + 1.2em)',
                          background:   'none',
                          border:       'none',
                          cursor:       blocked ? 'not-allowed' : 'pointer',
                          textAlign:    'left',
                          borderRadius: 4,
                          opacity:      blocked ? 0.4 : 1,
                        }}
                        className="type-body"
                        aria-checked={src.selected}
                        role="checkbox"
                      >
                        {/* Checkbox-style selected indicator */}
                        <span
                          aria-hidden="true"
                          style={{
                            width:      '1.2em',
                            textAlign:  'center',
                            color:      src.selected
                              ? 'var(--md-sys-color-primary)'
                              : 'var(--md-sys-color-outline)',
                            fontWeight: src.selected ? 700 : 400,
                            userSelect: 'none',
                            flexShrink: 0,
                          }}
                        >
                          {src.selected ? '✓' : '○'}
                        </span>
                        <span style={{ fontWeight: 500 }}>{src.source_label}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
