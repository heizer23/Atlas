import React, { useState } from 'react';
import type { EssayRow, RecallStatus, SectionProgressRow } from '../types';

// ── Learning markers (Sprint16_RecallFSRS) ──────────────────────────────────
//
// One dot per section shows two INDEPENDENT dimensions:
//   fill = Understanding — the confirmed guided level (0-6)
//   ring = Recall        — unguided oral recall: none / solid (current) / dashed (due)
// Flashcard progress is deliberately not shown here (it lives in the Flashcards
// tab). The colour ramp is a calm impression of progress, not a per-level key;
// exact level and recall dates are in the dot's caption and the reader.
// State is never conveyed by colour alone: every marker is a native button with a
// title + aria-label stating level and recall status.

export const GUIDED_LEVEL_NAMES = [
  'Not started', 'Orientation', 'Comprehension', 'Connections', 'Application', 'Critical understanding', 'Independence',
];

// Level 0 is hollow (grey outline). 1 yellow -> 6 dark green.
export const LEVEL_FILL: string[] = [
  'transparent', '#E0AE1F', '#C2DA8A', '#93CB7C', '#5DB56A', '#2F9A4F', '#1B6B34',
];

const RING_COLOR = 'var(--md-sys-color-on-surface)';
const HOLLOW_OUTLINE = 'var(--md-sys-color-outline)';

export const RECALL_LABELS: Record<RecallStatus, string> = {
  not_established: 'Recall not established',
  current: 'Recall current',
  due: 'Recall due',
};

export const NEXT_STEP_LABELS: Record<string, string> = {
  guided_oral: 'Guided learning, Level 1 (unlocks flashcards)',
  recall_due: 'Oral recall is due',
  guided_next: 'Next guided level',
  unguided_recall: 'Establish oral recall (unguided)',
};

// SVG geometry: 20x20 box, dot r=6, ring r=8.5 (stroke 1.75). `size` scales the whole marker.
function MarkerSvg({ level, recall, size, ringOnly = false }: {
  level: number; recall: RecallStatus; size: number; ringOnly?: boolean;
}) {
  const hollow = level <= 0 || ringOnly;
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" style={{ display: 'block' }}>
      {!ringOnly && (
        <circle
          cx="10" cy="10" r="6"
          fill={hollow ? 'none' : LEVEL_FILL[Math.min(level, 6)]}
          stroke={hollow ? HOLLOW_OUTLINE : 'none'}
          strokeWidth="1.25"
        />
      )}
      {recall !== 'not_established' && (
        <circle
          cx="10" cy="10" r={ringOnly ? 8 : 8.5} fill="none" stroke={RING_COLOR} strokeWidth="1.75"
          strokeDasharray={recall === 'due' ? '3.2 2.6' : undefined}
          strokeLinecap="butt"
        />
      )}
    </svg>
  );
}

// Native button (keyboard reachable), title for hover, and a caption that opens on
// click/tap. Click never bubbles, so a marker inside a clickable essay row does not
// also navigate.
function Marker({ level, recall, size, label, detail, ringOnly = false }: {
  level: number; recall: RecallStatus; size: number; label: string; detail: string; ringOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        type="button"
        title={`${label}\n${detail}`}
        aria-label={`${label}. ${detail.replace(/\n/g, '. ')}`}
        aria-expanded={open}
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
        onBlur={() => setOpen(false)}
        style={{ padding: 0, border: 'none', background: 'none', cursor: 'pointer', lineHeight: 0 }}
      >
        <MarkerSvg level={level} recall={recall} size={size} ringOnly={ringOnly} />
      </button>
      {open && (
        <span
          role="status"
          style={{
            position: 'absolute', top: size + 4, left: 0, zIndex: 20, minWidth: 180, maxWidth: 260,
            padding: '6px 8px', borderRadius: 6, fontSize: 12, whiteSpace: 'pre-line', lineHeight: 1.35,
            background: 'var(--md-sys-color-surface)', color: 'var(--md-sys-color-on-surface)',
            border: '1px solid var(--md-sys-color-outline-variant)', boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          }}
        >
          {`${label}\n${detail}`}
        </span>
      )}
    </span>
  );
}

function shortDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '';
}

