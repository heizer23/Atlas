/**
 * Progress charts shared by the finish celebration (FinishModal) and the Performance tab:
 * the monthly race and the streak ranking. Both draw a Celebration (before/after); with
 * `animate` false they show the "after" state at once. All numbers come from the backend.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AGE_COLOURS,
  CHAMPIONS_MIN,
  READABLE_H,
  ageBucket,
  ageLabels,
  aheadText,
  caughtUp,
  fitOthersHeight,
  fmtDay,
  fmtRange,
  layoutRanking,
  monthName,
  rankingBefore,
  type Celebration,
  type LayoutItem,
  type RankedStreak,
  type Snapshot,
  type StreakView,
} from "./progressModel";

const VIEW_KEY = "workout_streak_view";
export const PRIMARY = "var(--md-sys-color-primary)";
export const MUTED = "var(--md-sys-color-on-surface-variant)";
const LINE = "var(--md-sys-color-outline-variant)";

// ── Small hooks ───────────────────────────────────────────────────────────────

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

/** 0 → 1 over `ms` once `active` turns true (ease-out); stays 1 afterwards. */
function useTween(active: boolean, ms: number): number {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      setT(1 - Math.pow(1 - p, 3));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, ms]);
  return t;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function readView(): StreakView {
  try {
    return localStorage.getItem(VIEW_KEY) === "year" ? "year" : "all";
  } catch {
    return "all";
  }
}

// ── Step 1: monthly race ──────────────────────────────────────────────────────

const PAD = { l: 26, r: 26, t: 24, b: 20 };
const FREQ_MAX = 7; // average activity days per week

