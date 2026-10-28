/**
 * SessionView — the central "Session" tab (route /workout).
 *
 *   no active session → archetype chooser (start a session from an archetype)
 *   active session    → overview: exercises with mini history charts, Add Exercise, Finish Workout
 *
 * The active session lives in the database (workout.workout_session), so a reload or another
 * device resumes the same session. Which exercise screen was open is remembered locally.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset, Row } from "@platform-ui/api/types";
import ExerciseLogView from "./ExerciseLogView";
import {
  ConfirmDialog,
  DeltaChip,
  MINI_CHART_W,
  RepsChart,
  fmtLongDate,
  fmtShortDate,
  type ExerciseRow,
  type HistoryRow,
  clientTz,
} from "./workoutShared";

const OPEN_KEY = "workout_open_exercise";

interface ActiveSession {
  id: string;
  split: string;
  workout_date: string;
}

type OpenExercise = { sessionId: string; rowId: string | "new" };

function readOpen(): OpenExercise | null {
  try {
    const raw = localStorage.getItem(OPEN_KEY);
    return raw ? (JSON.parse(raw) as OpenExercise) : null;
  } catch {
    return null;
  }
}
function writeOpen(v: OpenExercise | null) {
  try {
    if (v) localStorage.setItem(OPEN_KEY, JSON.stringify(v));
    else localStorage.removeItem(OPEN_KEY);
  } catch {
    /* ignore */
  }
}

// ── Archetype chooser ─────────────────────────────────────────────────────────

