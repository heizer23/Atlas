/**
 * ExerciseHistoryView — one exercise across every archetype (route /workout/log/exercise?name=).
 *
 * Strictly read-only: selecting a column or a list entry only reveals recorded data or opens the
 * (read-only) session; nothing here creates or modifies a workout.
 *
 * Chart: one stacked column per occurrence; one segment per recorded set; column height = total
 * reps. "Sessions" spaces occurrences equally; "Timeline" places them by calendar date, so gaps are real.
 * All recorded exercises are rep-based today; occurrences without any reps are not charted.
 */

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import {
  SET_SHADES,
  SetBlocks,
  fmtDate,
  fmtShortDate,
  fmtWeight,
  placeWeightLabels,
  setsOf,
  totalOf,
  useGoBack,
  weightRuns,
  type HistoryRow,
} from "./workoutShared";

type Mode = "sessions" | "timeline";

const BAR_H = 132;
const LABEL_H = 16;
const AXIS_H = 18;
const GAP = 3;
const PAD = 6; // room for edge labels and the outlines of the first/last column
const DAY = 86_400_000;

const dayMs = (iso: string) => new Date(`${iso}T00:00:00`).getTime();

// ── Chart ─────────────────────────────────────────────────────────────────────

function HistoryChart({
  rows,
  mode,
  selected,
  onSelect,
}: {
  rows: HistoryRow[];
  mode: Mode;
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(340);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    setW(el.getBoundingClientRect().width || 340);
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width || 340));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = rows.length;
  const maxTotal = Math.max(1, ...rows.map(totalOf));

  // Column geometry
  const layout = useMemo(() => {
    if (mode === "sessions") {
      const colW = Math.max(10, Math.min(30, (W - 2 * PAD - GAP * (n - 1)) / n));
      const step = colW + GAP;
      const contentW = Math.max(W, n * step - GAP + 2 * PAD);
      const offset = contentW - PAD - (n * step - GAP); // newest at the right edge
      return { colW, contentW, xs: rows.map((_, i) => offset + i * step) };
    }
    // Timeline: x is proportional to the calendar date. The column width adapts to the closest
    // pair of sessions so columns don't overlap; the chart only scrolls if the data truly can't fit.
    const t = rows.map((r) => dayMs(r.workout_date));
    const t0 = t[0];
    const spanMs = Math.max(DAY, t[n - 1] - t0);
    const gaps = t.slice(1).map((v, i) => (v - t[i]) / DAY).filter((d) => d > 0);
    const minDays = gaps.length ? Math.min(...gaps) : 1;
    let colW = 10;
    for (let k = 0; k < 2; k++) {
      const pxPerDay = (W - 2 * PAD - colW) / (spanMs / DAY);
      colW = Math.max(4, Math.min(14, Math.floor(pxPerDay * minDays) - 1));
    }
    const scaleW = W - 2 * PAD - colW;
    const xs: number[] = [];
    t.forEach((ti, i) => {
      let x = n === 1 ? W - PAD - colW : PAD + ((ti - t0) / spanMs) * scaleW;
      if (i > 0) x = Math.max(x, xs[i - 1] + colW + 1); // same-day entries sit side by side
      xs.push(x);
    });
    return { colW, contentW: Math.max(W, xs[n - 1] + colW + PAD), xs, t0, spanMs, scaleW };
  }, [mode, rows, W, n]);

  const { colW, contentW, xs } = layout;

  // Keep the newest occurrences in view when the content is wider than the screen.
  const scrollRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [mode, contentW, n]);

  // Weight labels over each run of equal weight
  const runs = weightRuns(rows);
  const labels = placeWeightLabels(
    runs.map((r) => ({
      x0: xs[r.start],
      x1: r.end < n ? xs[r.end] - GAP : xs[n - 1] + colW,
      weight: r.weight,
    })),
    contentW,
    11,
  );

  // X-axis date ticks
  const ticks: { x: number; text: string }[] = [];
  if (mode === "sessions") {
    const every = Math.max(1, Math.ceil(72 / (colW + GAP)));
    for (let i = n - 1; i >= 0; i -= every) ticks.push({ x: xs[i] + colW / 2, text: fmtShortDate(rows[i].workout_date) });
  } else if (n === 1) {
    ticks.push({ x: xs[0] + colW / 2, text: fmtShortDate(rows[0].workout_date) });
  } else {
    const t = layout as { t0: number; spanMs: number; scaleW: number };
    const count = Math.max(2, Math.floor(contentW / 76));
    for (let k = 0; k <= count; k++) {
      const frac = k / count;
      const date = new Date(t.t0 + frac * t.spanMs);
      ticks.push({
        x: PAD + frac * t.scaleW + colW / 2,
        text: date.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      });
    }
  }

  return (
    <div ref={wrapRef} style={{ width: "100%" }}>
      <div ref={scrollRef} style={{ overflowX: "auto", overflowY: "hidden", WebkitOverflowScrolling: "touch" }}>
        <div
          role="group"
          aria-label={`${n} recorded sessions, ${mode === "sessions" ? "equally spaced" : "positioned by date"}`}
          style={{ position: "relative", width: contentW, height: LABEL_H + BAR_H + AXIS_H }}
        >
          {/* weight brackets + labels */}
          {runs.map((r) => (
            <div
              key={`b${r.start}`}
              style={{
                position: "absolute",
                top: LABEL_H - 1,
                left: xs[r.start],
                width: (r.end < n ? xs[r.end] - GAP : xs[n - 1] + colW) - xs[r.start],
                borderTop: "1px solid var(--md-sys-color-outline-variant)",
              }}
            />
          ))}
          {labels.map((l) => (
            <span
              key={l.x}
              style={{
                position: "absolute",
                top: 0,
                left: l.x,
                fontSize: 11,
                lineHeight: "14px",
                whiteSpace: "nowrap",
                color: "var(--md-sys-color-on-surface-variant)",
              }}
            >
              {l.text}
            </span>
          ))}

          {/* columns: the whole column height is the tap target */}
          {rows.map((r, i) => {
            const sets = setsOf(r);
            const tot = totalOf(r);
            const isSel = selected === i;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => onSelect(i)}
                aria-pressed={isSel}
                aria-label={`${fmtDate(r.workout_date)}, ${fmtWeight(r.weight_kg)}, reps ${sets.filter((v) => v != null).join(", ")}`}
                style={{
                  position: "absolute",
                  left: xs[i],
                  top: LABEL_H,
                  width: colW,
                  height: BAR_H,
                  padding: 0,
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "flex-end",
                  opacity: selected === null || isSel ? 1 : 0.45,
                  touchAction: "manipulation",
                }}
              >
                <span
                  style={{
                    width: "100%",
                    height: `${(tot / maxTotal) * 100}%`,
                    minHeight: tot > 0 ? 2 : 0,
                    display: "flex",
                    flexDirection: "column-reverse",
                    borderRadius: "2px 2px 0 0",
                    overflow: "hidden",
                    outline: isSel ? "2px solid var(--md-sys-color-primary)" : "none",
                    outlineOffset: 1,
                  }}
                >
                  {sets.map((v, si) =>
                    v ? <span key={si} style={{ display: "block", height: `${(v / tot) * 100}%`, background: SET_SHADES[si] }} /> : null,
                  )}
                </span>
              </button>
            );
          })}

          {/* baseline + date ticks */}
          <div
            style={{
              position: "absolute",
              top: LABEL_H + BAR_H,
              left: 0,
              width: contentW,
              borderTop: "1px solid var(--md-sys-color-outline-variant)",
            }}
          />
          {ticks.map((t, k) => (
            <span
              key={k}
              aria-hidden
              style={{
                position: "absolute",
                top: LABEL_H + BAR_H + 3,
                left: Math.min(Math.max(t.x - 24, 0), contentW - 48),
                width: 48,
                textAlign: "center",
                fontSize: 11,
                color: "var(--md-sys-color-on-surface-variant)",
                whiteSpace: "nowrap",
              }}
            >
              {t.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── View ──────────────────────────────────────────────────────────────────────

export default function ExerciseHistoryView() {
  const [params] = useSearchParams();
  const name = params.get("name") ?? "";
  const navigate = useNavigate();
  const goBack = useGoBack("/workout/log");

  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [mode, setMode] = useState<Mode>("sessions");
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    setRows(null);
    setSelected(null);
    setError(null);
    if (!name.trim()) return setRows([]);
    apiFetch<Dataset>(`/workout/exercises/history?name=${encodeURIComponent(name)}`).then((res) => {
      if (isApiError(res)) return setError(res);
      setRows(res.rows as unknown as HistoryRow[]);
    });
  }, [name]);

  const charted = useMemo(() => (rows ?? []).filter((r) => totalOf(r) > 0), [rows]);
  const sel = selected !== null ? charted[selected] : null;

  const openSession = (r: HistoryRow) => {
    const sid = (r as HistoryRow & { session_id?: string }).session_id;
    if (sid) navigate(`/workout/log/${sid}`);
  };

  return (
    <div className="page" style={{ gap: 12 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 4, marginLeft: -6 }}>
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={goBack} aria-label="Back">
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <div style={{ minWidth: 0, paddingTop: 6 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, lineHeight: 1.25, letterSpacing: "-0.01em", overflowWrap: "anywhere" }}>
            {name || "Exercise"}
          </h1>
          {rows && rows.length > 0 && (
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
              {rows.length} {rows.length === 1 ? "session" : "sessions"} recorded
            </p>
          )}
        </div>
      </div>

      {error && <ErrorCard error={error} />}
      {rows === null && !error && <p className="type-body">Loading…</p>}
      {rows && rows.length === 0 && (
        <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
          No recorded sets for this exercise yet.
        </p>
      )}

      {charted.length > 0 && (
        <>
          <div
            role="group"
            aria-label="Chart spacing"
            style={{ display: "flex", padding: 3, borderRadius: 12, background: "var(--md-sys-color-surface-variant)" }}
          >
            {(["sessions", "timeline"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => {
                  setMode(m);
                  setSelected(null);
                }}
                style={{
                  flex: 1,
                  minHeight: 40,
                  border: "none",
                  borderRadius: 10,
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: "pointer",
                  background: mode === m ? "var(--md-sys-color-primary)" : "transparent",
                  color: mode === m ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-on-surface)",
                }}
              >
                {m === "sessions" ? "Sessions" : "Timeline"}
              </button>
            ))}
          </div>

          <HistoryChart rows={charted} mode={mode} selected={selected} onSelect={(i) => setSelected(i === selected ? null : i)} />

          {sel ? (
            <section
              aria-label="Selected session"
              style={{
                border: "1px solid var(--md-sys-color-outline-variant)",
                borderRadius: 12,
                boxShadow: "var(--wt-card-shadow)",
                padding: "10px 12px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Previous session"
                  disabled={selected === 0}
                  onClick={() => setSelected((s) => (s === null ? s : Math.max(0, s - 1)))}
                >
                  <span className="material-symbols-rounded">chevron_left</span>
                </button>
                <div style={{ flex: 1, minWidth: 0, textAlign: "center" }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{fmtDate(sel.workout_date)}</div>
                  <div style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
                    {fmtWeight(sel.weight_kg)} · {setsOf(sel).filter((v) => v != null).length} sets · {totalOf(sel)} reps
                  </div>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Next session"
                  disabled={selected === charted.length - 1}
                  onClick={() => setSelected((s) => (s === null ? s : Math.min(charted.length - 1, s + 1)))}
                >
                  <span className="material-symbols-rounded">chevron_right</span>
                </button>
              </div>
              <SetBlocks sets={setsOf(sel)} />
              {sel.comment && sel.comment.trim() && (
                <p style={{ margin: 0, fontSize: 14, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{sel.comment}</p>
              )}
              <button
                type="button"
                className="btn-text"
                style={{ alignSelf: "flex-start", minHeight: 40, padding: "0 8px", color: "var(--md-sys-color-primary)" }}
                onClick={() => openSession(sel)}
              >
                Open session
              </button>
            </section>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
              Tap a column to see that session’s sets and weight.
            </p>
          )}
        </>
      )}

      {rows && rows.length > 0 && (
        <section aria-label="All sessions">
          <h2 style={{ margin: "4px 0 8px", fontSize: 17, fontWeight: 700 }}>Sessions</h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {[...rows].reverse().map((r) => {
              const idx = charted.findIndex((c) => c.id === r.id);
              const isSel = selected !== null && idx === selected;
              const sets = setsOf(r);
              return (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => openSession(r)}
                    aria-label={`${fmtDate(r.workout_date)}, open session`}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "10px 12px",
                      background: "var(--md-sys-color-surface)",
                      border: `1px solid ${isSel ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)"}`,
                      borderRadius: 12,
                      boxShadow: "var(--wt-card-shadow)",
                      color: "var(--md-sys-color-on-surface)",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "stretch",
                      gap: 8,
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontSize: 15, fontWeight: 600 }}>{fmtDate(r.workout_date)}</span>
                      <span style={{ fontSize: 15, fontWeight: 600 }}>{fmtWeight(r.weight_kg)}</span>
                      <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
                        {sets.filter((v) => v != null).length} sets · {totalOf(r)} reps
                      </span>
                    </span>
                    {totalOf(r) > 0 ? (
                      <SetBlocks sets={sets} />
                    ) : (
                      <span style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>No reps recorded</span>
                    )}
                    {r.comment && r.comment.trim() && (
                      <span style={{ fontSize: 14, whiteSpace: "pre-wrap", overflowWrap: "anywhere", color: "var(--md-sys-color-on-surface-variant)" }}>
                        {r.comment}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
