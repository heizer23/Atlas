/**
 * SessionDetailView — a finished session, opened from the Log or from an exercise history
 * (route /workout/log/:sessionId).
 *
 * Read-only by default: opening a session or an exercise from here never modifies anything.
 * Changing a past record needs the explicit "Edit" action. Repeat starts a NEW workout (after
 * confirmation) and Delete removes this session (after confirmation).
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import ExerciseLogView from "./ExerciseLogView";
import { localDate } from "./SessionView";
import {
  ConfirmDialog,
  DeltaChip,
  SetBlocks,
  fmtDate,
  fmtWeight,
  historyPath,
  setsOf,
  totalOf,
  useGoBack,
  type ExerciseRow,
} from "./workoutShared";

const smallBtn: React.CSSProperties = {
  minHeight: 44,
  padding: "0 14px",
  border: "none",
  borderRadius: 12,
  fontSize: 15,
  fontWeight: 600,
  cursor: "pointer",
  touchAction: "manipulation",
};

export default function SessionDetailView() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const goBack = useGoBack("/workout/log");

  const [rows, setRows] = useState<ExerciseRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [editing, setEditing] = useState(false);
  const [openRow, setOpenRow] = useState<ExerciseRow | "new" | null>(null);
  const [confirm, setConfirm] = useState<"repeat" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);

  useEffect(() => {
    setRows(null);
    setError(null);
    apiFetch<Dataset>(`/workout/sessions/${sessionId}/exercises`).then((res) => {
      if (isApiError(res)) return setError(res);
      setRows(res.rows as unknown as ExerciseRow[]);
    });
  }, [sessionId]);

  const first = rows?.[0];
  const split = first?.split ?? "";
  const date = first?.workout_date ?? "";

  async function repeat() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<Dataset>("/workout/sessions/start", {
      method: "POST",
      body: JSON.stringify({ split, from_session_id: sessionId, workout_date: localDate() }),
    });
    if (isApiError(res)) {
      setError(
        res.error.code === "ACTIVE_SESSION_EXISTS"
          ? { error: { ...res.error, message: "A workout is already in progress. Finish or discard it first." } }
          : res,
      );
      setBusy(false);
      setConfirm(null);
      lock.current = false;
      return;
    }
    navigate("/workout");
  }

  async function remove() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<unknown>(`/workout/sessions/${sessionId}`, { method: "DELETE" });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      setConfirm(null);
      lock.current = false;
      return;
    }
    navigate("/workout/log", { replace: true });
  }

  // Explicit editing workflow: the existing exercise editor, saving into THIS session.
  if (openRow) {
    return (
      <ExerciseLogView
        sessionId={sessionId}
        sessionDate={date}
        row={openRow === "new" ? undefined : openRow}
        onSaved={(ds) => {
          setRows(ds.rows as unknown as ExerciseRow[]);
          setOpenRow(null);
        }}
        onCancel={() => setOpenRow(null)}
        onDeleted={(ds) => {
          setRows(ds.rows as unknown as ExerciseRow[]);
          setOpenRow(null);
        }}
      />
    );
  }

  return (
    <div className="page" style={{ gap: 10 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 4, marginLeft: -6 }}>
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={goBack} aria-label="Back">
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <div style={{ minWidth: 0, paddingTop: 4 }}>
          <h1 className="type-display" style={{ margin: 0 }}>
            {split || "Session"}
          </h1>
          {date && (
            <p style={{ margin: "2px 0 0", fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}>{fmtDate(date)}</p>
          )}
        </div>
      </div>

      {error && <ErrorCard error={error} />}
      {rows === null && !error && <p className="type-body">Loading…</p>}

      {rows && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              style={{ ...smallBtn, background: "var(--md-sys-color-primary-container)", color: "var(--md-sys-color-primary)" }}
              onClick={() => setConfirm("repeat")}
            >
              Repeat
            </button>
            <button
              style={{
                ...smallBtn,
                background: editing ? "var(--md-sys-color-primary)" : "transparent",
                color: editing ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-primary)",
                border: editing ? "none" : "1px solid var(--md-sys-color-outline-variant)",
              }}
              aria-pressed={editing}
              onClick={() => setEditing((e) => !e)}
            >
              {editing ? "Done editing" : "Edit"}
            </button>
            <button style={{ ...smallBtn, background: "transparent", color: "var(--md-sys-color-error)" }} onClick={() => setConfirm("delete")}>
              Delete
            </button>
          </div>

          {editing && (
            <p
              role="status"
              style={{
                margin: 0,
                padding: "8px 12px",
                borderRadius: 10,
                fontSize: 13,
                background: "var(--md-sys-color-primary-container)",
                color: "var(--md-sys-color-on-surface)",
              }}
            >
              Editing a past workout. Tap an exercise to change it; changes are saved into this session.
            </p>
          )}

          {rows.length === 0 && <p className="type-body">No exercises recorded.</p>}

          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((r) => {
              const sets = setsOf(r);
              const done = r.status === "done";
              return (
                <li
                  key={r.id}
                  style={{
                    background: "var(--md-sys-color-surface)",
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
                      onClick={() => (editing ? setOpenRow(r) : navigate(historyPath(r.exercise)))}
                      aria-label={editing ? `Edit ${r.exercise}` : `${r.exercise}, open history`}
                      style={{
                        flex: 1,
                        minWidth: 0,
                        minHeight: 40,
                        padding: 0,
                        border: "none",
                        background: "transparent",
                        textAlign: "left",
                        fontSize: 16,
                        fontWeight: 600,
                        lineHeight: 1.25,
                        overflowWrap: "anywhere",
                        color: "var(--md-sys-color-on-surface)",
                        cursor: "pointer",
                      }}
                    >
                      {r.exercise}
                    </button>
                    <DeltaChip delta={r.delta} completed={done} />
                    {editing && (
                      <span className="material-symbols-rounded" aria-hidden style={{ color: "var(--md-sys-color-primary)", fontSize: 20 }}>
                        edit
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
                    {fmtWeight(r.weight_kg)} · {sets.filter((v) => v != null).length} sets · {totalOf(r)} reps
                  </div>
                  {totalOf(r) > 0 && <SetBlocks sets={sets} />}
                  {r.comment && r.comment.trim() && (
                    <p style={{ margin: 0, fontSize: 14, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{r.comment}</p>
                  )}
                </li>
              );
            })}
          </ul>

          {editing && (
            <button
              style={{ ...smallBtn, background: "var(--md-sys-color-primary-container)", color: "var(--md-sys-color-primary)", minHeight: 48 }}
              onClick={() => setOpenRow("new")}
            >
              + Add Exercise
            </button>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirm === "repeat"}
        title={`Start ${split} again?`}
        body="This starts a new workout with the same exercises and starting weights. Nothing from this session is copied as a result."
        confirmLabel="Start workout"
        danger={false}
        busy={busy}
        onConfirm={repeat}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "delete"}
        title="Delete this session?"
        body="The session and its exercises, sets and comments are permanently removed. Other sessions and the workout type are not affected."
        confirmLabel="Delete"
        busy={busy}
        onConfirm={remove}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
