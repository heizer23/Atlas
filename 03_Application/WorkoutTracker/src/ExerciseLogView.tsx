/**
 * ExerciseLogView — active exercise / set entry (Session tab, and editing old sessions in Log).
 *
 * Edit mode: `row` given → PATCH /workout/exercises/{id} (saving marks it performed).
 * New mode:  no `row`    → POST  /workout/sessions/{id}/exercises.
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
  fmtShortDate,
  fmtWeight,
  setsOf,
  type ExerciseRow,
  type HistoryRow,
} from "./workoutShared";

const MAX_SETS = 5;
const WEIGHT_STEP = 2.5;

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

interface Props {
  sessionId: string;
  sessionDate: string;
  row?: ExerciseRow;
  onSaved: (ds: Dataset) => void;
  onCancel: () => void;
  onDeleted?: (ds: Dataset) => void;
}

export default function ExerciseLogView({ sessionId, sessionDate, row, onSaved, onCancel, onDeleted }: Props) {
  const draftKey = `workout_draft_${row ? row.id : `new_${sessionId}`}`;

  const baseKey = JSON.stringify(
    row ? [row.exercise, row.weight_kg, setsOf(row), row.comment ?? null] : "new",
  );

  const initial = useMemo<Draft>(() => {
    const saved = readDraft(draftKey);
    if (saved && saved.base === baseKey) return saved;
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

  const repNums = reps.map((v) => (v === "" ? null : parseInt(v, 10)));
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
    setReps((prev) => {
      const next = [...prev];
      const base = next[i] === "" ? (last ? setsOf(last)[i] ?? 0 : 0) : parseInt(next[i], 10) || 0;
      next[i] = String(Math.max(0, base + d));
      return next;
    });
  }

  function adjustWeight(d: number) {
    setWeightTouched(true);
    const base = weight === "" ? (last?.weight_kg ?? 0) : parseFloat(weight) || 0;
    setWeight(String(Math.max(0, Math.round((base + d) * 100) / 100)));
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
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={handleCancel} aria-label="Back without saving">
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
        {Array.from({ length: visibleSets }, (_, i) => {
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
          onClick={handleSave}
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
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          className="btn-text"
          style={{ minHeight: 48, padding: "0 14px", fontSize: 16, color: "var(--md-sys-color-primary)" }}
          onClick={handleCancel}
          disabled={busy}
        >
          Cancel
        </button>
      </div>

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
