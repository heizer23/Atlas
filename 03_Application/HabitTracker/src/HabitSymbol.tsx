/**
 * HabitSymbol — the four-layer daily ornament (reusable, no app dependencies; Launcher-ready).
 *
 *   body         outer ring
 *   mind         diamond inscribed in the ring
 *   organization circle inside the diamond
 *   discipline   centre dot
 *
 * Geometry is fixed (HABIT_SYMBOL_GEOMETRY): level only changes opacity, never size/stroke/shape.
 * A hidden layer is simply not drawn — the other layers keep their exact size and position.
 * Layers are keyed by stable layer ids (categories.symbol_layer), never by display name.
 */

import React from 'react';

export type SymbolLayer = 'body' | 'mind' | 'organization' | 'discipline';
export type SymbolLevel = 0 | 1 | 2 | 3;

export const SYMBOL_LAYERS: SymbolLayer[] = ['body', 'mind', 'organization', 'discipline'];

// ── Centralised visual parameters ─────────────────────────────────────────────

/** Level -> opacity. Visual parameters only, no business logic. */
export const HABIT_SYMBOL_OPACITY: Record<SymbolLevel, number> = { 0: 0.12, 1: 0.4, 2: 0.7, 3: 1 };

export const HABIT_SYMBOL_COLOR = '#B5CC9C';        // muted sage
export const HABIT_SYMBOL_FAINT_COLOR = '#8E97A3';  // neutral for level 0 outlines

/** viewBox 0 0 48 48, shared centre (24, 24). */
export const HABIT_SYMBOL_GEOMETRY = {
  box: 48,
  c: 24,
  stroke: 1.8,
  bodyR: 21,          // outer ring
  mindR: 17.5,        // diamond vertex distance from centre (approaches the ring)
  organizationR: 7.5, // inner circle (diamond inradius is ~12.4, so it sits inside)
  disciplineR: 2.8,   // centre dot
} as const;

export type SymbolLevels = Partial<Record<SymbolLayer, number | null | undefined>>;

function clampLevel(v: number | null | undefined): SymbolLevel {
  const n = Math.round(Number(v) || 0);
  return (n < 0 ? 0 : n > 3 ? 3 : n) as SymbolLevel;
}

export interface HabitSymbolProps {
  levels: SymbolLevels;
  /** Layers to draw; default all four. */
  visible?: SymbolLayer[];
  /** Rendered width/height in px. */
  size?: number | string;
  title?: string;
}

export default function HabitSymbol({ levels, visible = SYMBOL_LAYERS, size = 40, title }: HabitSymbolProps) {
  const g = HABIT_SYMBOL_GEOMETRY;
  const show = (l: SymbolLayer) => visible.includes(l);
  const paint = (l: SymbolLayer) => {
    const lv = clampLevel(levels[l]);
    return {
      stroke: lv === 0 ? HABIT_SYMBOL_FAINT_COLOR : HABIT_SYMBOL_COLOR,
      opacity: HABIT_SYMBOL_OPACITY[lv],
    };
  };
  const common = { fill: 'none', strokeWidth: g.stroke, strokeLinejoin: 'round' as const };
  const d = g.mindR;
  const diamond = `${g.c},${g.c - d} ${g.c + d},${g.c} ${g.c},${g.c + d} ${g.c - d},${g.c}`;
  const label = title ?? SYMBOL_LAYERS.filter(show).map(l => `${l} ${clampLevel(levels[l])}`).join(', ');
  return (
    <svg viewBox={`0 0 ${g.box} ${g.box}`} width={size} height={size} role="img" aria-label={label}
         shapeRendering="geometricPrecision" style={{ display: 'block' }}>
      <title>{label}</title>
      {show('body') && <circle cx={g.c} cy={g.c} r={g.bodyR} {...common} {...paint('body')} />}
      {show('mind') && <polygon points={diamond} {...common} {...paint('mind')} />}
      {show('organization') && <circle cx={g.c} cy={g.c} r={g.organizationR} {...common} {...paint('organization')} />}
      {show('discipline') && (
        <circle cx={g.c} cy={g.c} r={g.disciplineR} fill={paint('discipline').stroke}
                opacity={paint('discipline').opacity} />
      )}
    </svg>
  );
}
