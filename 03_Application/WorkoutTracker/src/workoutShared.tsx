/**
 * WorkoutTracker shared UI pieces: row types, the stacked-reps chart, the delta chip
 * and the confirm dialog. Imported by SessionView, ExerciseLogView and ShellEntry.
 */

import { useId, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import type { Dataset, Row } from "@platform-ui/api/types";

// ── Log / archetype cache (stale-while-revalidate) ───────────────────────────
// Last page-1 result per archetype filter and the archetype list, kept at module level so they
// survive tab-switch remounts. Views paint them immediately and always refetch. Anything that
// adds, removes or edits a FINISHED session must call invalidateLogCache() so a stale list is
// never painted. The active-session state is never cached.

export const LOG_PAGE_SIZE = 15;

export interface LogCacheEntry {
  sessions: unknown[];
  total: number;
}
export const logCache = new Map<string, LogCacheEntry>();
export let archetypesCache: Row[] | null = null;
let cacheGen = 0; // bumped on invalidation so an in-flight warm-up can't write stale data back

export function setArchetypesCache(v: Row[] | null) {
  archetypesCache = v;
}
export function invalidateLogCache() {
  cacheGen++;
  logCache.clear();
  archetypesCache = null;
}

export function logQuery(page: number, split: string): string {
  const q = new URLSearchParams({ page: String(page), page_size: String(LOG_PAGE_SIZE), include_exercises: "true" });
  if (split) q.set("split", split);
  return q.toString();
}

/**
 * Fill whatever the Log/Session screens would otherwise fetch on first use: the archetype list and
 * page 1 for "All" and each archetype filter. Call it once a screen's own requests have finished;
 * it runs one request at a time, skips what is cached, and ignores errors.
 */
let warming = false;
export function warmLogCache() {
  if (warming) return;
  warming = true;
  const gen = cacheGen;
  const stale = () => gen !== cacheGen;
  setTimeout(async () => {
    try {
      if (!archetypesCache) {
        const res = await apiFetch<Dataset>("/workout/archetypes");
        if (stale() || isApiError(res)) return;
        archetypesCache = res.rows;
      }
      const splits = ["", ...archetypesCache.map((r) => String(r.split))];
      for (const split of splits) {
        if (logCache.has(split)) continue;
        const res = await apiFetch<Dataset>(`/workout/sessions?${logQuery(1, split)}`);
        if (stale()) return;
        if (!isApiError(res)) logCache.set(split, { sessions: res.rows, total: res.meta.total });
      }
    } finally {
      warming = false;
    }
  }, 300);
}

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
  /** Measured timing summary (exercise history only); null/absent when not measured. */
  started_at?: string | null;
  ended_at?: string | null;
  duration_sec?: number | null;
  rest_avg_sec?: number | null;
  time_of_day?: string | null;
}

/** One exercise row of a session as returned by /workout/sessions/{id}/exercises. */
export interface ExerciseRow extends HistoryRow {
  exercise: string;
  status: "planned" | "done";
  total_reps: number;
  delta: number | null;
  /** Per-set timing from the server clock (ISO). NULL = not measured. Present as set{n}_started_at / set{n}_ended_at. */
  set1_started_at?: string | null;
  set1_ended_at?: string | null;
  set2_started_at?: string | null;
  set2_ended_at?: string | null;
  set3_started_at?: string | null;
  set3_ended_at?: string | null;
  set4_started_at?: string | null;
  set4_ended_at?: string | null;
  set5_started_at?: string | null;
  set5_ended_at?: string | null;
}