export function recallDetail(status: RecallStatus, nextDueAt: string | null): string {
  if (status === 'current' && nextDueAt) return `${RECALL_LABELS.current} (next review ${shortDate(nextDueAt)})`;
  if (status === 'due' && nextDueAt) return `${RECALL_LABELS.due} (since ${shortDate(nextDueAt)})`;
  return RECALL_LABELS[status];
}

export function SectionProgressDots({ sections }: { sections: SectionProgressRow[] }) {
  const ordered = [...sections].sort((a, b) => a.order_index - b.order_index);
  return (
    <span style={{ display: 'inline-flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
      {ordered.map(sec => {
        const next = sec.next_step
          ? `Next: ${NEXT_STEP_LABELS[sec.next_step]}${sec.next_step === 'guided_next' && sec.next_guided_level ? ` (Level ${sec.next_guided_level})` : ''}`
          : 'Fully developed';
        return (
          <Marker
            key={sec.section_id}
            level={sec.guided_level}
            recall={sec.recall_status}
            size={20}
            label={`Section: ${sec.heading}`}
            detail={`Guided Level ${sec.guided_level} of 6 — ${GUIDED_LEVEL_NAMES[sec.guided_level]}\n${recallDetail(sec.recall_status, sec.recall_next_due_at)}\n${next}`}
          />
        );
      })}
    </span>
  );
}

// Essay-level marker: ONLY the essay-scope recall ring. There is deliberately no
// essay "understanding" fill — sections have different levels and no single level
// would be honest. A fixed-width slot keeps rows aligned when no ring is shown.
export function EssayRecallMarker({ essay, size = 22 }: { essay: EssayRow; size?: number }) {
  const status = essay.essay_recall_status;
  return (
    <span style={{ display: 'inline-flex', width: size, height: size, flexShrink: 0 }}>
      {status !== 'not_established' && (
        <Marker
          level={0}
          recall={status}
          size={size}
          ringOnly
          label="Whole-essay recall"
          detail={`${essay.title}\n${recallDetail(status, essay.essay_recall_next_due_at)}`}
        />
      )}
    </span>
  );
}

// Aggregate bar (essay row + category card). Semantics are a FLOOR, never an average:
// fill = the lowest confirmed guided level among the essay's sections ("every section is
// at least this far"); a dashed outline = at least one recall review in it is due. Grey =
// some section not started (or no sections). No numbers; exact levels are in the dots.
export function LevelBar({ sections, recallDue, width = 6, height, label }: {
  sections: SectionProgressRow[]; recallDue: boolean; width?: number; height?: number; label: string;
}) {
  const floor = sections.length ? Math.min(...sections.map(s => s.guided_level)) : 0;
  return (
    <span
      role="img"
      aria-label={`${label}: every section at least Level ${floor}${recallDue ? '; recall due' : ''}`}
      title={`${label}\nEvery section at least Level ${floor} of 6${recallDue ? '\nRecall due' : ''}`}
      style={{
        display: 'inline-block', width, height: height ?? 'auto', alignSelf: 'stretch', borderRadius: width / 2, flexShrink: 0,
        background: floor > 0 ? LEVEL_FILL[floor] : 'var(--md-sys-color-outline-variant)',
        outline: recallDue ? `1.5px dashed ${RING_COLOR}` : 'none', outlineOffset: 1.5,
      }}
    />
  );
}

export function ProgressLegend() {
  const swatch = (level: number) => (
    <span key={level} style={{ display: 'inline-flex' }}><MarkerSvg level={level} recall="not_established" size={16} /></span>
  );
  const ring = (recall: RecallStatus, text: string) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <MarkerSvg level={3} recall={recall} size={16} /> {text}
    </span>
  );
  return (
    <details style={{ marginBottom: 12, fontSize: 13 }}>
      <summary style={{ cursor: 'pointer' }}>Legend</summary>
      <div style={{ marginTop: 6, display: 'grid', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <strong>Fill</strong> — understanding (guided level):
          {[0, 1, 2, 3, 4, 5, 6].map(swatch)}
          <span style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>not started → deep</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <strong>Bars</strong> — per essay: its weakest section's level; dashed outline = recall due.
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <strong>Ring</strong> — oral recall:
          {ring('not_established', 'none: not established')}
          {ring('current', 'solid: current')}
          {ring('due', 'dashed: due')}
        </div>
      </div>
    </details>
  );
}
