/**
 * PerformanceView — the progress charts at rest (route /workout/performance): year calendar,
 * monthly race and streak ranking. Same components as the finish celebration, without animation.
 */

import { useEffect, useState } from "react";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import { MonthlyRace, StreakRanking } from "./ProgressCharts";
import YearCalendar from "./YearCalendar";
import type { Celebration, Snapshot } from "./progressModel";
import { localDate } from "./SessionView";

const card: React.CSSProperties = {
  border: "1px solid var(--md-sys-color-outline-variant)",
  borderRadius: 16,
  boxShadow: "var(--wt-card-shadow)",
  padding: 14,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  boxSizing: "border-box",
};

export default function PerformanceView() {
  const today = localDate();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    apiFetch<Dataset>(`/workout/progress?today=${today}`).then((res) => {
      if (isApiError(res)) setError(res);
      else setSnap(res.rows[0] as unknown as Snapshot);
    });
  }, [today]);

  if (error) return <div className="page"><ErrorCard error={error} /></div>;
  if (!snap) return <div className="page"><p className="type-body">Loading…</p></div>;

  // A resting view: before = after, nothing changed, nothing animates.
  const still: Celebration = { before: snap, after: snap, changed: false, note: null, crossed_champions: false };
  return (
    <div className="page" style={{ gap: 14 }}>
      <h1 className="type-display" style={{ margin: 0 }}>Performance</h1>
      <section style={card}><YearCalendar today={today} /></section>
      <section style={{ ...card, height: 460 }}><MonthlyRace c={still} animate={false} /></section>
      <section style={{ ...card, height: 560 }}><StreakRanking c={still} animate={false} /></section>
    </div>
  );
}
