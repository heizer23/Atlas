/**
 * ExerciseLogView — active exercise / set entry (Session tab, and editing old sessions in Log).
 *
 * Past-session edit (`live` false): `row` given → PATCH /workout/exercises/{id}; no `row` → POST
 * /workout/sessions/{id}/exercises. Plain reps entry, no timing.
 *
 * Active workout (`live`): a set is started by tapping its label and confirmed by its checkmark.
 * Only the checkmark persists a set (reps + server-stamped end time); a prefilled value shown
 * dashed is a suggestion until confirmed. Set events go through an ordered queue with retry, so
 * the UI answers immediately and a weak connection delays but never reorders them. "Done" waits
 * for the queue, then saves name / weight / notes (never sets or timing).
 * History (chart + recent comments) comes from /workout/exercises/history, which follows the
 * exercise name across archetypes.
 *
 * Unsaved input is kept in localStorage per exercise so a reload does not lose entered work.
 */

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { ApiError, Dataset } from "@platform-ui/api/types";
import {
  ConfirmDialog,
  RepsChart,
  fmtClock,
  fmtShortDate,
  fmtWeight,
  setsOf,
  type ExerciseRow,
  type HistoryRow,
} from "./workoutShared";

const MAX_SETS = 5;
const WEIGHT_STEP = 2.5;
/** Pauses before each retry of a set event that failed for lack of connection. */
const RETRY_DELAYS_MS = [800, 2000, 5000];
const RECONFIRM_DEBOUNCE_MS = 500;

type Op = () => Promise<Dataset | ApiError>;
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function timeOf(row: ExerciseRow | undefined, i: number, which: "started" | "ended"): string | null {
  const v = row?.[`set${i + 1}_${which}_at` as keyof ExerciseRow];
  return typeof v === "string" ? v : null;
}

interface Draft {
  /** Fingerprint of the saved row this draft was started from; a draft is ignored if the row changed since. */
  base: string;
  name: string;
  weight: string;
  reps: string[];
  comment: string;
}

