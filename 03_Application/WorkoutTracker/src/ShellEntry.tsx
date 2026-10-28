/**
 * WorkoutTracker ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 * All platform imports use the @platform-ui alias.
 *
 * Routes covered:
 *   /workout              → Session tab (archetype chooser / active workout)   — SessionView.tsx
 *   /workout/log          → Log tab (finished sessions)
 *   /workout/performance  → Performance view
 *   /workout/settings     → Settings view
 */

import { useState, useEffect, useRef } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import { useDataset } from "@platform-ui/hooks/useDataset";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { Row, Dataset, ApiError } from "@platform-ui/api/types";
import SessionView, { ExerciseListRow, localDate } from "./SessionView";
import ExerciseLogView from "./ExerciseLogView";
import { ConfirmDialog, type ExerciseRow, type HistoryRow } from "./workoutShared";
import "./workout.css";

// ── Types ─────────────────────────────────────────────────────────────────────

type ExerciseProgress = { exercise: string; total_reps: number; delta: number | null };

// ── RepChip ───────────────────────────────────────────────────────────────────
// Renders a colored delta pill for rep-progress comparison.
// delta > 0 → blue; delta < 0 → red; delta === 0 or null → grey outline.

function RepChip({ delta, chipLabel }: { delta: number | null; chipLabel?: string }) {
  const isPositive = delta !== null && delta > 0;
  const isNegative = delta !== null && delta < 0;

  const displayLabel =
    chipLabel !== undefined ? chipLabel
    : delta === null ? "—"
    : delta > 0      ? `+${delta}`
    : delta < 0      ? `−${Math.abs(delta)}`
    : "—";

  const chipStyle: React.CSSProperties = {
    flexShrink: 0,
    height: 20,
    borderRadius: 10,
    padding: "0 7px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: ".3px",
    whiteSpace: "nowrap",
    ...(isPositive
      ? { background: "color-mix(in srgb, var(--md-sys-color-primary) 16%, transparent)", color: "var(--md-sys-color-primary)" }
      : isNegative
      ? { background: "var(--md-sys-color-error)", color: "var(--md-sys-color-on-error)" }
      : {
          background: "transparent",
          border: "1px solid var(--md-sys-color-outline-variant)",
          color: "var(--md-sys-color-on-surface-variant)",
        }),
  };

  return <div style={chipStyle}>{displayLabel}</div>;
}

// ── SessionList ───────────────────────────────────────────────────────────────

interface SessionListProps {
  dataset: Dataset | null;
  progressBySession: Record<string, ExerciseProgress[]>;
  onRowClick: (row: Row) => void;
  onDelete: (id: string) => void;
  onCopy: (row: Row) => void;
}