/** The browser's IANA time zone, stored with a workout when it is started (time-of-day analysis). */
export function clientTz(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

export function setsOf(
  r: Pick<HistoryRow, "set1_reps" | "set2_reps" | "set3_reps" | "set4_reps" | "set5_reps">,
): SetReps {
  return [r.set1_reps, r.set2_reps, r.set3_reps, r.set4_reps, r.set5_reps];
}

export function totalOf(
  r: Pick<HistoryRow, "set1_reps" | "set2_reps" | "set3_reps" | "set4_reps" | "set5_reps">,
): number {
  return setsOf(r).reduce<number>((a, v) => a + (v ?? 0), 0);
}

/** m:ss for a running timer or a rest (e.g. 2:05). */
export function fmtClock(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Elapsed exercise time, compact: "45 s" under 90 s, else whole minutes. */
export function fmtDuration(sec: number): string {
  return sec < 90 ? `${Math.round(sec)} s` : `${Math.round(sec / 60)} min`;
}

/** "17:11 · 9 min · rest 2:00" from whatever was measured; null when nothing was. */
export function timingSummary(r: Pick<HistoryRow, "time_of_day" | "duration_sec" | "rest_avg_sec">): string | null {
  const parts = [
    r.time_of_day ?? null,
    r.duration_sec != null ? fmtDuration(r.duration_sec) : null,
    r.rest_avg_sec != null ? `rest ${fmtClock(r.rest_avg_sec)}` : null,
  ].filter((p): p is string => p !== null);
  return parts.length ? parts.join(" · ") : null;
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

export function fmtDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** "4 × 10" when every recorded set has the same reps, else the real per-set reps ("12/11/10/9"). */
export function repsSummary(sets: SetReps): string {
  const v = sets.filter((x): x is number => x != null);
  if (v.length === 0) return "—";
  if (v.every((x) => x === v[0])) return `${v.length} × ${v[0]}`;
  return v.join("/");
}

export function historyPath(name: string): string {
  return `/workout/log/exercise?name=${encodeURIComponent(name)}`;
}

/** Back to where the user came from; falls back to `fallback` for deep links. */
export function useGoBack(fallback: string): () => void {
  const navigate = useNavigate();
  return () => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate(fallback);
  };
}

// ── Weight labels (shared by the mini charts and the history chart) ───────────
// A run is a stretch of consecutive occurrences with the same weight. Labels are anchored at the
// run start, clamped inside the chart, placed newest-first; one that would collide with a newer
// label is dropped (the run bracket stays). A missing weight is never labelled.

export interface WeightRun {
  x0: number;
  x1: number;
  weight: number | null;
}

export function placeWeightLabels(runs: WeightRun[], width: number, fontPx: number): { x: number; text: string }[] {
  const textW = (t: string) => t.length * fontPx * 0.56 + 1;
  let limit = width + 4;
  const labels: { x: number; text: string }[] = [];
  for (let k = runs.length - 1; k >= 0; k--) {
    const run = runs[k];
    if (run.weight == null) continue;
    const text = textW(`${run.weight} kg`) <= run.x1 - run.x0 ? `${run.weight} kg` : `${run.weight}`;
    const x = Math.min(run.x0, width - textW(text) + 4);
    if (x + textW(text) <= limit + 0.5) {
      labels.push({ x, text });
      limit = x - 2;
    }
  }
  return labels;
}

/** Group consecutive equal weights: [{start, end(exclusive), weight}] */
export function weightRuns(rows: { weight_kg: number | null }[]): { start: number; end: number; weight: number | null }[] {
  const runs: { start: number; end: number; weight: number | null }[] = [];
  rows.forEach((r, i) => {
    if (i === 0 || (r.weight_kg ?? null) !== (rows[i - 1].weight_kg ?? null)) {
      runs.push({ start: i, end: i + 1, weight: r.weight_kg ?? null });
    } else {
      runs[runs.length - 1].end = i + 1;
    }
  });
  return runs;
}

/** Reps per set as equal blocks, set 1 darkest → later sets lighter. Only recorded sets are shown. */
export function SetBlocks({ sets }: { sets: SetReps }) {
  const shown = sets.map((v, i) => ({ v, i })).filter((x) => x.v != null);
  return (
    <div
      role="group"
      aria-label={`Reps per set: ${shown.map((x) => x.v).join(", ")}`}
      style={{ display: "flex", gap: 2, height: 28, borderRadius: 6, overflow: "hidden" }}
    >
      {shown.map(({ v, i }) => (
        <div
          key={i}
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 600,
            fontVariantNumeric: "tabular-nums",
            background: SET_SHADES[i],
            color: i < 3 ? "#fff" : "var(--md-sys-color-on-surface)",
          }}
        >
          {v}
        </div>
      ))}
    </div>
  );
}

// ── RepsChart ─────────────────────────────────────────────────────────────────
// One column per exercise occurrence; one segment per set. Column height = total reps
// (scaled to the tallest visible column), set 1 darkest at the bottom, later sets lighter.
// Right-aligned inside a fixed number of slots so sparse histories don't stretch.

export const SET_SHADES = [
  "var(--wt-set-1, var(--atlas-chart-1))",
  "var(--wt-set-2, var(--atlas-chart-2))",
  "var(--wt-set-3, var(--atlas-chart-3))",
  "var(--wt-set-4, var(--atlas-chart-4))",
  "var(--wt-set-5, color-mix(in srgb, var(--atlas-chart-4) 55%, var(--md-sys-color-surface)))",
];

/** Fixed width of the mini chart in the Session list (px). */
export const MINI_CHART_W = 132;

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
  const barAreaH = variant === "mini" ? 40 : 96;
  const labelH = variant === "mini" ? 14 : 18;
  const gap = variant === "mini" ? 2 : 3;
  const descId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(variant === "mini" ? MINI_CHART_W : 340);

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
          width: variant === "mini" ? MINI_CHART_W : "100%",
          height: variant === "mini" ? barAreaH + labelH : 28,
          flexShrink: 0,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "flex-end",
          fontSize: 11,
          paddingBottom: 2,
          borderBottom: "1px dashed var(--md-sys-color-outline-variant)",
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

  const fontPx = variant === "mini" ? 10 : 11;
  const colW = (width - gap * (slots - 1)) / slots;
  const xOf = (i: number) => (offset + i) * (colW + gap);
  const labels = placeWeightLabels(
    runs.map((r) => ({ x0: xOf(r.idx), x1: xOf(r.idx + r.span) - gap, weight: visible[r.idx].weight_kg })),
    width,
    fontPx,
  );

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
      style={{ width: variant === "mini" ? MINI_CHART_W : "100%", flexShrink: 0 }}
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
