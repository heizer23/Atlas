/**
 * YearCalendar — one row per month, one cell per day, coloured by the day's primary activity kind
 * (blue = workout, green = run, yellow = other, lilac = stretching/mobility). Left of each month: the
 * cumulative number of activity days. Read-only; data from GET /workout/calendar.
 */

import { useEffect, useMemo, useState } from "react";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import type { Dataset } from "@platform-ui/api/types";

const COLOURS: Record<string, string> = {
  workout: "#2B8BE0",
  running: "#3E9B5F",
  other: "#F2C94C",
  stretching: "#B7A6E0",
  mobility: "#B7A6E0",
};
const LEGEND = [
  ["Workout", COLOURS.workout],
  ["Run", COLOURS.running],
  ["Other", COLOURS.other],
  ["Stretch / mobility", COLOURS.stretching],
] as const;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * `reveal`: a day that was just added. It is left out until the data has loaded and `delayMs` has
 * passed, then it pops in and the counts tick up. Omit it for a plain, static calendar.
 */
export default function YearCalendar({ today, reveal }: { today: string; reveal?: { date: string; delayMs: number } }) {
  const year = Number(today.slice(0, 4));
  const [all, setAll] = useState<Map<string, string> | null>(null);
  const [revealed, setRevealed] = useState(!reveal);
  const days = useMemo(() => {
    if (!all || revealed || !reveal) return all;
    const m = new Map(all);
    m.delete(reveal.date);
    return m;
  }, [all, revealed, reveal]);

  useEffect(() => {
    if (!all || !reveal || revealed) return;
    const id = setTimeout(() => setRevealed(true), reveal.delayMs);
    return () => clearTimeout(id);
  }, [all, reveal, revealed]);

  useEffect(() => {
    let live = true;
    apiFetch<Dataset>(`/workout/calendar?year=${year}&today=${today}`).then((res) => {
      if (!live || isApiError(res)) return;
      setAll(new Map(res.rows.map((r) => [String(r.date), String(r.primary)])));
    });
    return () => {
      live = false;
    };
  }, [year, today]);

  let cumulative = 0;
  return (
    <section aria-label={`Activity calendar ${year}`} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 className="type-title" style={{ margin: 0 }}>{year}</h2>
        <span style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
          {days ? `${days.size} activity days` : ""}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }} role="img"
        aria-label={`Activity calendar ${year}: ${days?.size ?? 0} activity days`}>
        {MONTHS.map((name, m) => {
          const len = new Date(year, m + 1, 0).getDate();
          const inMonth = [...Array(len)].filter((_, i) => days?.has(`${year}-${String(m + 1).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`)).length;
          cumulative += inMonth;
          const cells = Array.from({ length: 31 }, (_, i) => {
            const day = i + 1;
            if (day > len) return <i key={day} style={{ background: "var(--md-sys-color-surface-variant)", opacity: 0.6, aspectRatio: "1" }} />;
            const iso = `${year}-${String(m + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const kind = days?.get(iso);
            return (
              <i key={day} title={kind ? `${iso} · ${kind}` : iso} className={reveal && revealed && iso === reveal.date ? "wt-cell-pop" : undefined}
                style={{ aspectRatio: "1", borderRadius: 2, background: kind ? COLOURS[kind] ?? COLOURS.other : "transparent",
                  border: kind ? "none" : "1px solid var(--md-sys-color-outline-variant)", boxSizing: "border-box",
                  outline: iso === today ? "2px solid var(--md-sys-color-on-surface)" : "none", outlineOffset: -1 }} />
            );
          });
          return (
            <div key={name} style={{ display: "grid", gridTemplateColumns: "28px 26px repeat(31, 1fr)", gap: 1.5, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "var(--md-sys-color-on-surface-variant)" }}>{name}</span>
              <span style={{ fontSize: 10, color: "var(--md-sys-color-on-surface-variant)", textAlign: "right", paddingRight: 4,
                fontVariantNumeric: "tabular-nums" }}>{days ? cumulative : ""}</span>
              {cells}
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 12px", fontSize: 11, color: "var(--md-sys-color-on-surface-variant)" }}>
        {LEGEND.map(([label, colour]) => (
          <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <i style={{ width: 9, height: 9, borderRadius: 2, background: colour, display: "inline-block" }} />{label}
          </span>
        ))}
      </div>
    </section>
  );
}