function SessionList({
  dataset,
  progressBySession,
  onRowClick,
  onDelete,
  onCopy,
}: SessionListProps) {
  const [openMenu, setOpenMenu] = useState<{ id: string; rect: DOMRect } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  if (!dataset)
    return <p className="type-body">Loading…</p>;
  if (dataset.rows.length === 0)
    return <p className="type-body">No sessions yet.</p>;

  function fmtDate(val: unknown) {
    const d = new Date(String(val));
    return isNaN(d.getTime())
      ? String(val)
      : d.toLocaleDateString(undefined, { dateStyle: "medium" });
  }

  return (
    <div
      ref={listRef}
      style={{
        background: "var(--md-sys-color-surface)",
        borderRadius: 12,
        boxShadow: "0px 1px 2px rgba(0,0,0,.3), 0px 1px 3px 1px rgba(0,0,0,.15)",
        overflow: "hidden",
        marginTop: 16,
      }}
    >
      {dataset.rows.map((row) => (
        <div
          key={row.id}
          onClick={() => {
            setOpenMenu(null);
            onRowClick(row);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            padding: "14px 16px",
            borderBottom: "1px solid var(--md-sys-color-outline-variant)",
            gap: 12,
            cursor: "pointer",
            position: "relative",
            transition: "background 200ms",
            background: "transparent",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "color-mix(in srgb, var(--md-sys-color-primary) 8%, transparent)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "transparent")
          }
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 16,
                fontWeight: 500,
                color: "var(--md-sys-color-on-surface)",
                letterSpacing: ".15px",
              }}
            >
              {String(row.split ?? "")}
            </div>
            <div
              style={{
                fontSize: 14,
                color: "var(--md-sys-color-on-surface-variant)",
                letterSpacing: ".25px",
              }}
            >
              {fmtDate(row.workout_date)}
            </div>
            {(progressBySession[row.id] ?? []).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
                {(progressBySession[row.id] ?? []).map((ex) => (
                  <RepChip key={ex.exercise} delta={ex.delta} chipLabel={ex.exercise} />
                ))}
              </div>
            )}
          </div>

          <div
            style={{
              flexShrink: 0,
              background: "var(--md-sys-color-surface-variant)",
              borderRadius: 12,
              padding: "2px 10px",
              fontSize: 12,
              color: "var(--md-sys-color-on-surface-variant)",
            }}
          >
            {String(row.exercise_count)} ex
          </div>

          <div
            style={{ flexShrink: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={(e) => {
                const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
                setOpenMenu(openMenu?.id === row.id ? null : { id: row.id, rect });
              }}
              style={{
                width: 40,
                height: 40,
                border: "none",
                borderRadius: "50%",
                background: "transparent",
                color: "var(--md-sys-color-on-surface-variant)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              aria-label="More options"
            >
              <span
                className="material-symbols-rounded"
                style={{ fontSize: 24 }}
              >
                more_vert
              </span>
            </button>

            {openMenu?.id === row.id && openMenu.rect && (
              <div
                style={{
                  position: "fixed",
                  top: openMenu.rect.bottom + 4,
                  right: window.innerWidth - openMenu.rect.right,
                  minWidth: 160,
                  background: "var(--md-sys-color-surface-variant)",
                  borderRadius: 4,
                  boxShadow:
                    "0 2px 6px 2px rgba(0,0,0,.15), 0 1px 2px rgba(0,0,0,.3)",
                  padding: "8px 0",
                  zIndex: 1000,
                }}
              >
                <div
                  onClick={() => {
                    setOpenMenu(null);
                    onCopy(row);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "0 12px",
                    height: 48,
                    fontSize: 14,
                    fontWeight: 400,
                    letterSpacing: ".25px",
                    color: "var(--md-sys-color-on-surface)",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "rgba(28,27,31,.08)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <span
                    className="material-symbols-rounded"
                    style={{ fontSize: 18, color: "var(--md-sys-color-on-surface-variant)" }}
                  >
                    replay
                  </span>
                  Repeat
                </div>
                <div
                  style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "4px 0" }}
                />
                <div
                  onClick={() => {
                    setOpenMenu(null);
                    onDelete(row.id);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "0 12px",
                    height: 48,
                    fontSize: 14,
                    fontWeight: 400,
                    letterSpacing: ".25px",
                    color: "var(--md-sys-color-error)",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "rgba(28,27,31,.08)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <span
                    className="material-symbols-rounded"
                    style={{ fontSize: 18, color: "var(--md-sys-color-error)" }}
                  >
                    delete
                  </span>
                  Delete
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── LogView (finished sessions — /workout/log) ────────────────────────────────

function LogView() {
  const navigate = useNavigate();

  const [selectedSession, setSelectedSession] = useState<Row | null>(null);
  const [selectedExercise, setSelectedExercise] = useState<ExerciseRow | "new" | null>(null);
  const [exercises, setExercises] = useState<ExerciseRow[] | null>(null);
  const [histories, setHistories] = useState<Record<string, HistoryRow[]>>({});
  const [exerciseError, setExerciseError] = useState<ApiError | null>(null);
  const [mutateError, setMutateError] = useState<ApiError | null>(null);
  const [progressBySession, setProgressBySession] = useState<Record<string, ExerciseProgress[]>>({});
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const { dataset: sessionDataset, error: sessionError, refresh: refreshSessions } =
    useDataset("/workout/sessions");

  useEffect(() => {
    if (!sessionDataset) return;
    sessionDataset.rows.forEach((row) => {
      apiFetch<Dataset>(`/workout/sessions/${row.id}/progress`).then((res) => {
        if (!isApiError(res)) {
          setProgressBySession((prev) => ({
            ...prev,
            [row.id]: res.rows.map((r) => ({
              exercise: r.exercise as string,
              total_reps: r.total_reps as number,
              delta: r.delta != null ? (r.delta as number) : null,
            })),
          }));
        }
      });
    });
  }, [sessionDataset]);

  async function loadHistories(rows: ExerciseRow[]) {
    const names = [...new Set(rows.map((r) => r.exercise))];
    const results = await Promise.all(
      names.map((n) => apiFetch<Dataset>(`/workout/exercises/history?name=${encodeURIComponent(n)}`)),
    );
    const map: Record<string, HistoryRow[]> = {};
    names.forEach((n, i) => {
      const r = results[i];
      if (!isApiError(r)) map[n.toLowerCase()] = r.rows as unknown as HistoryRow[];
    });
    setHistories(map);
  }

  async function openSession(row: Row) {
    setSelectedSession(row);
    setExercises(null);
    setHistories({});
    setExerciseError(null);
    const res = await apiFetch<Dataset>(`/workout/sessions/${row.id}/exercises`);
    if (isApiError(res)) return setExerciseError(res);
    const rows = res.rows as unknown as ExerciseRow[];
    setExercises(rows);
    loadHistories(rows);
  }

  function applyDataset(ds: Dataset) {
    const rows = ds.rows as unknown as ExerciseRow[];
    setExercises(rows);
    loadHistories(rows);
    setSelectedExercise(null);
  }

  async function handleSessionDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<unknown>(`/workout/sessions/${id}`, { method: "DELETE" });
    setConfirmDelete(null);
    if (isApiError(res)) {
      setMutateError(res);
      return;
    }
    refreshSessions();
  }

  // Repeat: new session from this one as a template (exercises + starting weights, no results).
  async function handleSessionRepeat(row: Row) {
    setMutateError(null);
    const res = await apiFetch<Dataset>("/workout/sessions/start", {
      method: "POST",
      body: JSON.stringify({ split: row.split, from_session_id: row.id, workout_date: localDate() }),
    });
    if (isApiError(res)) {
      setMutateError(
        res.error.code === "ACTIVE_SESSION_EXISTS"
          ? { error: { ...res.error, message: "A workout is already in progress. Finish or discard it first." } }
          : res,
      );
      return;
    }
    navigate("/workout");
  }

  if (selectedSession && selectedExercise) {
    return (
      <ExerciseLogView
        sessionId={selectedSession.id}
        sessionDate={String(selectedSession.workout_date)}
        row={selectedExercise === "new" ? undefined : selectedExercise}
        onSaved={applyDataset}
        onCancel={() => setSelectedExercise(null)}
        onDeleted={applyDataset}
      />
    );
  }

  if (selectedSession) {
    return (
      <div className="page">
        <div className="page-toolbar">
          <button
            className="icon-btn"
            aria-label="Back to sessions"
            onClick={() => {
              setSelectedSession(null);
              setExercises(null);
              setExerciseError(null);
              refreshSessions();
            }}
          >
            <span className="material-symbols-rounded">arrow_back</span>
          </button>
          <h1 className="type-headline">
            {String(selectedSession.split)} — {String(selectedSession.workout_date)}
          </h1>
        </div>

        {exerciseError && <ErrorCard error={exerciseError} />}
        {exercises === null && !exerciseError && <p className="type-body">Loading…</p>}

        {exercises && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {exercises.map((row) => (
              <ExerciseListRow
                key={row.id}
                row={row}
                history={histories[row.exercise.toLowerCase()]}
                onOpen={() => setSelectedExercise(row)}
              />
            ))}
          </ul>
        )}
        <button className="btn-outlined" style={{ minHeight: 48 }} onClick={() => setSelectedExercise("new")}>
          + Add Exercise
        </button>
      </div>
    );
  }

  if (sessionError) return <ErrorCard error={sessionError} />;

  return (
    <div className="page">
      <h1 className="type-display" style={{ margin: 0 }}>
        Log
      </h1>

      {mutateError && <ErrorCard error={mutateError} />}

      <SessionList
        dataset={sessionDataset}
        progressBySession={progressBySession}
        onRowClick={openSession}
        onDelete={(id) => setConfirmDelete(id)}
        onCopy={handleSessionRepeat}
      />

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete this session?"
        body="The session and all its exercises, sets and comments are permanently removed. Exercise history for other sessions is not affected."
        confirmLabel="Delete"
        onConfirm={() => confirmDelete && handleSessionDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}

// ── Placeholder views for Performance, Settings ──────────────────────

function PerformanceView() {
  return (
    <div className="page">
      <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
        Performance analytics coming soon.
      </p>
    </div>
  );
}

function SettingsView() {
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);
  const [activeId, setActiveId] = useState<string | null>(
    () => localStorage.getItem("workout_reminder_id")
  );
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function scheduleReminder() {
    setLoading(true);
    setStatusMsg(null);
    try {
      const tokenRes = await fetch("/api/devices/token?device_id=default");
      if (!tokenRes.ok) {
        setStatusMsg("No device registered. Open AtlasPhone on your phone first.");
        return;
      }
      const { token } = await tokenRes.json();

      const now = new Date();
      const fireAt = new Date();
      fireAt.setHours(hour, minute, 0, 0);
      if (fireAt <= now) fireAt.setDate(fireAt.getDate() + 1);

      if (activeId) {
        await fetch(`/api/notifications/${activeId}`, { method: "DELETE" });
      }

      const pad = (n: number) => String(n).padStart(2, "0");
      const res = await fetch("/api/notifications/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "workouttracker",
          fire_at: fireAt.toISOString(),
          title: "Time to train",
          body: `Daily workout reminder at ${pad(hour)}:${pad(minute)}`,
          label: "workout_reminder",
          deep_link: "atlas://workout",
          fcm_token: token,
        }),
      });
      if (!res.ok) {
        setStatusMsg("Failed to schedule reminder.");
        return;
      }
      const record = await res.json();
      setActiveId(record.id);
      localStorage.setItem("workout_reminder_id", record.id);
      const pad2 = (n: number) => String(n).padStart(2, "0");
      setStatusMsg(`Reminder set for ${pad2(hour)}:${pad2(minute)} — fires ${fireAt.toLocaleDateString()}`);
    } catch (e) {
      setStatusMsg("Error: " + String(e));
    } finally {
      setLoading(false);
    }
  }

  async function clearReminder() {
    if (!activeId) return;
    setLoading(true);
    try {
      await fetch(`/api/notifications/${activeId}`, { method: "DELETE" });
      setActiveId(null);
      localStorage.removeItem("workout_reminder_id");
      setStatusMsg("Reminder cleared.");
    } catch (e) {
      setStatusMsg("Error clearing: " + String(e));
    } finally {
      setLoading(false);
    }
  }

  const selectStyle: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: 8,
    background: "var(--md-sys-color-surface-variant)",
    border: "none",
    color: "var(--md-sys-color-on-surface)",
    fontSize: 16,
  };

  return (
    <div className="page">
      <div>
        <h2 className="type-title" style={{ marginBottom: 4 }}>Daily Workout Reminder</h2>
        <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)", marginBottom: 16 }}>
          Push notification to your phone at a set time each day.
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
          <select value={hour} onChange={e => setHour(Number(e.target.value))} style={selectStyle}>
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>{String(i).padStart(2, "0")}</option>
            ))}
          </select>
          <span className="type-body">:</span>
          <select value={minute} onChange={e => setMinute(Number(e.target.value))} style={selectStyle}>
            {Array.from({ length: 60 }, (_, m) => (
              <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button
            onClick={scheduleReminder}
            disabled={loading}
            style={{ padding: "10px 20px", borderRadius: 20, background: "var(--md-sys-color-primary)", color: "var(--md-sys-color-on-primary)", border: "none", cursor: loading ? "default" : "pointer", fontSize: 14 }}
          >
            {loading ? "Saving..." : activeId ? "Update Reminder" : "Set Reminder"}
          </button>
          {activeId && (
            <button
              onClick={clearReminder}
              disabled={loading}
              style={{ padding: "10px 20px", borderRadius: 20, background: "var(--md-sys-color-surface-variant)", color: "var(--md-sys-color-on-surface)", border: "none", cursor: loading ? "default" : "pointer", fontSize: 14 }}
            >
              Clear
            </button>
          )}
        </div>
        {statusMsg && (
          <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>{statusMsg}</p>
        )}
      </div>
    </div>
  );
}

// ── ShellEntry — default export ───────────────────────────────────────────────

/**
 * Renders nested <Routes> for the WorkoutTracker application.
 * No BrowserRouter — inherits the shell's router context.
 */
export default function ShellEntry() {
  // Scope the Workout visual theme (workout.css) to this app while it is mounted.
  useEffect(() => {
    document.body.dataset.app = "workout";
    return () => {
      delete document.body.dataset.app;
    };
  }, []);

  return (
    <Routes>
      <Route path="/" element={<SessionView />} />
      <Route path="/log" element={<LogView />} />
      <Route path="/performance" element={<PerformanceView />} />
      <Route path="/settings" element={<SettingsView />} />
    </Routes>
  );
}