export function MonthlyRace({ c, animate, headingId }: { c: Celebration; animate: boolean; headingId?: string }) {
  const { before, after } = c;
  // The chart is drawn in real pixels of the space it is given, so it fills the modal on any phone.
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 340, h: 250 });
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setSize({ w: Math.max(240, el.clientWidth), h: Math.max(160, el.clientHeight) });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    return () => ro.disconnect();
  }, []);
  const W = size.w;
  const H = size.h;
  const PLOT_W = W - PAD.l - PAD.r;
  const PLOT_H = H - PAD.t - PAD.b;
  const [go, setGo] = useState(!animate);
  const t = useTween(animate && go, 1000);
  const tt = animate ? t : 1;
  const landed = !animate || t >= 1;
  useEffect(() => {
    if (!animate) return;
    const id = setTimeout(() => setGo(true), 700); // open on the old statistics, then grow
    return () => clearTimeout(id);
  }, [animate]);

  const year = after.month.year;
  const mi = after.month.month - 1;
  const years = after.years;
  const cur = String(year);
  const bars = (y: number, m: number): number => {
    const a = after.monthly[String(y)]?.[m];
    if (a == null) return 0;
    if (y !== year || m !== mi) return a;
    return lerp(before.monthly[cur][m] ?? 0, a, tt);
  };

  let max = 8;
  for (const y of years) for (let m = 0; m < 12; m++) max = Math.max(max, after.monthly[String(y)]?.[m] ?? 0);
  const yMax = Math.ceil(max / 4) * 4;
  const gw = PLOT_W / 12;
  const bw = Math.min(10, (gw - 4) / years.length);
  const barX = (m: number, yi: number) => PAD.l + m * gw + (gw - bw * years.length) / 2 + yi * bw;
  const yOf = (v: number) => PAD.t + PLOT_H - (v / yMax) * PLOT_H;
  const fOf = (f: number) => PAD.t + PLOT_H - (f / FREQ_MAX) * PLOT_H;

  const freq = (y: number): (number | null)[] => {
    const a = after.frequency[String(y)];
    if (!a) return [];
    if (y !== year) return a;
    return a.map((v, m) => (m === mi && v !== null ? lerp(before.frequency[cur][m] ?? 0, v, tt) : v));
  };
  const path = (vals: (number | null)[]) =>
    vals
      .map((v, m) => (v === null ? null : `${PAD.l + m * gw + gw / 2},${fOf(v)}`))
      .filter(Boolean)
      .map((p, i) => `${i ? "L" : "M"}${p}`)
      .join(" ");

  const count = Math.round(lerp(before.month.count, after.month.count, tt));
  const strong = c.changed && caughtUp(before.month.ahead, after.month.ahead);
  const ahead = aheadText(after.month.ahead);
  const colour = (yi: number) => (years[yi] === year ? PRIMARY : yi === years.length - 2 ? "#AAB6C8" : "#D3DAE5");
  const curFreq = freq(year);
  const lastPt = curFreq.length ? mi : 0;
  const badgeX = barX(mi, years.length - 1) + bw / 2;
  const badgeY = yOf(bars(year, mi)) - 6;

  return (
    <>
      <div style={{ textAlign: "center" }}>
        <h2 id={headingId} style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Your monthly race</h2>
        <div style={{ color: MUTED, fontSize: 14 }}>{monthName(after.month.month)} · day {after.month.day}</div>
        <div style={{ margin: "8px 0 2px", fontSize: 18 }} aria-live="polite">
          <span style={{ fontSize: 34, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{count}</span>{" "}
          <span style={{ fontWeight: 600 }}>activity {count === 1 ? "day" : "days"}</span>
        </div>
        <div style={{ minHeight: 20, fontSize: 15, color: PRIMARY, fontWeight: strong && landed ? 700 : 500 }}>
          {ahead ?? <span style={{ color: MUTED }}>No earlier years to compare yet</span>}
        </div>
        {!c.changed && c.note && <div style={{ fontSize: 13, color: MUTED }}>{c.note}</div>}
      </div>

      <div ref={box} style={{ flex: 1, minHeight: 0, position: "relative" }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" style={{ position: "absolute", inset: 0 }}
        aria-label={`Activity days per month for ${years.join(", ")}. This month ${after.month.count}${ahead ? `, ${ahead}` : ""}.`}>
        {[0, 1, 2, 3, 4].map((i) => {
          const v = (yMax / 4) * i;
          return (
            <g key={i}>
              <line x1={PAD.l} x2={W - PAD.r} y1={yOf(v)} y2={yOf(v)} stroke={LINE} strokeWidth={0.6} />
              <text x={PAD.l - 4} y={yOf(v) + 3} fontSize={9} textAnchor="end" fill={MUTED}>{v}</text>
            </g>
          );
        })}
        {[0, 2, 4, 6].map((f) => (
          <text key={f} x={W - PAD.r + 4} y={fOf(f) + 3} fontSize={9} fill={MUTED}>{f}</text>
        ))}
        <text x={W - PAD.r + 4} y={PAD.t - 8} fontSize={8} fill={MUTED}>/wk</text>

        {landed && c.changed && (
          <rect className="wt-race-highlight" x={PAD.l + mi * gw} y={PAD.t - 4} width={gw} height={PLOT_H + 4} rx={4}
            fill="var(--md-sys-color-primary-container)" opacity={0.7} />
        )}

        {Array.from({ length: 12 }, (_, m) => (
          <g key={m}>
            {years.map((y, yi) => {
              const v = bars(y, m);
              return v > 0 ? (
                <rect key={y} x={barX(m, yi)} y={yOf(v)} width={bw} height={PAD.t + PLOT_H - yOf(v)} rx={1.5} fill={colour(yi)} />
              ) : null;
            })}
            <text x={PAD.l + m * gw + gw / 2} y={H - 6} fontSize={9} textAnchor="middle" fill={MUTED}
              fontWeight={m === mi ? 700 : 400}>{monthName(m + 1, false)}</text>
          </g>
        ))}

        {after.frequency[String(year - 1)] && (
          <path d={path(freq(year - 1))} fill="none" stroke="#4A5260" strokeWidth={1.6} strokeDasharray="4 3" />
        )}
        <path d={path(curFreq)} fill="none" stroke="#173F9E" strokeWidth={2} />
        {curFreq[lastPt] != null && (
          <circle cx={PAD.l + lastPt * gw + gw / 2} cy={fOf(curFreq[lastPt] as number)} r={3.2} fill="#173F9E" stroke="#fff" strokeWidth={1} />
        )}

        {landed && c.changed && (
          <g className={strong ? "wt-race-badge wt-race-badge--strong" : "wt-race-badge"}
            style={{ transformOrigin: `${badgeX}px ${badgeY}px` }}>
            <rect x={badgeX - 11} y={badgeY - 15} width={22} height={15} rx={7} fill={PRIMARY} />
            <text x={badgeX} y={badgeY - 4} fontSize={10} fontWeight={700} textAnchor="middle" fill="#fff">+1</text>
          </g>
        )}
      </svg>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 12, color: MUTED, justifyContent: "center" }}>
        {years.map((y, yi) => (
          <span key={y} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <i style={{ width: 10, height: 10, borderRadius: 2, background: colour(yi), display: "inline-block" }} />
            {y}{y === year ? " (this year)" : ""}
          </span>
        ))}
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <i style={{ width: 16, height: 0, borderTop: "2px solid #173F9E", display: "inline-block" }} />{year} avg / week
        </span>
        {after.frequency[String(year - 1)] && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <i style={{ width: 16, height: 0, borderTop: "2px dashed #4A5260", display: "inline-block" }} />{year - 1} avg / week
          </span>
        )}
      </div>
      {after.month.ahead !== null && (
        <div style={{ textAlign: "center", fontSize: 12, color: MUTED }}>
          Compared through {fmtDay(after.month.last_year_through, year)}
        </div>
      )}
    </>
  );
}

