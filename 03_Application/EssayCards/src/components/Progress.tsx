import React, { useState } from 'react';
import type { EssayRow, EssayState, SectionProgressRow, SectionState } from '../types';

// ── Learning-level badge (Sprint12_FSRSAndUXOverhaul) ───────────────────────
//
// Compact 0-4 level with a tooltip/accessible explanation of the four
// milestones and their current true/false state. Keyboard/touch-reachable
// via a native <button> with title (hover/focus tooltip) and aria-label
// (always-available accessible explanation, not hover-only).

// ── Progress traffic lights (Sprint14) ──────────────────────────────────────
//
// States are derived server-side (backend/progress.py) — the frontend only
// maps a state key to a color and a text label. The draft's color NAMES are the
// canonical keys. UI_DesignLanguage.md defines no yellow/green token (status
// colors are not part of the M3 set), so yellow/green are literal status
// colors; grey/blue/violet reuse the neutral/primary/tertiary tokens.
// State is never conveyed by color alone: every dot is a native button with a
// title + aria-label naming the state, grey is a hollow ring, and the legend
// lists the names.

export const TRAFFIC_COLORS: Record<EssayState, string> = {
  grey: 'var(--md-sys-color-outline)',
  yellow: '#E0AE1F',
  green: '#3F9A52',
  blue: 'var(--md-sys-color-primary)',
  violet: 'var(--md-sys-color-tertiary)',
};

export const SECTION_STATE_LABELS: Record<SectionState, { name: string; meaning: string }> = {
  grey: { name: 'Not started', meaning: 'Flashcards are locked' },
  yellow: { name: 'Guided oral passed', meaning: 'Flashcards unlocked' },
  green: { name: 'Flashcards established', meaning: 'Every card has an interval of 24h or more' },
  blue: { name: 'Unguided oral passed', meaning: 'Independent reconstruction of the section' },
};

export const ESSAY_STATE_LABELS: Record<EssayState, { name: string; meaning: string }> = {
  grey: { name: 'Not started', meaning: 'No essay-level progress yet' },
  yellow: { name: 'Guided essay oral passed', meaning: 'Understands the essay as a whole, with support' },
  green: { name: 'All cards learned', meaning: 'Every card has an interval of 30 days or more' },
  blue: { name: 'All sections independently mastered', meaning: 'Every section passed its unguided oral' },
  violet: { name: 'Unguided essay oral passed', meaning: 'Highest mastery: the whole essay without guidance' },
};

export const NEXT_STEP_LABELS: Record<string, string> = {
  // section ladder
  guided_oral: 'Pass the guided oral for this section',
  flashcards_established: 'Get every flashcard to an interval of 24h or more',
  unguided_oral: 'Pass the unguided oral for this section',
  // essay ladder
  guided_essay_oral: 'Pass the guided oral for the whole essay',
  cards_learned: 'Get every flashcard to an interval of 30 days or more',
  section_unguided_orals: 'Pass the unguided oral for every section',
  unguided_essay_oral: 'Pass the unguided oral for the whole essay',
};

// One dot: native button (keyboard reachable), title for hover, and a small
// caption that opens on click/tap/focus-activate. Click never bubbles, so a dot
// inside a clickable essay row does not also navigate.
export function ProgressDot({ color, size, label, detail }: {
  color: string;
  size: number;
  label: string;
  detail: string;
}) {
  const [open, setOpen] = useState(false);
  const hollow = color === TRAFFIC_COLORS.grey;
  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        type="button"
        title={`${label}\n${detail}`}
        aria-label={`${label}. ${detail}`}
        aria-expanded={open}
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
        onBlur={() => setOpen(false)}
        style={{
          width: size, height: size, padding: 0, borderRadius: '50%', cursor: 'pointer',
          border: `2px solid ${color}`, background: hollow ? 'transparent' : color,
        }}
      />
      {open && (
        <span
          role="status"
          style={{
            position: 'absolute', top: size + 6, left: 0, zIndex: 20, minWidth: 180, maxWidth: 260,
            padding: '6px 8px', borderRadius: 6, fontSize: 12, whiteSpace: 'pre-line',
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

export function EssayProgressDot({ essay, size = 20 }: { essay: EssayRow; size?: number }) {
  const st = ESSAY_STATE_LABELS[essay.essay_state];
  const next = essay.essay_next_step ? `Next: ${NEXT_STEP_LABELS[essay.essay_next_step]}` : 'Highest state reached';
  return (
    <ProgressDot
      color={TRAFFIC_COLORS[essay.essay_state]}
      size={size}
      label={`Essay: ${st.name}`}
      detail={`${essay.title}\n${next}`}
    />
  );
}

export function SectionProgressDots({ sections }: { sections: SectionProgressRow[] }) {
  const ordered = [...sections].sort((a, b) => a.order_index - b.order_index);
  return (
    <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
      {ordered.map(sec => {
        const st = SECTION_STATE_LABELS[sec.state];
        const next = sec.next_step ? `Next: ${NEXT_STEP_LABELS[sec.next_step]}` : 'Highest state reached';
        return (
          <ProgressDot
            key={sec.section_id}
            color={TRAFFIC_COLORS[sec.state]}
            size={12}
            label={`Section: ${st.name}`}
            detail={`${sec.heading}\n${next}`}
          />
        );
      })}
    </span>
  );
}

export function ProgressLegend() {
  const row = (color: string, name: string, meaning: string) => (
    <li key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0' }}>
      <span
        aria-hidden="true"
        style={{
          width: 12, height: 12, borderRadius: '50%', flexShrink: 0, border: `2px solid ${color}`,
          background: color === TRAFFIC_COLORS.grey ? 'transparent' : color,
        }}
      />
      <span><strong>{name}</strong> — {meaning}</span>
    </li>
  );
  return (
    <details style={{ marginBottom: 12, fontSize: 13 }}>
      <summary style={{ cursor: 'pointer' }}>Legend</summary>
      <div style={{ marginTop: 6 }}>
        <div style={{ fontWeight: 600 }}>Section (small dots)</div>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {row(TRAFFIC_COLORS.grey, 'Grey', 'Not started')}
          {row(TRAFFIC_COLORS.yellow, 'Yellow', 'Guided oral passed / flashcards unlocked')}
          {row(TRAFFIC_COLORS.green, 'Green', 'Flashcards established')}
          {row(TRAFFIC_COLORS.blue, 'Blue', 'Unguided oral passed')}
        </ul>
        <div style={{ fontWeight: 600, marginTop: 8 }}>Essay (large dot)</div>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {row(TRAFFIC_COLORS.grey, 'Grey', 'Not started')}
          {row(TRAFFIC_COLORS.yellow, 'Yellow', 'Guided essay oral passed')}
          {row(TRAFFIC_COLORS.green, 'Green', 'All cards learned')}
          {row(TRAFFIC_COLORS.blue, 'Blue', 'All sections independently mastered')}
          {row(TRAFFIC_COLORS.violet, 'Violet', 'Unguided essay oral passed')}
        </ul>
      </div>
    </details>
  );
}
