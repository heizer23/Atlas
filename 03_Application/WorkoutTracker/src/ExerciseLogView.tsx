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

import { useEffect, useMemo, useRef, useState } from "react";
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
  borderRadius: 22,
  border: "none",
  background: "var(--md-sys-color-surface-variant)",
  color: "var(--md-sys-color-on-surface-variant)",
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
  height: 44,
  textAlign: "center",
  border: "1px solid var(--md-sys-color-outline-variant)",
  borderRadius: "var(--radius-input)",
  fontSize: 18,
  fontVariantNumeric: "tabular-nums",
  color: "var(--md-sys-color-on-surface)",
  background: "var(--md-sys-color-surface)",
  outline: "none",
  boxSizing: "border-box",
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
  const submitLock = useRef(false);

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

  const delta = row && row.status === "done" ? row.delta : null;

  return (
    <div className="page" style={{ gap: "var(--space-md)", paddingBottom: 96 }}>
      <div className="page-toolbar">
        <button className="icon-btn" style={{ marginLeft: 0 }} onClick={handleCancel} aria-label="Back without saving">
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
      </div>

      {error && <ErrorCard error={error} />}

      <div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => setHistoryName(name)}
          list={row ? undefined : "workout-exercise-names"}
          placeholder="Exercise name"
          aria-label="Exercise name"
          autoCapitalize="sentences"
          style={{
            width: "100%",
            border: "none",
            borderBottom: "1px solid var(--md-sys-color-outline-variant)",
            fontSize: 24,
            fontWeight: 600,
            color: "var(--md-sys-color-on-surface)",
            background: "transparent",
            padding: "4px 0 8px",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
        {!row && (
          <datalist id="workout-exercise-names">
            {names.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
        )}
        {last && (
          <p className="type-label" style={{ margin: "8px 0 0", color: "var(--md-sys-color-on-surface-variant)" }}>
            Last time · {fmtShortDate(last.workout_date)} · {fmtWeight(last.weight_kg)} ·{" "}
            {setsOf(last)
              .filter((v) => v != null)
              .join(" / ")}
            {delta !== null && delta !== 0 ? ` · ${delta > 0 ? "+" : "−"}${Math.abs(delta)} vs last` : ""}
          </p>
        )}
      </div>

      {historyName.trim() && (
        <div aria-live="polite">
          {history === null ? (
            <p className="type-label" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
              Loading history…
            </p>
          ) : (
            <RepsChart rows={earlier} liveRow={liveRow} variant="large" />
          )}
        </div>
      )}

      {/* Weight */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <label htmlFor="wt-weight" style={{ flex: "0 0 auto", fontSize: 15, minWidth: 84 }}>
          Weight (kg)
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
          placeholder="none"
          onChange={(e) => setWeight(e.target.value)}
          onFocus={(e) => e.currentTarget.select()}
          style={numberInput}
        />
        <button style={stepBtn} onClick={() => adjustWeight(WEIGHT_STEP)} aria-label="Increase weight">
          +
        </button>
      </div>

      {/* Sets */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Array.from({ length: visibleSets }, (_, i) => {
          const has = reps[i] !== "" && parseInt(reps[i], 10) > 0;
          const hint = last ? setsOf(last)[i] : null;
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 8px",
                borderRadius: "var(--radius-card)",
                background: has
                  ? "color-mix(in srgb, var(--md-sys-color-primary) 8%, transparent)"
                  : "var(--md-sys-color-surface-variant)",
              }}
            >
              <span
                style={{
                  flex: "0 0 44px",
                  fontSize: 15,
                  fontWeight: 600,
                  color: has ? "var(--md-sys-color-primary)" : "var(--md-sys-color-on-surface-variant)",
                }}
              >
                Set {i + 1}
              </span>
              <button style={stepBtn} onClick={() => adjustRep(i, -1)} aria-label={`Set ${i + 1}: fewer reps`}>
                −
              </button>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={reps[i]}
                placeholder={hint != null ? String(hint) : "reps"}
                aria-label={`Set ${i + 1} reps`}
                onChange={(e) =>
                  setReps((prev) => {
                    const next = [...prev];
                    next[i] = e.target.value;
                    return next;
                  })
                }
                onFocus={(e) => e.currentTarget.select()}
                style={numberInput}
              />
              <button style={stepBtn} onClick={() => adjustRep(i, 1)} aria-label={`Set ${i + 1}: more reps`}>
                +
              </button>
              <span
                aria-hidden
                className="material-symbols-rounded"
                style={{
                  flex: "0 0 28px",
                  fontSize: 24,
                  color: has ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)",
                }}
              >
                {has ? "check_circle" : "radio_button_unchecked"}
              </span>
            </div>
          );
        })}
        {visibleSets < MAX_SETS && (
          <button
            className="btn-text"
            style={{ alignSelf: "flex-start", minHeight: 44 }}
            onClick={() => setVisibleSets((n) => Math.min(MAX_SETS, n + 1))}
          >
            + Add set
          </button>
        )}
      </div>

      {/* Recent comments for this exercise (any archetype) */}
      {recentComments.length > 0 && (
        <section aria-label="Recent comments">
          <h2 className="type-title" style={{ margin: "0 0 4px" }}>
            Recent comments
          </h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {recentComments.map((h) => (
              <li
                key={h.id}
                style={{
                  display: "flex",
                  gap: 12,
                  padding: "8px 0",
                  borderTop: "1px solid var(--md-sys-color-outline-variant)",
                  fontSize: 14,
                }}
              >
                <span style={{ flex: "0 0 52px", color: "var(--md-sys-color-on-surface-variant)" }}>
                  {fmtShortDate(h.workout_date)}
                </span>
                <span style={{ flex: 1, whiteSpace: "pre-wrap" }}>{h.comment}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Today's note */}
      <div>
        <label htmlFor="wt-comment" className="type-title" style={{ display: "block", marginBottom: 6 }}>
          Notes
        </label>
        <textarea
          id="wt-comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add notes about this exercise…"
          rows={3}
          style={{
            width: "100%",
            border: "1px solid var(--md-sys-color-outline-variant)",
            borderRadius: "var(--radius-input)",
            padding: "10px 12px",
            fontSize: 16,
            color: "var(--md-sys-color-on-surface)",
            background: "var(--md-sys-color-surface)",
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
      </div>

      {formError && (
        <p role="alert" className="type-body" style={{ color: "var(--md-sys-color-error)", margin: 0 }}>
          {formError}
        </p>
      )}

      {row && onDeleted && (
        <button
          className="btn-text"
          style={{ alignSelf: "flex-start", minHeight: 44, color: "var(--md-sys-color-error)" }}
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
        >
          Delete exercise
        </button>
      )}

      {/* Sticky action bar so Save is always reachable above the keyboard / bottom nav */}
      <div
        style={{
          position: "sticky",
          bottom: 0,
          display: "flex",
          gap: 12,
          padding: "12px 0",
          background: "var(--md-sys-color-background)",
          borderTop: "1px solid var(--md-sys-color-outline-variant)",
        }}
      >
        <button className="btn-filled" style={{ flex: 1, minHeight: 48 }} onClick={handleSave} disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button className="btn-text" style={{ minHeight: 48 }} onClick={handleCancel} disabled={busy}>
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
