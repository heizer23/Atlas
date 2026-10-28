/**
 * WorkoutTracker shared UI pieces: row types, the stacked-reps chart, the delta chip
 * and the confirm dialog. Imported by SessionView, ExerciseLogView and ShellEntry.
 */

import { useId, useLayoutEffect, useRef, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type SetReps = [number | null, number | null, number | null, number | null, number | null];

/** One exercise occurrence as returned by /workout/exercises/history. */
export interface HistoryRow {
  id: string;
  workout_date: string;
  weight_kg: number | null;
  set1_reps: number | null;
  set2_reps: number | null;
  set3_reps: number | null;
  set4_reps: number | null;
  set5_reps: number | null;
  comment?: string | null;
  split?: string | null;
}

/** One exercise row of a session as returned by /workout/sessions/{id}/exercises. */
export interface ExerciseRow extends HistoryRow {
  exercise: string;
  status: "planned" | "done";
  total_reps: number;
  delta: number | null;
}

export function setsOf(r: HistoryRow): SetReps {
  return [r.set1_reps, r.set2_reps, r.set3_reps, r.set4_reps, r.set5_reps];
}

export function totalOf(r: HistoryRow): number {
  return setsOf(r).reduce<number>((a, v) => a + (v ?? 0), 0);
}

export function fmtWeight(w: number | null | undefined): string {
  return w == null ? "no weight" : `${w} kg`;
}

export function fmtShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function fmtLongDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

// ── RepsChart ─────────────────────────────────────────────────────────────────
// One column per exercise occurrence; one segment per set. Column height = total reps
// (scaled to the tallest visible column), set 1 darkest at the bottom, later sets lighter.
// Right-aligned inside a fixed number of slots so sparse histories don't stretch.

export const SET_SHADES = [
  "var(--atlas-chart-1)",
  "var(--atlas-chart-2)",
  "var(--atlas-chart-3)",
  "var(--atlas-chart-4)",
  "color-mix(in srgb, var(--atlas-chart-4) 55%, var(--md-sys-color-surface))",
];

interface RepsChartProps {
  rows: HistoryRow[];
  /** mini = fixed 148px wide, 15 slots (Session list); large = full width, 20 slots */
  variant: "mini" | "large";
  /** Optional in-progress column appended on the right (not yet saved). */
  liveRow?: HistoryRow;
  className?: string;
}

function sameWeight(a: number | null, b: number | null) {
  return (a ?? null) === (b ?? null);
}

export function RepsChart({ rows, variant, liveRow }: RepsChartProps) {
  const slots = variant === "mini" ? 15 : 20;
  const barAreaH = variant === "mini" ? 36 : 120;
  const labelH = variant === "mini" ? 14 : 18;
  const gap = variant === "mini" ? 2 : 3;
  const descId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(variant === "mini" ? 148 : 340);

  useLayoutEffect(() => {
    if (variant === "mini") return;
    const el = wrapRef.current;
    if (!el) return;
    setWidth(el.getBoundingClientRect().width || 340);
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width || 340));
    ro.observe(el);
    return () => ro.disconnect();
  }, [variant]);

  const all = liveRow ? [...rows, liveRow] : rows;
  const visible = all.slice(-slots);
  const offset = slots - visible.length; // empty slots on the left

  if (visible.length === 0) {
    return (
      <div
        role="img"
        aria-label="No history yet"
        style={{
          width: variant === "mini" ? 148 : "100%",
          height: barAreaH + labelH,
          flexShrink: 0,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "flex-end",
          fontSize: 11,
          color: "var(--md-sys-color-on-surface-variant)",
        }}
      >
        No history yet
      </div>
    );
  }

  const maxTotal = Math.max(1, ...visible.map(totalOf));

  // Weight runs: the first visible column, then wherever the weight changes.
  const runs: { idx: number; span: number }[] = [];
  visible.forEach((r, i) => {
    if (i === 0 || !sameWeight(r.weight_kg, visible[i - 1].weight_kg)) runs.push({ idx: i, span: 0 });
  });
  runs.forEach((r, k) => {
    r.span = (k + 1 < runs.length ? runs[k + 1].idx : visible.length) - r.idx;
  });

  // Label placement in px: anchored at the run start, clamped inside the chart. Labels are
  // placed newest-first and a label that would collide with a newer one is dropped (the run
  // bracket stays); exact weights are always available in the exercise history.
  const fontPx = variant === "mini" ? 10 : 11;
  const colW = (width - gap * (slots - 1)) / slots;
  const xOf = (i: number) => (offset + i) * (colW + gap);
  const textW = (t: string) => t.length * fontPx * 0.6 + 2;
  let limit = width;
  const labels: { x: number; text: string }[] = [];
  for (let k = runs.length - 1; k >= 0; k--) {
    const run = runs[k];
    const w = visible[run.idx].weight_kg;
    const runPx = run.span * (colW + gap) - gap;
    const base = w == null ? "" : `${w}`;
    const text = w != null && textW(`${w} kg`) <= runPx ? `${w} kg` : base;
    if (!text) continue; // no recorded weight: bracket only, nothing asserted
    const x = Math.min(xOf(run.idx), width - textW(text));
    if (x + textW(text) <= limit + 0.5) {
      labels.push({ x, text });
      limit = x - 2;
    }
  }

  const newest = visible[visible.length - 1];
  const summary = `${visible.length} most recent sessions, newest ${fmtShortDate(newest.workout_date)}: ${fmtWeight(
    newest.weight_kg,
  )}, ${setsOf(newest).filter((v) => v != null).join("+")} reps`;

  const colTemplate = `repeat(${slots}, minmax(0, 1fr))`;

  return (
    <div
      role="img"
      aria-label={summary}
      aria-describedby={descId}
      ref={wrapRef}
      style={{ width: variant === "mini" ? 148 : "100%", flexShrink: 0 }}
    >
      <span id={descId} style={{ display: "none" }}>
        {visible
          .map((r) => `${fmtShortDate(r.workout_date)} ${fmtWeight(r.weight_kg)}: ${setsOf(r).filter((v) => v != null).join("/")}`)
          .join("; ")}
      </span>

      {/* weight labels: run brackets + placed labels */}
      <div style={{ position: "relative", height: labelH }}>
        {runs.map((r) => (
          <div
            key={`b${r.idx}`}
            style={{
              position: "absolute",
              left: xOf(r.idx),
              width: r.span * (colW + gap) - gap,
              bottom: 0,
              borderBottom: "1px solid var(--md-sys-color-outline-variant)",
            }}
          />
        ))}
        {labels.map((l) => (
          <span
            key={l.x}
            style={{
              position: "absolute",
              left: l.x,
              bottom: 2,
              fontSize: fontPx,
              lineHeight: 1,
              whiteSpace: "nowrap",
              color: "var(--md-sys-color-on-surface-variant)",
            }}
          >
            {l.text}
          </span>
        ))}
      </div>

      {/* bars */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: colTemplate,
          columnGap: gap,
          height: barAreaH,
          alignItems: "end",
          marginTop: 2,
        }}
      >
        {visible.map((r, i) => {
          const isLive = liveRow !== undefined && i === visible.length - 1;
          const sets = setsOf(r);
          const tot = totalOf(r);
          return (
            <div
              key={r.id ?? i}
              title={`${fmtShortDate(r.workout_date)} · ${fmtWeight(r.weight_kg)} · ${sets.filter((v) => v != null).join("/")} reps`}
              style={{
                gridColumn: offset + i + 1,
                height: `${(tot / maxTotal) * 100}%`,
                minHeight: tot > 0 ? 2 : 0,
                display: "flex",
                flexDirection: "column-reverse",
                borderRadius: "2px 2px 0 0",
                overflow: "hidden",
                outline: isLive ? "1px dashed var(--md-sys-color-primary)" : "none",
                outlineOffset: 1,
              }}
            >
              {sets.map((v, si) =>
                v ? <div key={si} style={{ height: `${(v / tot) * 100}%`, background: SET_SHADES[si] }} /> : null,
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── DeltaChip ─────────────────────────────────────────────────────────────────
// Completed + comparable: positive blue, negative red, zero neutral.
// Not completed, or no valid comparison: neutral em dash.

export function DeltaChip({ delta, completed }: { delta: number | null | undefined; completed: boolean }) {
  const shown = completed && delta != null;
  const positive = shown && delta! > 0;
  const negative = shown && delta! < 0;
  const label = !shown ? "—" : delta! > 0 ? `+${delta}` : delta! < 0 ? `−${Math.abs(delta!)}` : "0";
  const aria = !shown
    ? completed
      ? "No comparable previous result"
      : "Not completed yet"
    : delta! > 0
      ? `${delta} more reps than last time`
      : delta! < 0
        ? `${Math.abs(delta!)} fewer reps than last time`
        : "Same reps as last time";

  return (
    <span
      aria-label={aria}
      title={aria}
      style={{
        flexShrink: 0,
        minWidth: 34,
        height: 22,
        padding: "0 8px",
        borderRadius: 11,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 12,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums",
        background: positive
          ? "color-mix(in srgb, var(--md-sys-color-primary) 16%, transparent)"
          : negative
            ? "var(--md-sys-color-error-container)"
            : "var(--md-sys-color-surface-variant)",
        color: positive
          ? "var(--md-sys-color-primary)"
          : negative
            ? "var(--md-sys-color-error)"
            : "var(--md-sys-color-on-surface-variant)",
      }}
    >
      {label}
    </span>
  );
}

// ── ConfirmDialog (canonical structure from UI_AppPatterns.md §6) ─────────────

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.4)",
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--md-sys-color-surface)",
          borderRadius: "var(--radius-dialog)",
          padding: "var(--space-lg)",
          maxWidth: 360,
          width: "90%",
          boxShadow: "var(--elevation-2)",
        }}
      >
        <h2 id={titleId} className="type-title">
          {title}
        </h2>
        <p
          className="type-body"
          style={{ color: "var(--md-sys-color-on-surface-variant)", margin: "var(--space-sm) 0 var(--space-md)" }}
        >
          {body}
        </p>
        <div style={{ display: "flex", gap: "var(--space-sm)", justifyContent: "flex-end" }}>
          <button className="btn-outlined" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button className={danger ? "btn-danger" : "btn-filled"} onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