// ── Step 2: streak ranking ────────────────────────────────────────────────────

function pick(s: Snapshot, view: StreakView): RankedStreak[] {
  return view === "year" ? s.ranking_year : s.ranking;
}

export function StreakRanking({ c, animate, headingId }: { c: Celebration; animate: boolean; headingId?: string }) {
  const { before, after } = c;
  const thisYear = after.month.year;
  const [view, setView] = useState<StreakView>(readView);
  const [expanded, setExpanded] = useState(false);
  const [phase, setPhase] = useState<0 | 1 | 2>(animate ? 0 : 2); // 0 old state · 1 count+bar grow · 2 climb
  const [welcome, setWelcome] = useState(!animate);
  const scroller = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState(300);
  // Transitions stay off until the list has been measured and painted once, so rows never slide in from a guess.
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setArmed(true)));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (!animate || !armed) return;
    const ids = [setTimeout(() => setPhase(1), 600), setTimeout(() => setPhase(2), 1700), setTimeout(() => setWelcome(true), 2900)];
    return () => ids.forEach(clearTimeout);
  }, [animate, armed]);

  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAvail(el.clientHeight));
    ro.observe(el);
    setAvail(el.clientHeight);
    return () => ro.disconnect();
  }, []);

  const afterList = pick(after, view);
  const beforeList = rankingBefore(pick(before, view), afterList);
  const othersH = fitOthersHeight(afterList, avail);
  const layoutB = layoutRanking(beforeList, expanded, othersH);
  const layoutA = layoutRanking(afterList, expanded, othersH);
  const showB = phase < 2;
  const layout = showB ? layoutB : layoutA;
  const posB = new Map(layoutB.items.map((i) => [i.key, i]));
  const placeOf = (i: LayoutItem) => (showB ? posB.get(i.key) ?? i : i);
  const items = layoutA.items;

  const curAfter = afterList.find((s) => s.current);
  const curBefore = beforeList.find((s) => s.current);
  const max = Math.max(1, ...afterList.map((s) => s.length));
  const tLen = useTween(animate && phase >= 1, 700);
  const lenNow = curAfter ? Math.round(lerp(curBefore?.length ?? 0, curAfter.length, animate ? tLen : 1)) : 0;
  const rankNow = showB ? curBefore?.rank : curAfter?.rank;
  const moved = curAfter && curBefore && !showB ? curBefore.rank - curAfter.rank : 0;
  const crossed = c.crossed_champions && welcome;

  // Keep the current streak in view: at its old place first, then follow it as it climbs.
  const reduced = !animate;
  useEffect(() => {
    const el = scroller.current;
    const it = layout.items.find((i) => i.key === "current");
    if (!el || !it) return;
    const top = Math.max(0, it.y - el.clientHeight / 2 + it.h / 2);
    el.scrollTo({ top, behavior: reduced || phase === 0 ? "auto" : "smooth" });
  }, [phase, view, expanded, reduced, layout]);

  function chooseView(v: StreakView) {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* ignore */
    }
  }

  const ease = animate && armed ? "transform 650ms cubic-bezier(.3,.7,.3,1)" : "none";
  const bounce = animate && armed ? "transform 900ms cubic-bezier(.3,1.35,.5,1)" : "none";

  return (
    <>
      <div style={{ textAlign: "center" }}>
        <h2 id={headingId} style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>
          {c.changed ? "Your streak is climbing" : "Your streak"}
        </h2>
        <div style={{ margin: "6px 0 0", fontSize: 34, fontWeight: 700, fontVariantNumeric: "tabular-nums" }} aria-live="polite">
          {lenNow} {lenNow === 1 ? "day" : "days"}
        </div>
        <div style={{ color: MUTED, fontSize: 14 }}>
          {rankNow ? `Rank ${rankNow} of ${afterList.length}` : "No current streak"}
          {moved > 0 && <span style={{ color: PRIMARY }}> · up {moved} {moved === 1 ? "place" : "places"}</span>}
        </div>
        {!c.changed && c.note && <div style={{ fontSize: 13, color: MUTED }}>{c.note}</div>}
        <div style={{ minHeight: 24, marginTop: 4 }}>
          {crossed && (
            <span className="wt-welcome" style={{ display: "inline-block", padding: "3px 12px", borderRadius: 12,
              background: "var(--md-sys-color-primary-container)", color: PRIMARY, fontSize: 13, fontWeight: 600 }}>
              Welcome to the Champions League.
            </span>
          )}
        </div>
      </div>

      <div role="tablist" aria-label="Streak ranking scope" style={{ display: "flex", background: "var(--md-sys-color-surface-variant)", borderRadius: 10, padding: 2 }}>
        {(["all", "year"] as const).map((v) => (
          <button key={v} role="tab" aria-selected={view === v} onClick={() => chooseView(v)}
            style={{ flex: 1, minHeight: 36, border: "none", borderRadius: 8, fontSize: 14, cursor: "pointer",
              background: view === v ? "var(--md-sys-color-primary-container)" : "transparent",
              color: view === v ? PRIMARY : MUTED, fontWeight: view === v ? 600 : 400 }}>
            {v === "all" ? "All time" : "This year"}
          </button>
        ))}
      </div>

      <div ref={scroller} style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", position: "relative" }}>
        <div role="list" aria-label="Streak ranking" style={{ position: "relative", height: layout.height }}>
          {items.map((it) => {
            const p = placeOf(it);
            const isCur = it.key === "current";
            const common: React.CSSProperties = {
              position: "absolute", left: 0, right: 0, top: 0, height: p.h,
              transform: `translateY(${p.y}px)`, transition: isCur ? bounce : ease,
              zIndex: isCur ? 2 : 0,
            };
            if (it.kind === "header") {
              const champ = it.key === "h-champ";
              return (
                <div key={it.key} style={{ ...common, display: "flex", alignItems: "flex-end", paddingBottom: 3,
                  fontSize: 11, letterSpacing: "0.06em", color: MUTED, fontWeight: 600 }}>
                  {champ ? `CHAMPIONS LEAGUE · ${CHAMPIONS_MIN}+ DAYS` : `ALL OTHERS · 1–${CHAMPIONS_MIN - 1} DAYS`}
                  {!champ && (
                    <button onClick={() => setExpanded((e) => !e)} aria-expanded={expanded}
                      style={{ marginLeft: "auto", border: "none", background: "none", color: PRIMARY, fontSize: 12,
                        cursor: "pointer", fontWeight: 600, letterSpacing: 0 }}>
                      {expanded ? "Collapse history" : "Expand history"}
                    </button>
                  )}
                </div>
              );
            }
            const s = it.streak as RankedStreak;
            const len = isCur ? (phase >= 1 ? curAfter?.length ?? s.length : curBefore?.length ?? s.length) : s.length;
            const rank = isCur ? rankNow : s.rank;
            const readable = p.h >= READABLE_H;
            const barH = readable ? 10 : Math.max(2, Math.min(5, p.h - 2));
            const colour = isCur ? PRIMARY : AGE_COLOURS[ageBucket(s.start, thisYear)];
            const label = isCur ? `${lenNow} · Current` : expanded ? `${len} · ${fmtRange(s, after.today, thisYear)}` : String(len);
            return (
              <div key={it.key} role="listitem"
                aria-label={`Rank ${rank}, ${len} days${isCur ? ", current streak" : ""}, ${fmtRange(s, after.today, thisYear)}`}
                style={{ ...common, display: "flex", flexDirection: "column", justifyContent: "center",
                  boxSizing: "border-box", padding: isCur ? "2px 6px" : 0, borderRadius: 8,
                  outline: isCur ? `2px solid ${PRIMARY}` : "none", outlineOffset: -1,
                  background: isCur ? "var(--md-sys-color-primary-container)" : "transparent" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 22, fontSize: 11, color: isCur ? PRIMARY : MUTED, fontWeight: isCur ? 700 : 400,
                    fontVariantNumeric: "tabular-nums", textAlign: "right", visibility: it.labelled || readable ? "visible" : "hidden" }}>
                    {rank}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", height: barH, borderRadius: barH / 2, background: colour,
                      width: `${(len / max) * 100}%`, minWidth: len > 0 ? 3 : 0,
                      transition: animate && armed && isCur ? "width 700ms cubic-bezier(.3,.7,.3,1)" : "none" }} />
                  </span>
                  <span style={{ minWidth: 0, maxWidth: "58%", fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    color: isCur ? PRIMARY : MUTED, fontWeight: isCur ? 700 : 400, fontVariantNumeric: "tabular-nums",
                    visibility: it.labelled || readable ? "visible" : "hidden" }}>
                    {label}
                  </span>
                </div>
                {isCur && <div style={{ marginLeft: 30, fontSize: 11, color: MUTED }}>{fmtRange(s, after.today, thisYear)}</div>}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 12px", justifyContent: "center", fontSize: 11, color: MUTED }}>
        {ageLabels(thisYear).map((l, i) => (
          <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <i style={{ width: 9, height: 9, borderRadius: 2, background: AGE_COLOURS[i], display: "inline-block" }} />{l}
          </span>
        ))}
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <i style={{ width: 9, height: 9, borderRadius: 2, background: PRIMARY, outline: `1.5px solid ${PRIMARY}`, outlineOffset: 1, display: "inline-block" }} />Current
        </span>
      </div>
    </>
  );
}

