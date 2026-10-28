/**
 * LogView — finished sessions, newest first (route /workout/log).
 *
 * Browsing only: opening a session or an exercise never creates or modifies a workout.
 * Filter chips use the archetypes actually in the data. On a session card, swipe right = Repeat
 * (starts a NEW workout, after confirmation), swipe left = Delete (after confirmation). The same
 * actions are available as buttons on the session screen.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import { localDate } from "./SessionView";
import { ConfirmDialog, fmtDate, historyPath, repsSummary, setsOf } from "./workoutShared";

const PAGE_SIZE = 15;
const SWIPE_THRESHOLD = 88;

interface LogExercise {
  id: string;
  exercise: string;
  weight_kg: number | null;
  set1_reps: number | null;
  set2_reps: number | null;
  set3_reps: number | null;
  set4_reps: number | null;
  set5_reps: number | null;
  delta: number | null;
}

interface LogSession {
  id: string;
  workout_date: string;
  split: string;
  exercises: LogExercise[];
}

// ── Swipe ─────────────────────────────────────────────────────────────────────

function SwipeableCard({
  onRepeat,
  onDelete,
  children,
}: {
  onRepeat: () => void;
  onDelete: () => void;
  children: React.ReactNode;
}) {
  const [dx, setDx] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ x: number; y: number } | null>(null);
  const active = useRef(false);
  const suppressClick = useRef(false);
  const lastDx = useRef(0);

  function onPointerDown(e: React.PointerEvent) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    start.current = { x: e.clientX, y: e.clientY };
    active.current = false;
    suppressClick.current = false;
  }

  function onPointerMove(e: React.PointerEvent) {
    const s = start.current;
    if (!s) return;
    const ddx = e.clientX - s.x;
    const ddy = e.clientY - s.y;
    if (!active.current) {
      if (Math.abs(ddx) > 10 && Math.abs(ddx) > Math.abs(ddy) * 1.5) {
        active.current = true;
        setDragging(true);
        try {
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        } catch {
          /* ignore */
        }
      } else if (Math.abs(ddy) > 10) {
        start.current = null; // vertical scroll, not ours
        return;
      }
    }
    if (active.current) {
      const v = Math.max(-140, Math.min(140, ddx));
      lastDx.current = v;
      setDx(v);
    }
  }

  function finish() {
    const wasActive = active.current;
    const d = lastDx.current;
    start.current = null;
    active.current = false;
    lastDx.current = 0;
    setDragging(false);
    setDx(0);
    if (wasActive) {
      suppressClick.current = true; // the click that follows a drag must not open anything
      if (d >= SWIPE_THRESHOLD) onRepeat();
      else if (d <= -SWIPE_THRESHOLD) onDelete();
    }
  }

  return (
    <div
      style={{
        position: "relative",
        borderRadius: 12,
        overflow: "hidden",
        touchAction: "pan-y",
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={finish}
      onClickCapture={(e) => {
        if (suppressClick.current) {
          e.stopPropagation();
          e.preventDefault();
          suppressClick.current = false;
        }
      }}
    >
      {/* action backgrounds, revealed by the swipe */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: dx >= 0 ? "flex-start" : "flex-end",
          padding: "0 20px",
          fontSize: 15,
          fontWeight: 700,
          color: "#fff",
          background: dx >= 0 ? "var(--md-sys-color-primary)" : "var(--md-sys-color-error)",
          opacity: Math.min(1, Math.abs(dx) / 40),
        }}
      >
        {dx >= 0 ? "Repeat" : "Delete"}
      </div>
      <div
        style={{
          position: "relative",
          transform: `translateX(${dx}px)`,
          transition: dragging ? "none" : "transform 160ms ease-out",
        }}
      >
        {children}
      </div>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function statusDot(delta: number | null): { color: string; hollow: boolean; label: string } {
  if (delta == null) return { color: "var(--md-sys-color-outline-variant)", hollow: true, label: "no comparable previous result" };
  if (delta > 0) return { color: "var(--md-sys-color-primary)", hollow: false, label: `${delta} more reps than last time` };
  if (delta < 0) return { color: "var(--md-sys-color-error)", hollow: false, label: `${Math.abs(delta)} fewer reps than last time` };
  return { color: "var(--md-sys-color-outline)", hollow: false, label: "same reps as last time" };
}

function SessionCard({ s, onOpenSession, onOpenExercise }: { s: LogSession; onOpenSession: () => void; onOpenExercise: (name: string) => void }) {
  return (
    <article
      aria-label={`${s.split}, ${fmtDate(s.workout_date)}`}
      style={{
        display: "grid",
        gridTemplateColumns: "92px minmax(0, 1fr)",
        gap: 8,
        padding: "10px 12px",
        background: "var(--md-sys-color-surface)",
        border: "1px solid var(--md-sys-color-outline-variant)",
        borderRadius: 12,
      }}
    >
      <button
        type="button"
        onClick={onOpenSession}
        aria-label={`Open ${s.split} session from ${fmtDate(s.workout_date)}`}
        style={{
          alignSelf: "start",
          padding: "4px 0",
          minHeight: 44,
          border: "none",
          background: "transparent",
          textAlign: "left",
          cursor: "pointer",
          color: "var(--md-sys-color-on-surface)",
        }}
      >
        <span style={{ display: "block", fontSize: 15, fontWeight: 700, lineHeight: 1.25 }}>{fmtDate(s.workout_date)}</span>
        <span style={{ display: "block", fontSize: 13, color: "var(--md-sys-color-on-surface-variant)", overflowWrap: "anywhere" }}>
          {s.split}
        </span>
      </button>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {s.exercises.length === 0 && (
          <li style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)", padding: "8px 0" }}>No exercises recorded</li>
        )}
        {s.exercises.map((e) => {
          const dot = statusDot(e.delta);
          const sets = setsOf(e);
          return (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => onOpenExercise(e.exercise)}
                aria-label={`${e.exercise}, ${repsSummary(sets)}, ${dot.label}, open history`}
                style={{
                  width: "100%",
                  minHeight: 36,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "3px 0",
                  border: "none",
                  background: "transparent",
                  textAlign: "left",
                  cursor: "pointer",
                  color: "var(--md-sys-color-on-surface)",
                }}
              >
                <span aria-hidden style={{ flexShrink: 0, width: 9, height: 9, borderRadius: "50%", boxSizing: "border-box", background: dot.hollow ? "transparent" : dot.color, border: `1.5px solid ${dot.color}` }} />
                <span style={{ flex: 1, minWidth: 0, fontSize: 14, lineHeight: 1.25, overflowWrap: "anywhere" }}>{e.exercise}</span>
                <span style={{ flexShrink: 0, fontSize: 13, fontVariantNumeric: "tabular-nums", color: "var(--md-sys-color-on-surface-variant)" }}>
                  {repsSummary(sets)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

// ── View ──────────────────────────────────────────────────────────────────────

export default function LogView() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const split = params.get("split") ?? "";

  const [archetypes, setArchetypes] = useState<string[]>([]);
  const [sessions, setSessions] = useState<LogSession[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "repeat" | "delete"; s: LogSession } | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);

  useEffect(() => {
    apiFetch<Dataset>("/workout/archetypes").then((res) => {
      if (!isApiError(res)) setArchetypes(res.rows.map((r) => String(r.split)));
    });
  }, []);

  const load = useCallback(
    async (p: number, append: boolean) => {
      const q = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE), include_exercises: "true" });
      if (split) q.set("split", split);
      const res = await apiFetch<Dataset>(`/workout/sessions?${q}`);
      if (isApiError(res)) return setError(res);
      const rows = res.rows as unknown as LogSession[];
      setSessions((prev) => (append && prev ? [...prev, ...rows] : rows));
      setTotal(res.meta.total);
      setPage(p);
    },
    [split],
  );

  useEffect(() => {
    setSessions(null);
    setError(null);
    load(1, false);
  }, [load]);

  async function repeat(s: LogSession) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<Dataset>("/workout/sessions/start", {
      method: "POST",
      body: JSON.stringify({ split: s.split, from_session_id: s.id, workout_date: localDate() }),
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

  async function remove(s: LogSession) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    const res = await apiFetch<unknown>(`/workout/sessions/${s.id}`, { method: "DELETE" });
    setBusy(false);
    setConfirm(null);
    lock.current = false;
    if (isApiError(res)) return setError(res);
    setSessions((prev) => (prev ? prev.filter((x) => x.id !== s.id) : prev));
    setTotal((t) => Math.max(0, t - 1));
  }

  const chip = (label: string, value: string) => {
    const on = split.toLowerCase() === value.toLowerCase();
    return (
      <button
        key={label}
        type="button"
        aria-pressed={on}
        onClick={() => setParams(value ? { split: value } : {}, { replace: true })}
        style={{
          flexShrink: 0,
          minHeight: 40,
          padding: "0 16px",
          border: on ? "none" : "1px solid var(--md-sys-color-outline-variant)",
          borderRadius: 20,
          fontSize: 15,
          fontWeight: 600,
          cursor: "pointer",
          background: on ? "var(--md-sys-color-primary)" : "var(--md-sys-color-surface)",
          color: on ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-on-surface)",
        }}
      >
        {label}
      </button>
    );
  };

  return (
    <div className="page" style={{ gap: 10 }}>
      <h1 className="type-display" style={{ margin: 0 }}>
        Log
      </h1>

      <div
        role="group"
        aria-label="Filter by workout type"
        style={{ display: "flex", gap: 8, overflowX: "auto", margin: "0 -12px", padding: "0 12px 2px", scrollbarWidth: "none" }}
      >
        {chip("All", "")}
        {archetypes.map((a) => chip(a, a))}
      </div>

      {error && <ErrorCard error={error} />}
      {sessions === null && !error && <p className="type-body">Loading…</p>}

      {sessions && (
        <p style={{ margin: 0, fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
          {split || "All"} · {total} {total === 1 ? "session" : "sessions"}
        </p>
      )}

      {sessions && sessions.length === 0 && (
        <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
          No sessions{split ? ` for ${split}` : ""} yet.
        </p>
      )}

      {sessions && sessions.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {sessions.map((s) => (
            <li key={s.id}>
              <SwipeableCard onRepeat={() => setConfirm({ kind: "repeat", s })} onDelete={() => setConfirm({ kind: "delete", s })}>
                <SessionCard
                  s={s}
                  onOpenSession={() => navigate(`/workout/log/${s.id}`)}
                  onOpenExercise={(name) => navigate(historyPath(name))}
                />
              </SwipeableCard>
            </li>
          ))}
        </ul>
      )}

      {sessions && sessions.length < total && (
        <button
          className="btn-outlined"
          style={{ minHeight: 44 }}
          disabled={loadingMore}
          onClick={async () => {
            setLoadingMore(true);
            await load(page + 1, true);
            setLoadingMore(false);
          }}
        >
          {loadingMore ? "Loading…" : "Show more"}
        </button>
      )}

      {sessions && sessions.length > 0 && (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "var(--md-sys-color-on-surface-variant)", textAlign: "center" }}>
          Swipe a session right to repeat it, left to delete it. Open a session for buttons.
        </p>
      )}

      <ConfirmDialog
        open={confirm?.kind === "repeat"}
        title={`Start ${confirm?.s.split ?? ""} again?`}
        body="This starts a new workout with the same exercises and starting weights. Nothing from the old session is copied as a result."
        confirmLabel="Start workout"
        danger={false}
        busy={busy}
        onConfirm={() => confirm && repeat(confirm.s)}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm?.kind === "delete"}
        title="Delete this session?"
        body={`${confirm ? `${confirm.s.split}, ${fmtDate(confirm.s.workout_date)}` : ""}: the session and its exercises, sets and comments are permanently removed. Other sessions and the workout type are not affected.`}
        confirmLabel="Delete"
        busy={busy}
        onConfirm={() => confirm && remove(confirm.s)}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
