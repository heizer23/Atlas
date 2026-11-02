/**
 * ActivityDayCard — log a lighter movement day (running, stretching, mobility, other, e.g. skiing). It counts exactly like a
 * strength session toward activity days and streaks. Shown under the archetype chooser.
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import type { Celebration, CompletionResult } from "./progressModel";

const KINDS = [
  { id: "running", label: "Run" },
  { id: "stretching", label: "Stretch" },
  { id: "mobility", label: "Mobility" },
  { id: "other", label: "Other" },
] as const;

interface Recent {
  activity_date: string;
  kind: string;
}

const label = (kind: string) => KINDS.find((k) => k.id === kind)?.label ?? kind;

export default function ActivityDayCard({ today, onCelebrate }: { today: string; onCelebrate: (c: Celebration) => void }) {
  const [date, setDate] = useState(today);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<Dataset>("/workout/activity-days?limit=5").then((res) => {
      if (!isApiError(res)) setRecent(res.rows as unknown as Recent[]);
    });
  }, []);
  useEffect(load, [load]);

  async function log(kind: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    const res = await apiFetch<CompletionResult>(`/workout/activity-days?today=${today}`, {
      method: "POST",
      body: JSON.stringify({ activity_date: date || today, kind }),
    });
    setBusy(false);
    if (isApiError(res)) return setError(res);
    load();
    if (res.celebration) onCelebrate(res.celebration);
    else setSaved(`${label(kind)} saved for ${date}.`);
  }

  async function remove(r: Recent) {
    const res = await apiFetch<unknown>(`/workout/activity-days/${r.activity_date}/${r.kind}`, { method: "DELETE" });
    if (isApiError(res)) return setError(res);
    setSaved(null);
    load();
  }

  const btn: React.CSSProperties = {
    flex: 1, minHeight: 44, border: "1px solid var(--md-sys-color-outline-variant)", borderRadius: 12,
    background: "var(--md-sys-color-surface)", color: "var(--md-sys-color-on-surface)", fontSize: 15, cursor: "pointer",
    touchAction: "manipulation",
  };

  return (
    <section aria-label="Log activity day" style={{ borderTop: "1px solid var(--md-sys-color-outline-variant)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h2 className="type-title" style={{ margin: 0 }}>Log activity day</h2>
        <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} aria-label="Date"
          style={{ height: 36, fontSize: 14, border: "1px solid var(--md-sys-color-outline-variant)", borderRadius: 8, padding: "0 8px",
            background: "var(--md-sys-color-surface)", color: "var(--md-sys-color-on-surface)" }} />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {KINDS.map((k) => (
          <button key={k.id} style={btn} disabled={busy} onClick={() => log(k.id)}>{k.label}</button>
        ))}
      </div>
      {error && <ErrorCard error={error} />}
      {saved && <p className="type-body" style={{ margin: 0, color: "var(--md-sys-color-on-surface-variant)" }}>{saved}</p>}
      {recent.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column" }} aria-label="Recent activity days">
          {recent.map((r) => (
            <li key={`${r.activity_date}|${r.kind}`} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", minHeight: 40, fontSize: 14 }}>
              <span>{r.activity_date} · {label(r.kind)}</span>
              <button onClick={() => remove(r)} aria-label={`Remove ${label(r.kind)} on ${r.activity_date}`}
                style={{ border: "none", background: "none", color: "var(--md-sys-color-on-surface-variant)", minWidth: 44, minHeight: 40, cursor: "pointer" }}>
                <span className="material-symbols-rounded" aria-hidden>close</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
