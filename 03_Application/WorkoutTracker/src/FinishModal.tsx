/**
 * FinishModal — the reward after a completed activity day, in four steps: this session's summary (time, reps vs. last time), the year calendar (today's
 * day is added), the monthly race, the streak ranking. The charts live in ProgressCharts.tsx and
 * YearCalendar.tsx (shared with the Performance tab); this file only sequences them.
 */

import { useEffect, useRef, useState } from "react";
import YearCalendar from "./YearCalendar";
import { MUTED, MonthlyRace, PRIMARY, StreakRanking, useReducedMotion } from "./ProgressCharts";
import { formatDuration, type Celebration, type SessionSummary } from "./progressModel";

const NEXT = ["See my year →", "See my month →", "See my streak →", "Done"];

// ── Step 0: this session ─────────────────────────────────────────────────────

function useCountUp(target: number, animate: boolean, ms = 900): number {
  const [v, setV] = useState(animate ? 0 : target);
  useEffect(() => {
    if (!animate) return setV(target);
    const t0 = performance.now();
    let raf = requestAnimationFrame(function tick(now) {
      const k = Math.min(1, (now - t0) / ms);
      setV(Math.round(target * (1 - (1 - k) ** 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(raf);
  }, [target, animate, ms]);
  return v;
}

const kg = (w: number | null) => (w == null ? "no weight" : `${w} kg`);

function SessionSummaryStep({ s, animate, headingId }: { s: SessionSummary; animate: boolean; headingId: string }) {
  const dur = useCountUp(Math.round((s.duration_sec ?? 0) / 60), animate);
  const faster = s.duration_sec != null && s.avg_duration_sec != null && s.duration_sec < s.avg_duration_sec;
  const maxReps = Math.max(1, ...s.exercises.flatMap((e) => [e.reps, e.prev_reps ?? 0]));
  return (
    <>
      <h2 id={headingId} style={{ margin: 0, fontSize: 22, fontWeight: 600, textAlign: "center" }}>This workout</h2>
      <div style={{ display: "flex", gap: 10 }}>
        <div className={animate ? "wt-welcome" : undefined} style={{ flex: 1, padding: 12, borderRadius: 14, background: "var(--md-sys-color-surface-container)", textAlign: "center" }}>
          <div style={{ fontSize: 12, color: MUTED }}>Total time</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: PRIMARY }}>
            {s.duration_sec == null ? "–" : dur < 60 ? `${dur} min` : formatDuration(dur * 60)}
          </div>
        </div>
        <div className={animate ? "wt-welcome" : undefined} style={{ flex: 1, padding: 12, borderRadius: 14, background: "var(--md-sys-color-surface-container)", textAlign: "center", animationDelay: "120ms" }}>
          <div style={{ fontSize: 12, color: MUTED }}>Average{s.avg_count ? ` (${s.avg_count})` : ""}</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{s.avg_duration_sec == null ? "–" : formatDuration(s.avg_duration_sec)}</div>
          {faster && <div className={animate ? "wt-pop" : undefined} style={{ fontSize: 12, color: "#1E8E4E", animationDelay: "900ms" }}>⚡ faster than usual</div>}
        </div>
      </div>
      <ul style={{ flex: 1, minHeight: 0, overflowY: "auto", listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {s.exercises.map((e, i) => {
          const d = e.prev_reps == null ? null : e.reps - e.prev_reps;
          const color = d == null || d === 0 ? MUTED : d > 0 ? "#1E8E4E" : "#B3261E";
          return (
            <li key={`${e.exercise}-${i}`} className={animate ? "wt-welcome" : undefined}
              style={{ padding: "8px 10px", borderRadius: 12, background: "var(--md-sys-color-surface-container-low)", animationDelay: `${300 + i * 90}ms` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{e.exercise}</span>
                <span className={animate && d ? "wt-pop" : undefined} style={{ fontWeight: 700, fontSize: 14, color, animationDelay: `${700 + i * 90}ms` }}>
                  {e.prev_reps == null ? "first time ✨" : d === 0 ? "= same" : `${d! > 0 ? "▲ +" : "▼ "}${d}`}
                </span>
              </div>
              {([["Now", e.reps, PRIMARY], ["Last", e.prev_reps, MUTED]] as const).map(([label, v, c]) => v != null && (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, fontSize: 12 }}>
                  <span style={{ width: 30, color: MUTED }}>{label}</span>
                  <div style={{ flex: 1, height: 8, borderRadius: 4, background: "var(--md-sys-color-surface-container-highest)" }}>
                    <div className={animate ? "wt-bar" : undefined} style={{ width: `${(v / maxReps) * 100}%`, height: "100%", borderRadius: 4, background: c, animationDelay: `${400 + i * 90}ms` }} />
                  </div>
                  <span style={{ width: 26, textAlign: "right", fontWeight: 600 }}>{v}</span>
                </div>
              ))}
              {e.weight_changed ? (
                <div className={animate ? "wt-pop" : undefined} style={{ marginTop: 4, fontSize: 12, fontWeight: 600, color: "#9A5B00", animationDelay: `${900 + i * 90}ms` }}>
                  ⚖ Weight changed: {kg(e.prev_weight_kg)} → {kg(e.weight_kg)} (reps not directly comparable)
                </div>
              ) : e.prev_reps != null && e.weight_kg != null ? (
                <div style={{ marginTop: 4, fontSize: 12, color: MUTED }}>Same weight: {kg(e.weight_kg)}</div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

export default function FinishModal({ celebration, summary, title, onClose }: { celebration: Celebration; summary?: SessionSummary | null; title: string; onClose: () => void }) {
  // Steps are numbered from 0 only when a session summary exists (workout finish); activity logs start at the calendar.
  const first = summary ? 0 : 1;
  const [step, setStep] = useState<number>(first);
  const STEPS = 3;
  const reduced = useReducedMotion();
  const animate = celebration.changed && !reduced;
  const next = useRef<HTMLButtonElement>(null);

  useEffect(() => next.current?.focus(), [step]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="finish-title"
      style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.45)", display: "flex",
        alignItems: "center", justifyContent: "center", padding: 12 }}>
      <div style={{ width: "100%", maxWidth: 440, height: "min(100%, 760px)", boxSizing: "border-box", display: "flex",
        flexDirection: "column", gap: 10, padding: 16, background: "var(--md-sys-color-surface)", borderRadius: 20,
        color: "var(--md-sys-color-on-surface)", overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600 }}>
            <span className="material-symbols-rounded" aria-hidden style={{ color: "#1E8E4E", fontVariationSettings: "'FILL' 1" }}>check_circle</span>
            {title}
          </span>
          <ol aria-label={`Step ${step + 1 - first} of ${STEPS + 1 - first}`} style={{ display: "flex", gap: 6, listStyle: "none", margin: 0, padding: 0 }}>
            {[0, 1, 2, 3].filter((n) => n >= first).map((n) => (
              <li key={n} aria-current={step === n ? "step" : undefined}
                style={{ width: 8, height: 8, borderRadius: 4, background: step === n ? PRIMARY : "var(--md-sys-color-outline-variant)" }} />
            ))}
          </ol>
        </div>

        {step === 0 && summary && <SessionSummaryStep s={summary} animate={!reduced} headingId="finish-title" />}
        {step === 1 && (
          <>
            <div style={{ textAlign: "center" }}>
              <h2 id="finish-title" style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Your year</h2>
              {!celebration.changed && celebration.note && (
                <div style={{ fontSize: 13, color: MUTED }}>{celebration.note}</div>
              )}
            </div>
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
              <YearCalendar today={celebration.after.today} reveal={animate ? { date: celebration.after.today, delayMs: 800 } : undefined} />
            </div>
          </>
        )}
        {step === 2 && <MonthlyRace c={celebration} animate={animate} headingId="finish-title" />}
        {step === 3 && <StreakRanking c={celebration} animate={animate} headingId="finish-title" />}

        <button ref={next} className="btn-filled" style={{ minHeight: 48, fontSize: 16, flexShrink: 0 }}
          onClick={() => (step < STEPS ? setStep(step + 1) : onClose())}>
          {NEXT[step]}
        </button>
      </div>
    </div>
  );
}