function readDraft(key: string): Draft | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}
function writeDraft(key: string, d: Draft) {
  try {
    localStorage.setItem(key, JSON.stringify(d));
  } catch {
    /* storage unavailable — drafts are a convenience only */
  }
}
function clearDraft(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

const stepBtn: React.CSSProperties = {
  width: 44,
  height: 44,
  borderRadius: 10,
  border: "1px solid var(--md-sys-color-outline-variant)",
  background: "var(--md-sys-color-surface)",
  color: "var(--md-sys-color-primary)",
  fontSize: 22,
  lineHeight: 1,
  cursor: "pointer",
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  touchAction: "manipulation",
};

const numberInput: React.CSSProperties = {
  width: "100%",
  minWidth: 0,
  height: 44,
  textAlign: "center",
  border: "1px solid var(--md-sys-color-outline-variant)",
  borderRadius: 10,
  fontSize: 18,
  fontVariantNumeric: "tabular-nums",
  color: "var(--md-sys-color-on-surface)",
  background: "var(--md-sys-color-surface)",
  outline: "none",
};

const card: React.CSSProperties = {
  background: "var(--md-sys-color-surface)",
  border: "1px solid var(--md-sys-color-outline-variant)",
  borderRadius: 12,
  boxShadow: "var(--wt-card-shadow)",
};

/**
 * Secondary timing line for the active exercise: time since the first measured set start, and
 * either the running set or the rest since the last confirmation. Display only: it ticks on the
 * phone's clock against the server-stamped times (a skewed phone clock shifts the display, never
 * the stored data). Nothing is shown until something was measured.
 */
function LiveTiming({ row }: { row: ExerciseRow | undefined }) {
  const [now, setNow] = useState(() => Date.now());
  const ms = (v: string | null) => (v ? Date.parse(v) : NaN);
  const starts = [0, 1, 2, 3, 4].map((i) => ms(timeOf(row, i, "started")));
  const ends = [0, 1, 2, 3, 4].map((i) => ms(timeOf(row, i, "ended")));
  const firstStart = Math.min(...starts.filter((v) => !Number.isNaN(v)));
  const lastEnd = Math.max(...ends.filter((v) => !Number.isNaN(v)));
  const running = starts.filter((s, i) => !Number.isNaN(s) && Number.isNaN(ends[i]));
  const activeStart = running.length ? Math.max(...running) : NaN;
  const hasAny = Number.isFinite(firstStart) || Number.isFinite(lastEnd);

  useEffect(() => {
    if (!hasAny) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [hasAny]);

  if (!hasAny) return null;
  const parts: string[] = [];
  if (Number.isFinite(firstStart)) parts.push(`Exercise ${fmtClock((now - firstStart) / 1000)}`);
  if (!Number.isNaN(activeStart)) parts.push(`Set ${fmtClock((now - activeStart) / 1000)}`);
  else if (Number.isFinite(lastEnd)) parts.push(`Rest ${fmtClock((now - lastEnd) / 1000)}`);
  return (
    <p
      data-testid="live-timing"
      style={{ margin: "-4px 0 0", fontSize: 12, color: "var(--md-sys-color-on-surface-variant)", fontVariantNumeric: "tabular-nums" }}
    >
      {parts.join(" · ")}
    </p>
  );
}

interface Props {
  sessionId: string;
  sessionDate: string;
  row?: ExerciseRow;
  onSaved: (ds: Dataset) => void;
  onCancel: () => void;
  onDeleted?: (ds: Dataset) => void;
  /** Active workout: per-set start / checkmark flow with timing. */
  live?: boolean;
  /** Live only: the session's exercises after each set event (does not close the screen). */
  onSynced?: (ds: Dataset) => void;
  /** Live only: a new exercise got its row on the first set tap. */
  onRowCreated?: (id: string) => void;
}

export default function ExerciseLogView({
  sessionId,
  sessionDate,
  row,
  onSaved,
  onCancel,
  onDeleted,
  live = false,
  onSynced,
  onRowCreated,
}: Props) {
  const draftKey = `workout_draft_${row ? row.id : `new_${sessionId}`}`;

  // Live: sets are saved as they are confirmed, so they must not invalidate a draft of the rest.
  const baseKey = JSON.stringify(
    row ? (live ? [row.exercise, row.weight_kg, row.comment ?? null] : [row.exercise, row.weight_kg, setsOf(row), row.comment ?? null]) : "new",
  );

  const initial = useMemo<Draft>(() => {
    const saved = readDraft(draftKey);
    if (saved && saved.base === baseKey) {
      if (!live || !row) return saved;
      const persisted = setsOf(row); // confirmed sets always come from the server
      return { ...saved, reps: saved.reps.map((v, i) => (persisted[i] != null ? String(persisted[i]) : v)) };
    }
    const reps = [0, 1, 2, 3, 4].map((i) => {
      const v = row ? setsOf(row)[i] : null;
      return v == null ? "" : String(v);
    });
    return {
      base: baseKey,
      name: row?.exercise ?? "",
      weight: row?.weight_kg != null ? String(row.weight_kg) : "",
      reps,
      comment: row?.comment ?? "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey]);

  const [name, setName] = useState(initial.name);
  const [weight, setWeight] = useState(initial.weight);
  const [reps, setReps] = useState(initial.reps);
  const [comment, setComment] = useState(initial.comment);
  const [visibleSets, setVisibleSets] = useState(() => {
    const lastFilled = initial.reps.reduce((m, v, i) => (v !== "" ? i + 1 : m), 0);
    return Math.min(MAX_SETS, Math.max(3, lastFilled));
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [names, setNames] = useState<string[]>([]);
  const [nameFocused, setNameFocused] = useState(false);
  const submitLock = useRef(false);
  const nameRef = useRef<HTMLTextAreaElement>(null);
  // A weight carried over from the previous session is only a suggestion until touched.
  const [weightTouched, setWeightTouched] = useState(false);

  // ── Live-workout state: a set is confirmed once its reps are persisted ──────────
  const [confirmed, setConfirmed] = useState<boolean[]>(() =>
    [0, 1, 2, 3, 4].map((i) => (row ? setsOf(row)[i] != null : false)),
  );
  const [started, setStarted] = useState<boolean[]>(() =>
    [0, 1, 2, 3, 4].map((i) => !!row && setsOf(row)[i] == null && timeOf(row, i, "started") != null),
  );
  const [undoSet, setUndoSet] = useState<number | null>(null);
  const [sync, setSync] = useState<"idle" | "retrying" | "failed">("idle");
  const rowIdRef = useRef<string | undefined>(row?.id);
  const queue = useRef<Op[]>([]);
  const pumping = useRef<Promise<boolean> | null>(null);
  const reconfirmTimers = useRef<Array<ReturnType<typeof setTimeout> | undefined>>([]);

  // Long exercise names wrap: grow the title field to its content.
  useLayoutEffect(() => {
    const el = nameRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [name]);

  // Persist the draft on every change.
  useEffect(() => {
    writeDraft(draftKey, { base: baseKey, name, weight, reps, comment });
  }, [draftKey, baseKey, name, weight, reps, comment]);

  // History follows the exercise name; refreshed when an existing name is committed (blur).
  const [historyName, setHistoryName] = useState(row?.exercise ?? "");
  useEffect(() => {
    const n = historyName.trim();
    if (!n) {
      setHistory(null);
      return;
    }
    let cancelled = false;
    apiFetch<Dataset>(`/workout/exercises/history?name=${encodeURIComponent(n)}`).then((res) => {
      if (cancelled || isApiError(res)) return;
      setHistory(res.rows as unknown as HistoryRow[]);
    });
    return () => {
      cancelled = true;
    };
  }, [historyName]);

  useEffect(() => {
    if (row) return;
    apiFetch<Dataset>("/workout/exercises/names").then((res) => {
      if (!isApiError(res)) setNames(res.rows.map((r) => String(r.exercise)));
    });
  }, [row]);

  const earlier = useMemo(
    () => (history ?? []).filter((h) => !row || h.id !== row.id),
    [history, row],
  );
  const recentComments = useMemo(
    () => [...earlier].reverse().filter((h) => h.comment && h.comment.trim()).slice(0, 3),
    [earlier],
  );
  const last = earlier[earlier.length - 1];

  const repNums = reps.map((v, i) => (v === "" || (live && !confirmed[i]) ? null : parseInt(v, 10)));
  const liveRow: HistoryRow | undefined = repNums.some((v) => v)
    ? {
        id: "__live__",
        workout_date: row?.workout_date ?? sessionDate,
        weight_kg: weight === "" ? null : parseFloat(weight),
        set1_reps: repNums[0],
        set2_reps: repNums[1],
        set3_reps: repNums[2],
        set4_reps: repNums[3],
        set5_reps: repNums[4],
      }
    : undefined;

  function adjustRep(i: number, d: number) {
    const cur = reps[i] !== "" ? parseInt(reps[i], 10) || 0 : last ? setsOf(last)[i] ?? 0 : 0;
    const v = String(Math.max(0, cur + d));
    setReps((prev) => prev.map((x, k) => (k === i ? v : x)));
    scheduleReconfirm(i, v);
  }

  function adjustWeight(d: number) {
    setWeightTouched(true);
    const base = weight === "" ? (last?.weight_kg ?? 0) : parseFloat(weight) || 0;
    setWeight(String(Math.max(0, Math.round((base + d) * 100) / 100)));
  }

  // Last session's reps are offered as a dashed suggestion on sets not yet confirmed.
  const lastRepsForHint = last ? setsOf(last) : null;
  function shownReps(i: number): string {
    if (reps[i] !== "") return reps[i];
    if (live && !confirmed[i] && lastRepsForHint?.[i] != null) return String(lastRepsForHint[i]);
    return "";
  }
  const isPrefill = (i: number) => live && !confirmed[i] && reps[i] === "" && shownReps(i) !== "";

  // Show every set the previous session had.
  useEffect(() => {
    if (!live || !lastRepsForHint) return;
    const n = lastRepsForHint.filter((v) => v != null).length;
    setVisibleSets((v) => Math.min(MAX_SETS, Math.max(v, n)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, last?.id]);

  /** Run queued set events in order. Resolves true when the queue is empty, false if stuck offline. */
  function pump(): Promise<boolean> {
    if (pumping.current) return pumping.current;
    const run = async (): Promise<boolean> => {
      while (queue.current.length) {
        const op = queue.current[0];
        let res = await op();
        for (let a = 0; isApiError(res) && res.error.code === "NETWORK_ERROR" && a < RETRY_DELAYS_MS.length; a++) {
          setSync("retrying");
          await sleep(RETRY_DELAYS_MS[a]);
          res = await op();
        }
        if (isApiError(res) && res.error.code === "NETWORK_ERROR") {
          setSync("failed");
          return false;
        }
        queue.current.shift();
        if (isApiError(res)) setError(res);
        else onSynced?.(res);
      }
      setSync("idle");
      return true;
    };
    pumping.current = run().finally(() => {
      pumping.current = null;
    });
    return pumping.current;
  }

  function enqueue(op: Op) {
    queue.current.push(op);
    void pump();
  }

  /** The exercise's row, created (as 'planned') on the first set event of a new exercise. */
  async function ensureRow(exName: string, exWeight: number | null): Promise<string | ApiError> {
    if (rowIdRef.current) return rowIdRef.current;
    const res = await apiFetch<Dataset>(`/workout/sessions/${sessionId}/exercises`, {
      method: "POST",
      body: JSON.stringify({ exercise: exName, status: "planned", weight_kg: exWeight }),
    });
    if (isApiError(res)) return res;
    const id = String(res.rows[res.rows.length - 1].id);
    rowIdRef.current = id;
    clearDraft(`workout_draft_new_${sessionId}`);
    onSynced?.(res);
    onRowCreated?.(id);
    return id;
  }

  const weightNow = () => (weight !== "" && !Number.isNaN(parseFloat(weight)) ? parseFloat(weight) : null);

  function setOp(i: number, kind: "start" | "confirm", repsValue?: number): Op {
    const exName = name.trim();
    const w = weightNow();
    return async () => {
      const id = await ensureRow(exName, w);
      if (typeof id !== "string") return id;
      return apiFetch<Dataset>(`/workout/exercises/${id}/sets/${i + 1}/${kind}`, {
        method: "POST",
        body: kind === "confirm" ? JSON.stringify({ reps: repsValue, weight_kg: w }) : undefined,
      });
    };
  }

  function startSet(i: number) {
    if (confirmed[i] || started[i]) return;
    if (!name.trim()) return setFormError("Enter an exercise name first.");
    setFormError(null);
    setStarted((p) => p.map((v, k) => (k === i ? true : v)));
    enqueue(setOp(i, "start"));
  }

  function confirmSet(i: number) {
    const shown = shownReps(i);
    if (shown === "") return;
    if (!name.trim()) return setFormError("Enter an exercise name first.");
    setFormError(null);
    const n = Math.max(0, parseInt(shown, 10) || 0);
    setReps((p) => p.map((v, k) => (k === i ? String(n) : v)));
    setConfirmed((p) => p.map((v, k) => (k === i ? true : v)));
    setStarted((p) => p.map((v, k) => (k === i ? false : v)));
    enqueue(setOp(i, "confirm", n));
  }

  function undoConfirm(i: number) {
    setUndoSet(null);
    setConfirmed((p) => p.map((v, k) => (k === i ? false : v)));
    setStarted((p) => p.map((v, k) => (k === i ? false : v)));
    setReps((p) => p.map((v, k) => (k === i ? "" : v)));
    window.clearTimeout(reconfirmTimers.current[i]);
    enqueue(async () => {
      const id = rowIdRef.current;
      if (!id) return { error: { code: "NOT_FOUND", message: "exercise not saved yet", request_id: "" } } as ApiError;
      return apiFetch<Dataset>(`/workout/exercises/${id}/sets/${i + 1}/unconfirm`, { method: "POST" });
    });
  }

  // Correcting the reps of an already confirmed set re-sends the confirmation (timing never moves).
  function scheduleReconfirm(i: number, value: string) {
    if (!live || !confirmed[i]) return;
    window.clearTimeout(reconfirmTimers.current[i]);
    reconfirmTimers.current[i] = setTimeout(() => {
      reconfirmTimers.current[i] = undefined;
      const n = parseInt(value, 10);
      if (!Number.isNaN(n)) enqueue(setOp(i, "confirm", Math.max(0, n)));
    }, RECONFIRM_DEBOUNCE_MS);
  }

  function flushReconfirms() {
    reconfirmTimers.current.forEach((t, i) => {
      if (t === undefined) return;
      window.clearTimeout(t);
      reconfirmTimers.current[i] = undefined;
      const n = parseInt(reps[i], 10);
      if (!Number.isNaN(n)) enqueue(setOp(i, "confirm", Math.max(0, n)));
    });
  }

  async function handleDone() {
    if (submitLock.current) return;
    submitLock.current = true;
    setBusy(true);
    setError(null);
    setFormError(null);
    flushReconfirms();
    const drained = await pump();
    if (!drained) {
      setBusy(false);
      submitLock.current = false;
      return;
    }
    const id = rowIdRef.current;
    if (!id) {
      clearDraft(draftKey);
      return onCancel();
    }
    if (!name.trim()) {
      setFormError("Enter an exercise name.");
      setBusy(false);
      submitLock.current = false;
      return;
    }
    // Nothing but sets changed (they were saved as they happened): leave without a write.
    const unchanged =
      !!row &&
      name.trim() === row.exercise &&
      weightNow() === row.weight_kg &&
      (comment.trim() ? comment : null) === (row.comment ?? null);
    if (unchanged) {
      clearDraft(draftKey);
      return onCancel();
    }
    const res = await apiFetch<Dataset>(`/workout/exercises/${id}/details`, {
      method: "PATCH",
      body: JSON.stringify({ exercise: name.trim(), weight_kg: weightNow(), comment: comment.trim() ? comment : null }),
    });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      submitLock.current = false;
      return;
    }
    clearDraft(draftKey);
    onSaved(res);
  }

  async function handleSave() {
    if (submitLock.current) return;
    setFormError(null);
    if (!name.trim()) return setFormError("Enter an exercise name.");
    if (!reps.some((v) => v !== "")) return setFormError("Enter reps for at least one set.");

    submitLock.current = true;
    setBusy(true);
    setError(null);
    const body = JSON.stringify({
      exercise: name.trim(),
      weight_kg: weight !== "" ? parseFloat(weight) : null,
      set1_reps: reps[0] !== "" ? parseInt(reps[0], 10) : null,
      set2_reps: reps[1] !== "" ? parseInt(reps[1], 10) : null,
      set3_reps: reps[2] !== "" ? parseInt(reps[2], 10) : null,
      set4_reps: reps[3] !== "" ? parseInt(reps[3], 10) : null,
      set5_reps: reps[4] !== "" ? parseInt(reps[4], 10) : null,
      comment: comment.trim() ? comment : null,
    });
    const res = row
      ? await apiFetch<Dataset>(`/workout/exercises/${row.id}`, { method: "PATCH", body })
      : await apiFetch<Dataset>(`/workout/sessions/${sessionId}/exercises`, { method: "POST", body });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      submitLock.current = false;
      return;
    }
    clearDraft(draftKey);
    onSaved(res);
  }

  function handleCancel() {
    clearDraft(draftKey);
    onCancel();
  }

  async function handleDelete() {
    if (!row || submitLock.current) return;
    submitLock.current = true;
    setBusy(true);
    const res = await apiFetch<Dataset>(`/workout/exercises/${row.id}`, { method: "DELETE" });
    if (isApiError(res)) {
      setError(res);
      setBusy(false);
      setConfirmDelete(false);
      submitLock.current = false;
      return;
    }
    clearDraft(draftKey);
    onDeleted?.(res);
  }

  const typed = name.trim().toLowerCase();
  const nameSuggestions = names
    .filter((n) => (typed ? n.toLowerCase().includes(typed) && n.toLowerCase() !== typed : true))
    .slice(0, typed ? 5 : 6);

  // Starting weight carried over from the last session: shown as a suggestion until touched.
  const weightIsSuggestion =
    !!row && row.status === "planned" && !weightTouched && weight !== "" && weight === String(row.weight_kg ?? "");

  const delta = row && row.status === "done" ? row.delta : null;
  const lastReps = last ? setsOf(last) : null;

  return (
    <div className="page" style={{ gap: 12, paddingBottom: 0 }}>
      {error && <ErrorCard error={error} />}

      {/* Title row: back + exercise name */}
      <div style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: -6 }}>
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={live ? handleDone : handleCancel} aria-label={live ? "Back" : "Back without saving"}>
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <textarea
          ref={nameRef}
          rows={1}
          value={name}
          onChange={(e) => setName(e.target.value.replace(/\n/g, " "))}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.preventDefault();
          }}
          onFocus={() => setNameFocused(true)}
          onBlur={() => {
            setHistoryName(name);
            setTimeout(() => setNameFocused(false), 150); // let a tap on a suggestion land first
          }}
          placeholder="Exercise name"
          aria-label="Exercise name"
          autoCapitalize="sentences"
          style={{
            flex: 1,
            minWidth: 0,
            resize: "none",
            overflow: "hidden",
            border: "none",
            borderBottom: "1px solid var(--md-sys-color-outline-variant)",
            fontFamily: "inherit",
            fontSize: 22,
            fontWeight: 700,
            lineHeight: 1.25,
            letterSpacing: "-0.01em",
            color: "var(--md-sys-color-on-surface)",
            background: "transparent",
            padding: "6px 0",
            outline: "none",
          }}
        />
      </div>
      {!row && nameFocused && nameSuggestions.length > 0 && (
        <ul
          aria-label="Exercise suggestions"
          style={{ ...card, listStyle: "none", margin: "-6px 0 0", padding: 4, display: "flex", flexDirection: "column" }}
        >
          {nameSuggestions.map((n) => (
            <li key={n}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setName(n);
                  setHistoryName(n);
                  setNameFocused(false);
                }}
                style={{
                  width: "100%",
                  minHeight: 44,
                  padding: "0 10px",
                  border: "none",
                  background: "transparent",
                  textAlign: "left",
                  fontSize: 16,
                  color: "var(--md-sys-color-on-surface)",
                  cursor: "pointer",
                }}
              >
                {n}
              </button>
            </li>
          ))}
        </ul>
      )}

      {last && (
        <p style={{ margin: "-4px 0 0", fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
          Last time · {fmtShortDate(last.workout_date)} · {fmtWeight(last.weight_kg)} ·{" "}
          {setsOf(last)
            .filter((v) => v != null)
            .join(" / ")}
          {delta !== null && delta !== 0 ? ` · ${delta > 0 ? "+" : "−"}${Math.abs(delta)} vs last` : ""}
        </p>
      )}

      {live && <LiveTiming row={row} />}

      {historyName.trim() && (
        <div aria-live="polite">
          {history === null ? (
            <p style={{ fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>Loading history…</p>
          ) : (
            <RepsChart rows={earlier} liveRow={liveRow} variant="large" />
          )}
        </div>
      )}

      {/* Weight */}
      <div style={{ ...card, display: "flex", alignItems: "center", gap: 8, padding: "8px 10px" }}>
        <label htmlFor="wt-weight" style={{ flex: 1, minWidth: 0, fontSize: 15, fontWeight: 600 }}>
          Weight (kg)
          {weightIsSuggestion ? (
            <span style={{ display: "block", fontSize: 12, fontWeight: 400, color: "var(--md-sys-color-on-surface-variant)" }}>
              from last session
            </span>
          ) : (
            last?.weight_kg != null &&
            weight === "" && (
              <span style={{ display: "block", fontSize: 12, fontWeight: 400, color: "var(--md-sys-color-on-surface-variant)" }}>
                last {last.weight_kg}
              </span>
            )
          )}
        </label>
        <button style={stepBtn} onClick={() => adjustWeight(-WEIGHT_STEP)} aria-label="Decrease weight">
          −
        </button>
        <input
          id="wt-weight"
          type="number"
          inputMode="decimal"
          step="any"
          min={0}
          value={weight}
          placeholder="–"
          onChange={(e) => {
            setWeightTouched(true);
            setWeight(e.target.value);
          }}
          onFocus={(e) => {
            setWeightTouched(true);
            e.currentTarget.select();
          }}
          style={{
            ...numberInput,
            width: 84,
            fontWeight: weight !== "" && !weightIsSuggestion ? 600 : 400,
            color: weightIsSuggestion ? "var(--md-sys-color-on-surface-variant)" : "var(--md-sys-color-on-surface)",
            borderStyle: weightIsSuggestion ? "dashed" : "solid",
          }}
        />
        <button style={stepBtn} onClick={() => adjustWeight(WEIGHT_STEP)} aria-label="Increase weight">
          +
        </button>
      </div>

      {/* Sets: empty = nothing entered yet; blue + check = a value you entered this session */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {live &&
          Array.from({ length: visibleSets }, (_, i) => {
            const done = confirmed[i];
            const active = started[i] && !done;
            const prefill = isPrefill(i);
            const shown = shownReps(i);
            return (
              <div
                key={i}
                role="group"
                aria-label={`Set ${i + 1}`}
                data-state={done ? "done" : active ? "active" : "idle"}
                style={{
                  ...card,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 10px",
                  borderColor: done || active ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
                  borderWidth: active ? 2 : 1,
                  background: done ? "var(--md-sys-color-primary-container)" : "var(--md-sys-color-surface)",
                }}
              >
                <button
                  type="button"
                  onClick={() => startSet(i)}
                  disabled={done}
                  aria-label={`Start set ${i + 1}`}
                  style={{
                    flex: 1,
                    minWidth: 0,
                    minHeight: 44,
                    padding: 0,
                    border: "none",
                    background: "transparent",
                    textAlign: "left",
                    cursor: done ? "default" : "pointer",
                    touchAction: "manipulation",
                    color: "inherit",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: 15,
                      fontWeight: 600,
                      color: done || active ? "var(--md-sys-color-primary)" : "var(--md-sys-color-on-surface)",
                    }}
                  >
                    Set {i + 1}
                  </span>
                  <span style={{ display: "block", fontSize: 12, color: "var(--md-sys-color-on-surface-variant)" }}>
                    {done ? "Done" : active ? "In progress" : "Tap to start"}
                  </span>
                </button>
                <button style={stepBtn} onClick={() => adjustRep(i, -1)} aria-label={`Set ${i + 1}: fewer reps`}>
                  −
                </button>
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={shown}
                  placeholder="–"
                  aria-label={`Set ${i + 1} reps`}
                  onChange={(e) => {
                    setReps((prev) => prev.map((x, k) => (k === i ? e.target.value : x)));
                    scheduleReconfirm(i, e.target.value);
                  }}
                  onFocus={(e) => e.currentTarget.select()}
                  style={{
                    ...numberInput,
                    width: 56,
                    fontWeight: prefill ? 400 : 700,
                    borderStyle: prefill ? "dashed" : "solid",
                    color: prefill ? "var(--md-sys-color-on-surface-variant)" : "var(--md-sys-color-on-surface)",
                    borderColor: done ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
                  }}
                />
                <button style={stepBtn} onClick={() => adjustRep(i, 1)} aria-label={`Set ${i + 1}: more reps`}>
                  +
                </button>
                <button
                  type="button"
                  onClick={() => (done ? setUndoSet(i) : confirmSet(i))}
                  disabled={!done && shown === ""}
                  aria-label={done ? `Set ${i + 1} confirmed, tap to undo` : `Confirm set ${i + 1}`}
                  aria-pressed={done}
                  style={{
                    ...stepBtn,
                    border: "none",
                    borderRadius: 22,
                    background: done ? "var(--md-sys-color-primary)" : "transparent",
                    color: done ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-primary)",
                    opacity: !done && shown === "" ? 0.35 : 1,
                  }}
                >
                  <span
                    aria-hidden
                    className="material-symbols-rounded"
                    style={{ fontSize: 26, fontVariationSettings: done ? "'FILL' 1" : "'FILL' 0" }}
                  >
                    {done ? "check" : "check_circle"}
                  </span>
                </button>
              </div>
            );
          })}
        {!live &&
          Array.from({ length: visibleSets }, (_, i) => {
          const entered = reps[i] !== "";
          const hint = lastReps ? lastReps[i] : null;
          return (
            <div
              key={i}
              style={{
                ...card,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 10px",
                borderColor: entered ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
              }}
            >
              <span style={{ flex: 1, minWidth: 0 }}>
                <span
                  style={{
                    display: "block",
                    fontSize: 15,
                    fontWeight: 600,
                    color: entered ? "var(--md-sys-color-primary)" : "var(--md-sys-color-on-surface-variant)",
                  }}
                >
                  Set {i + 1}
                </span>
                {hint != null && !entered && (
                  <span style={{ display: "block", fontSize: 12, color: "var(--md-sys-color-on-surface-variant)" }}>
                    last {hint}
                  </span>
                )}
              </span>
              <button style={stepBtn} onClick={() => adjustRep(i, -1)} aria-label={`Set ${i + 1}: fewer reps`}>
                −
              </button>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={reps[i]}
                placeholder="–"
                aria-label={`Set ${i + 1} reps`}
                onChange={(e) =>
                  setReps((prev) => {
                    const next = [...prev];
                    next[i] = e.target.value;
                    return next;
                  })
                }
                onFocus={(e) => e.currentTarget.select()}
                style={{
                  ...numberInput,
                  width: 64,
                  fontWeight: entered ? 700 : 400,
                  borderColor: entered ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
                }}
              />
              <button style={stepBtn} onClick={() => adjustRep(i, 1)} aria-label={`Set ${i + 1}: more reps`}>
                +
              </button>
              <span
                aria-hidden
                className="material-symbols-rounded"
                style={{
                  flex: "0 0 24px",
                  fontSize: 24,
                  color: entered ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
                  fontVariationSettings: entered ? "'FILL' 1" : "'FILL' 0",
                }}
              >
                {entered ? "check_circle" : "radio_button_unchecked"}
              </span>
            </div>
          );
        })}
        {visibleSets < MAX_SETS && (
          <button
            className="btn-text"
            style={{ alignSelf: "flex-start", minHeight: 40, padding: "0 8px", color: "var(--md-sys-color-primary)" }}
            onClick={() => setVisibleSets((n) => Math.min(MAX_SETS, n + 1))}
          >
            + Add set
          </button>
        )}
      </div>

      {/* Recent comments for this exercise (any archetype) */}
      {recentComments.length > 0 && (
        <section aria-label="Recent comments" style={{ ...card, padding: "10px 12px" }}>
          <h2 style={{ margin: "0 0 2px", fontSize: 15, fontWeight: 700 }}>Recent comments</h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {recentComments.map((h, k) => (
              <li
                key={h.id}
                style={{
                  display: "flex",
                  gap: 12,
                  padding: "7px 0",
                  borderTop: k === 0 ? "none" : "1px solid var(--md-sys-color-outline-variant)",
                  fontSize: 14,
                  lineHeight: 1.35,
                }}
              >
                <span style={{ flex: "0 0 48px", color: "var(--md-sys-color-on-surface-variant)" }}>
                  {fmtShortDate(h.workout_date)}
                </span>
                <span style={{ flex: 1, minWidth: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{h.comment}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Today's note */}
      <div>
        <label htmlFor="wt-comment" style={{ display: "block", marginBottom: 4, fontSize: 15, fontWeight: 700 }}>
          Notes
        </label>
        <textarea
          id="wt-comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add notes about this exercise…"
          rows={2}
          style={{
            width: "100%",
            border: "1px solid var(--md-sys-color-outline-variant)",
            borderRadius: 10,
            padding: "10px 12px",
            fontSize: 16,
            color: "var(--md-sys-color-on-surface)",
            background: "var(--md-sys-color-surface)",
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
          }}
        />
      </div>

      {formError && (
        <p role="alert" style={{ margin: 0, fontSize: 14, color: "var(--md-sys-color-error)" }}>
          {formError}
        </p>
      )}

      {row && onDeleted && (
        <button
          className="btn-text"
          style={{ alignSelf: "flex-start", minHeight: 44, padding: "0 8px", color: "var(--md-sys-color-error)" }}
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
        >
          Delete exercise
        </button>
      )}

      {live && sync !== "idle" && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderRadius: 10,
            fontSize: 13,
            background: "var(--md-sys-color-surface-variant)",
            color: "var(--md-sys-color-on-surface)",
          }}
        >
          <span style={{ flex: 1 }}>
            {sync === "retrying" ? "No connection — retrying. Your taps are kept." : "Not saved yet — no connection."}
          </span>
          {sync === "failed" && (
            <button
              className="btn-text"
              style={{ minHeight: 40, padding: "0 10px", color: "var(--md-sys-color-primary)", fontWeight: 600 }}
              onClick={() => void pump()}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* Sticky action bar so Save stays reachable above the keyboard / bottom nav */}
      <div
        style={{
          position: "sticky",
          bottom: 0,
          display: "flex",
          alignItems: "center",
          gap: 10,
          margin: "0 -12px",
          padding: "10px 12px",
          background: "var(--md-sys-color-background)",
          borderTop: "1px solid var(--md-sys-color-outline-variant)",
        }}
      >
        <button
          onClick={live ? handleDone : handleSave}
          disabled={busy}
          style={{
            flex: 1,
            minHeight: 48,
            border: "none",
            borderRadius: 14,
            background: "var(--md-sys-color-primary)",
            color: "var(--md-sys-color-on-primary)",
            fontSize: 16,
            fontWeight: 600,
            cursor: "pointer",
            opacity: busy ? 0.6 : 1,
            touchAction: "manipulation",
          }}
        >
          {busy ? "Saving…" : live ? "Done" : "Save"}
        </button>
        {!live && (
          <button
            className="btn-text"
            style={{ minHeight: 48, padding: "0 14px", fontSize: 16, color: "var(--md-sys-color-primary)" }}
            onClick={handleCancel}
            disabled={busy}
          >
            Cancel
          </button>
        )}
      </div>

      <ConfirmDialog
        open={undoSet !== null}
        title={`Undo set ${(undoSet ?? 0) + 1}?`}
        body="Its reps and timing are cleared. Your other sets are not affected."
        confirmLabel="Undo set"
        danger={false}
        onConfirm={() => undoSet !== null && undoConfirm(undoSet)}
        onCancel={() => setUndoSet(null)}
      />
      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${row?.exercise ?? "exercise"}?`}
        body="This removes the exercise and its sets from this workout."
        confirmLabel="Delete"
        busy={busy}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
