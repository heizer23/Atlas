import React from 'react';
import type { Grade } from './types';

// ── Shared styles ─────────────────────────────────────────────────────────────

export const pageStyle: React.CSSProperties = { padding: 16, maxWidth: 720, margin: '0 auto' };

export const btnStyle: React.CSSProperties = {
  padding: '0 16px',
  minHeight: 40,
  borderRadius: 'var(--radius-button, 20px)',
  border: '1px solid var(--md-sys-color-outline)',
  background: 'transparent',
  color: 'var(--md-sys-color-on-surface)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 14,
  fontWeight: 500,
};

export const primaryBtnStyle: React.CSSProperties = {
  ...btnStyle,
  background: 'var(--md-sys-color-primary)',
  color: 'var(--md-sys-color-on-primary)',
  borderColor: 'transparent',
};

// ── Review screen (Sprint05b redesign) — Material 3 surfaces / tokens ────────

export const reviewCardStyle: React.CSSProperties = {
  background: 'var(--md-sys-color-surface)',
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 'var(--radius-card, 12px)',
  padding: 24,
  margin: '16px 0',
  minHeight: 140,
  boxShadow: 'var(--elevation-1)',
  position: 'relative',
};

// Full-width primary action after reading the question (goal 1).
export const flipBtnStyle: React.CSSProperties = {
  width: '100%',
  height: 52,
  borderRadius: 'var(--radius-button, 20px)',
  border: 'none',
  background: 'var(--md-sys-color-primary)',
  color: 'var(--md-sys-color-on-primary)',
  fontFamily: 'inherit',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
  margin: '8px 0',
};

export const gradeBtnStyle: React.CSSProperties = {
  flex: 1,
  height: 52,
  borderRadius: 'var(--radius-button, 20px)',
  border: '1px solid var(--md-sys-color-outline)',
  background: 'var(--md-sys-color-surface)',
  color: 'var(--md-sys-color-on-surface)',
  fontFamily: 'inherit',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};

// Grade emphasis: Again reads as a failure (error tone), Good as the
// expected answer (primary tone), Hard/Easy stay neutral.
export const gradeBtnAgainStyle: React.CSSProperties = {
  ...gradeBtnStyle,
  borderColor: 'var(--md-sys-color-error)',
  color: 'var(--md-sys-color-error)',
};
export const gradeBtnGoodStyle: React.CSSProperties = {
  ...gradeBtnStyle,
  border: '1px solid transparent',
  background: 'var(--md-sys-color-primary)',
  color: 'var(--md-sys-color-on-primary)',
};
export function gradeStyleFor(g: Grade): React.CSSProperties {
  return g === 'again' ? gradeBtnAgainStyle : g === 'good' ? gradeBtnGoodStyle : gradeBtnStyle;
}

export const jumpBtnStyle: React.CSSProperties = {
  ...btnStyle,
  marginTop: 8,
  border: 'none',
  background: 'transparent',
  color: 'var(--md-sys-color-primary)',
  padding: '0 4px',
  minHeight: 44,
  fontSize: 14,
};

// Rendered once by the root component. Keeps a Markdown image inside the
// reading column / review card from overflowing. CSS-only per
// Sprint03_Images/10_architecture.json — no custom img component.
export const ESSAYCARDS_IMG_CSS =
  '.essaycards-section-body img, .essaycards-review-card img { max-width: 100%; height: auto; }' +
  // Reading column: 16px body, relaxed leading, ~68ch measure.
  ' .essaycards-section-body { font-size: 16px; line-height: 1.65; }' +
  ' .essaycards-section-body p { max-width: 68ch; margin: 0 0 1em; }' +
  ' .essaycards-section-body :is(a, span)[role="button"], .essaycards-section-body a { text-underline-offset: 3px; }';

export const studyBtnStyle: React.CSSProperties = {
  ...btnStyle,
  padding: '0 14px',
  fontSize: 14,
  flexShrink: 0,
  whiteSpace: 'nowrap',
};
