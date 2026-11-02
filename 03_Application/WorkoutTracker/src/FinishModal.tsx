/**
 * FinishModal — the reward after a completed activity day, in three steps: the year calendar (today's
 * day is added), the monthly race, the streak ranking. The charts live in ProgressCharts.tsx and
 * YearCalendar.tsx (shared with the Performance tab); this file only sequences them.
 */

import { useEffect, useRef, useState } from "react";
import YearCalendar from "./YearCalendar";
import { MUTED, MonthlyRace, PRIMARY, StreakRanking, useReducedMotion } from "./ProgressCharts";
import type { Celebration } from "./progressModel";

const STEPS = 3;
const NEXT = ["See my month →", "See my streak →", "Done"];

// ── Modal ─────────────────────────────────────────────────────────────────────

export default function FinishModal({ celebration, title, onClose }: { celebration: Celebration; title: string; onClose: () => void }) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
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
          <ol aria-label={`Step ${step} of 3`} style={{ display: "flex", gap: 6, listStyle: "none", margin: 0, padding: 0 }}>
            {[1, 2, 3].map((n) => (
              <li key={n} aria-current={step === n ? "step" : undefined}
                style={{ width: 8, height: 8, borderRadius: 4, background: step === n ? PRIMARY : "var(--md-sys-color-outline-variant)" }} />
            ))}
          </ol>
        </div>

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
          onClick={() => (step < STEPS ? setStep((step + 1) as 2 | 3) : onClose())}>
          {NEXT[step - 1]}
        </button>
      </div>
    </div>
  );
}