function ArchetypeChooser({ onStarted }: { onStarted: (s: ActiveSession) => void }) {
  const [archetypes, setArchetypes] = useState<Row[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [newName, setNewName] = useState("");
  const [starting, setStarting] = useState(false);
  const lock = useRef(false);

  useEffect(() => {
    apiFetch<Dataset>("/workout/archetypes").then((res) => {
      if (isApiError(res)) setError(res);
      else setArchetypes(res.rows);
    });
  }, []);

  async function start(split: string) {
    if (lock.current || !split.trim()) return;
    lock.current = true;
    setStarting(true);
    setError(null);
    const res = await apiFetch<Dataset>("/workout/sessions/start", {
      method: "POST",
      body: JSON.stringify({ split: split.trim(), workout_date: localDate(), tz: clientTz() }),
    });
    if (isApiError(res)) {
      if (res.error.code === "ACTIVE_SESSION_EXISTS") {
        // Another tab/device started one meanwhile — resume it instead of failing.
        const active = await apiFetch<Dataset>("/workout/sessions/active");
        if (!isApiError(active) && active.rows[0]) return onStarted(active.rows[0] as unknown as ActiveSession);
      }
      setError(res);
      setStarting(false);
      lock.current = false;
      return;
    }
    onStarted(res.rows[0] as unknown as ActiveSession);
  }

  return (
    <div className="page">
      <h1 className="type-display" style={{ margin: 0 }}>
        Start workout
      </h1>
      {error && <ErrorCard error={error} />}
      {archetypes === null && !error && <p className="type-body">Loading…</p>}

      {archetypes && (
        <ul
          style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}
          aria-label="Workout types"
        >
          {archetypes.map((a) => (
            <li key={String(a.id)}>
              <button
                onClick={() => start(String(a.split))}
                disabled={starting}
                style={{
                  width: "100%",
                  minHeight: 64,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "8px 14px",
                  border: "1px solid var(--md-sys-color-outline-variant)",
                  borderRadius: 12,
                  boxShadow: "var(--wt-card-shadow)",
                  background: "var(--md-sys-color-surface)",
                  color: "var(--md-sys-color-on-surface)",
                  textAlign: "left",
                  cursor: "pointer",
                  touchAction: "manipulation",
                }}
              >
                <span>
                  <span style={{ display: "block", fontSize: 18, fontWeight: 600 }}>{String(a.split)}</span>
                  <span style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
                    {String(a.session_count)} {Number(a.session_count) === 1 ? "session" : "sessions"} · last {fmtShortDate(String(a.last_date))}
                  </span>
                </span>
                <span className="material-symbols-rounded" aria-hidden style={{ color: "var(--md-sys-color-primary)" }}>
                  play_arrow
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          start(newName);
        }}
        style={{ display: "flex", gap: 8, alignItems: "center", borderTop: "1px solid var(--md-sys-color-outline-variant)", paddingTop: 16 }}
      >
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New workout type, e.g. Legs"
          aria-label="New workout type"
          style={{
            flex: 1,
            height: 44,
            padding: "0 12px",
            fontSize: 16,
            border: "1px solid var(--md-sys-color-outline-variant)",
            borderRadius: "var(--radius-input)",
            background: "var(--md-sys-color-surface)",
            color: "var(--md-sys-color-on-surface)",
            boxSizing: "border-box",
          }}
        />
        <button className="btn-filled" type="submit" disabled={starting || !newName.trim()} style={{ minHeight: 44 }}>
          Start
        </button>
      </form>
    </div>
  );
}

// ── Exercise row (overview) ───────────────────────────────────────────────────

export function ExerciseListRow({
  row,
  history,
  onOpen,
}: {
  row: ExerciseRow;
  history: HistoryRow[] | undefined;
  onOpen: () => void;
}) {
  const done = row.status === "done";
  return (
    <li>
      <button
        onClick={onOpen}
        aria-label={`${row.exercise}, ${done ? "completed" : "not completed yet"}`}
        style={{
          width: "100%",
          minHeight: 72,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 12px",
          background: "var(--md-sys-color-surface)",
          border: "1px solid var(--md-sys-color-outline-variant)",
          borderLeft: done
            ? "3px solid var(--md-sys-color-primary)"
            : "1px solid var(--md-sys-color-outline-variant)",
          borderRadius: 12,
          boxShadow: "var(--wt-card-shadow)",
          color: "var(--md-sys-color-on-surface)",
          textAlign: "left",
          cursor: "pointer",
          touchAction: "manipulation",
        }}
      >
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 16,
            fontWeight: done ? 600 : 500,
            lineHeight: 1.25,
            overflowWrap: "anywhere",
            color: done ? "var(--md-sys-color-on-surface)" : "var(--md-sys-color-on-surface-variant)",
          }}
        >
          {row.exercise}
        </span>
        <span style={{ flex: "0 0 40px", display: "flex", justifyContent: "center" }}>
          <DeltaChip delta={row.delta} completed={done} />
        </span>
        {history ? (
          <RepsChart rows={history} variant="mini" />
        ) : (
          <span style={{ width: MINI_CHART_W, height: 52, flexShrink: 0 }} aria-hidden />
        )}
      </button>
    </li>
  );
}

const actionBtn: React.CSSProperties = {
  flex: 1,
  minHeight: 48,
  border: "none",
  borderRadius: 14,
  fontSize: 16,
  fontWeight: 600,
  cursor: "pointer",
  touchAction: "manipulation",
};

// ── Active session overview ───────────────────────────────────────────────────

function ActiveOverview({ session, onEnded }: { session: ActiveSession; onEnded: () => void }) {
  const navigate = useNavigate();
  const [exercises, setExercises] = useState<ExerciseRow[] | null>(null);
  const [histories, setHistories] = useState<Record<string, HistoryRow[]>>({});
  const [error, setError] = useState<ApiError | null>(null);
  const [view, setView] = useState<{ kind: "overview" } | { kind: "exercise"; rowId: string | "new" }>(() => {
    const open = readOpen();
    return open && open.sessionId === session.id ? { kind: "exercise", rowId: open.rowId } : { kind: "overview" };
  });
  const [confirm, setConfirm] = useState<"finish" | "discard" | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);

  const loadHistory = useCallback(async (names: string[]) => {
    const results = await Promise.all(
      names.map((n) => apiFetch<Dataset>(`/workout/exercises/history?name=${encodeURIComponent(n)}`)),
    );
    setHistories((prev) => {
      const next = { ...prev };
      names.forEach((n, i) => {
        const r = results[i];
        if (!isApiError(r)) next[n.toLowerCase()] = r.rows as unknown as HistoryRow[];
      });
      return next;
    });
  }, []);

  useEffect(() => {
    apiFetch<Dataset>(`/workout/sessions/${session.id}/exercises`).then((res) => {
      if (isApiError(res)) return setError(res);
      const rows = res.rows as unknown as ExerciseRow[];
      setExercises(rows);
      loadHistory([...new Set(rows.map((r) => r.exercise))]);
    });
  }, [session.id, loadHistory]);

  function openExercise(rowId: string | "new") {
    writeOpen({ sessionId: session.id, rowId });
    setView({ kind: "exercise", rowId });
  }
  function closeExercise() {
    writeOpen(null);
    setView({ kind: "overview" });
  }

  function applyDataset(ds: Dataset) {
    const rows = ds.rows as unknown as ExerciseRow[];
    setExercises(rows);
    loadHistory([...new Set(rows.map((r) => r.exercise))]);
    closeExercise();
  }

  async function finish() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<Dataset>(`/workout/sessions/${session.id}/finish`, { method: "POST" });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      setConfirm(null);
      lock.current = false;
      return;
    }
    writeOpen(null);
    onEnded();
    navigate("/workout/log");
  }

  async function discard() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<unknown>(`/workout/sessions/${session.id}`, { method: "DELETE" });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      setConfirm(null);
      lock.current = false;
      return;
    }
    writeOpen(null);
    onEnded();
  }

  if (view.kind === "exercise" && exercises) {
    const row = view.rowId === "new" ? undefined : exercises.find((e) => e.id === view.rowId);
    if (view.rowId === "new" || row) {
      return (
        <ExerciseLogView
          sessionId={session.id}
          sessionDate={session.workout_date}
          row={row}
          live
          onSynced={(ds) => setExercises(ds.rows as unknown as ExerciseRow[])}
          onRowCreated={(id) => {
            writeOpen({ sessionId: session.id, rowId: id });
            setView({ kind: "exercise", rowId: id });
          }}
          onSaved={applyDataset}
          onCancel={closeExercise}
          onDeleted={applyDataset}
        />
      );
    }
    // Remembered exercise no longer exists (deleted elsewhere) — fall through to the overview.
    writeOpen(null);
  }

  const planned = exercises?.filter((e) => e.status === "planned").length ?? 0;
  const done = exercises?.filter((e) => e.status === "done").length ?? 0;

  const finishBody =
    done === 0
      ? "Nothing has been logged yet, so this workout will be discarded."
      : `${planned} exercise${planned === 1 ? "" : "s"} not logged will be removed from this workout.`;

  return (
    <div className="page" style={{ gap: 10, paddingBottom: 0 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <h1 className="type-display" style={{ margin: 0 }}>
            {session.split}
          </h1>
          <p style={{ margin: "2px 0 0", fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}>
            {fmtLongDate(session.workout_date)}
          </p>
        </div>
        <button
          className="btn-text"
          style={{ minHeight: 44, padding: "0 8px", fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}
          onClick={() => setConfirm("discard")}
        >
          Discard
        </button>
      </div>

      {error && <ErrorCard error={error} />}
      {exercises === null && !error && <p className="type-body">Loading…</p>}
      {exercises && exercises.length === 0 && (
        <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
          No exercises yet. Add the first one below.
        </p>
      )}

      {exercises && exercises.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {exercises.map((row) => (
            <ExerciseListRow
              key={row.id}
              row={row}
              history={histories[row.exercise.toLowerCase()]}
              onOpen={() => openExercise(row.id)}
            />
          ))}
        </ul>
      )}

      <div
        style={{
          position: "sticky",
          bottom: 0,
          display: "flex",
          gap: 10,
          margin: "0 -12px",
          padding: "10px 12px",
          background: "var(--md-sys-color-background)",
          borderTop: "1px solid var(--md-sys-color-outline-variant)",
        }}
      >
        <button
          style={{ ...actionBtn, background: "var(--md-sys-color-primary-container)", color: "var(--md-sys-color-primary)" }}
          onClick={() => openExercise("new")}
        >
          + Add Exercise
        </button>
        <button
          style={{ ...actionBtn, background: "var(--md-sys-color-primary)", color: "var(--md-sys-color-on-primary)" }}
          disabled={busy || exercises === null}
          onClick={() => (planned > 0 || done === 0 ? setConfirm("finish") : finish())}
        >
          Finish Workout
        </button>
      </div>

      <ConfirmDialog
        open={confirm === "finish"}
        title="Finish workout?"
        body={finishBody}
        confirmLabel="Finish"
        danger={false}
        busy={busy}
        onConfirm={finish}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "discard"}
        title="Discard this workout?"
        body="Everything logged in this workout will be permanently removed. Earlier sessions are not affected."
        confirmLabel="Discard"
        busy={busy}
        onConfirm={discard}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}

// ── Local date (client time is the authority for "today"; see start_session) ──

export function localDate(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// ── SessionView ───────────────────────────────────────────────────────────────

export default function SessionView() {
  const [active, setActive] = useState<ActiveSession | null | undefined>(undefined); // undefined = loading
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    apiFetch<Dataset>("/workout/sessions/active").then((res) => {
      if (isApiError(res)) return setError(res);
      setActive(res.rows[0] ? (res.rows[0] as unknown as ActiveSession) : null);
    });
  }, []);

  if (error) return <div className="page"><ErrorCard error={error} /></div>;
  if (active === undefined) return <div className="page"><p className="type-body">Loading…</p></div>;
  if (active === null) return <ArchetypeChooser onStarted={setActive} />;
  return <ActiveOverview session={active} onEnded={() => setActive(null)} />;
}
