import { useState, useEffect, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { apiFetch, isApiError } from "../api/client";
import { useDataset } from "../hooks/useDataset";
import CreateForm from "../components/CreateForm";
import ErrorCard from "../components/ErrorCard";
import type { Row, FormField, Dataset, ApiError } from "../api/types";

type HistoryData = { rows: Row[] };

// ── Form field definitions ────────────────────────────────────────────────────

const SESSION_FIELDS: FormField[] = [
  { key: "workout_date", label: "Date",         type: "date",   required: true },
  { key: "split",        label: "Split",        type: "string", required: true, placeholder: "e.g. Push, Pull, Legs" },
  { key: "exercise",     label: "Exercise",     type: "string", required: true },
  { key: "weight_kg",    label: "Weight (kg)",  type: "number", placeholder: "optional" },
  { key: "set1_reps",    label: "Set 1 Reps",   type: "number" },
  { key: "set2_reps",    label: "Set 2 Reps",   type: "number" },
  { key: "set3_reps",    label: "Set 3 Reps",   type: "number" },
  { key: "set4_reps",    label: "Set 4 Reps",   type: "number" },
  { key: "set5_reps",    label: "Set 5 Reps",   type: "number" },
  { key: "comment",      label: "Comment",      type: "string" },
];

const EXERCISE_FIELDS: FormField[] = [
  { key: "exercise",  label: "Exercise",    type: "string", required: true },
  { key: "weight_kg", label: "Weight (kg)", type: "number", placeholder: "optional" },
  { key: "set1_reps", label: "Set 1 Reps",  type: "number" },
  { key: "set2_reps", label: "Set 2 Reps",  type: "number" },
  { key: "set3_reps", label: "Set 3 Reps",  type: "number" },
  { key: "set4_reps", label: "Set 4 Reps",  type: "number" },
  { key: "set5_reps", label: "Set 5 Reps",  type: "number" },
  { key: "comment",   label: "Comment",     type: "string" },
];

const SET_COLORS = ["#6750A4", "#7965AF", "#8B7AB9", "#9D8FC4", "#AFA4CF"];

// ── HistoryChart ──────────────────────────────────────────────────────────────

function HistoryChart({
  history, size, liveRow,
}: {
  history:  HistoryData | undefined;
  size:     "mini" | "full";
  liveRow?: Record<string, unknown>;
}) {
  if (!history) {
    if (size === "mini") {
      return (
        <div style={{
          flex: "1 1 0", minWidth: 0, overflow: "hidden",
          display: "flex", alignItems: "flex-end", gap: 5, height: 46,
        }}>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} style={{
              flex: 1, height: 20, background: "#CAC4D0",
              borderRadius: "3px 3px 0 0",
            }} />
          ))}
        </div>
      );
    }
    return (
      <div style={{
        height: 200, background: "#F8F6FA", borderRadius: 8,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#49454F", fontSize: 14,
      }}>
        Loading history…
      </div>
    );
  }

  const baseRows = (size === "mini" ? history.rows.slice(-8) : history.rows) as Record<string, unknown>[];
  const data = (size === "full" && liveRow) ? [...baseRows, liveRow] : baseRows;

  if (size === "mini") {
    return (
      <div style={{ flex: "1 1 0", minWidth: 0, overflow: "hidden", height: 46 }}>
        <ResponsiveContainer width="100%" height={46}>
          <BarChart data={data} margin={{ top: 0, right: 0, left: 0, bottom: 0 }} barCategoryGap="20%">
            <Bar dataKey="set1_reps" stackId="a" fill={SET_COLORS[0]} isAnimationActive={false} />
            <Bar dataKey="set2_reps" stackId="a" fill={SET_COLORS[1]} isAnimationActive={false} />
            <Bar dataKey="set3_reps" stackId="a" fill={SET_COLORS[2]} isAnimationActive={false} />
            <Bar dataKey="set4_reps" stackId="a" fill={SET_COLORS[3]} isAnimationActive={false} />
            <Bar dataKey="set5_reps" stackId="a" fill={SET_COLORS[4]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // full
  return (
    <div style={{ background: "#F8F6FA", borderRadius: 8, padding: 16 }}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="0" stroke="#E6E1E5" vertical={false} />
          <XAxis dataKey="workout_date" axisLine={false} tickLine={false} tick={false} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: "#49454F", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#FFFBFE",
              border: "1px solid #E6E1E5",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={label => String(label)}
            formatter={(value, name) => [
              `${value} reps`,
              String(name).replace("_reps", "").replace("set", "Set "),
            ]}
          />
          <Bar dataKey="set1_reps" stackId="a" fill={SET_COLORS[0]} />
          <Bar dataKey="set2_reps" stackId="a" fill={SET_COLORS[1]} />
          <Bar dataKey="set3_reps" stackId="a" fill={SET_COLORS[2]} />
          <Bar dataKey="set4_reps" stackId="a" fill={SET_COLORS[3]} />
          <Bar dataKey="set5_reps" stackId="a" fill={SET_COLORS[4]} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Exercise row ──────────────────────────────────────────────────────────────

interface ExerciseRowProps {
  row:          Row;
  history:      HistoryData | undefined;
  menuOpen:     boolean;
  onToggleMenu: (e: React.MouseEvent) => void;
  onClick:      () => void;
  onEdit:       () => void;
  onDelete:     () => void;
}

function ExerciseRow({ row, history, menuOpen, onToggleMenu, onClick, onEdit, onDelete }: ExerciseRowProps) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center",
        padding: "12px 16px", minHeight: 80,
        borderBottom: "1px solid #CAC4D0",
        gap: 12, cursor: "pointer", position: "relative",
        transition: "background 200ms",
        background: "transparent",
      }}
      onMouseEnter={e => (e.currentTarget.style.background = "rgba(103,80,164,.08)")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      {/* Leading icon */}
      <div style={{
        width: 40, height: 40, flexShrink: 0,
        background: "#E7E0EC", borderRadius: "50%",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <span className="material-symbols-rounded" style={{ fontSize: 20, color: "#49454F" }}>
          fitness_center
        </span>
      </div>

      {/* Text */}
      <div style={{ flex: "0 0 100px", flexShrink: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 500, lineHeight: "24px", color: "#1C1B1F", letterSpacing: ".15px" }}>
          {String(row.exercise ?? "")}
        </div>
        {row.weight_kg != null && (
          <div style={{ fontSize: 14, fontWeight: 400, lineHeight: "20px", color: "#49454F", letterSpacing: ".25px" }}>
            {row.weight_kg} kg
          </div>
        )}
      </div>

      {/* Mini history chart */}
      <HistoryChart history={history} size="mini" />

      {/* Trailing: more_vert + menu */}
      <div style={{ flexShrink: 0, position: "relative" }} onClick={e => e.stopPropagation()}>
        <button
          onClick={onToggleMenu}
          style={{
            width: 40, height: 40, border: "none", borderRadius: "50%",
            background: "transparent", color: "#49454F",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
          aria-label="More options"
        >
          <span className="material-symbols-rounded" style={{ fontSize: 24 }}>more_vert</span>
        </button>

        {menuOpen && (
          <div style={{
            position: "absolute", top: "calc(100% + 4px)", right: 0,
            minWidth: 168, background: "#ECE6F0",
            borderRadius: 4,
            boxShadow: "0 2px 6px 2px rgba(0,0,0,.15), 0 1px 2px rgba(0,0,0,.3)",
            padding: "8px 0", zIndex: 100,
          }}>
            <div
              onClick={onEdit}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "0 12px", height: 48, fontSize: 14,
                fontWeight: 400, letterSpacing: ".25px", color: "#1C1B1F",
                cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: "#49454F" }}>edit</span>
              Edit
            </div>
            <div style={{ height: 1, background: "#CAC4D0", margin: "8px 0" }} />
            <div
              onClick={onDelete}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "0 12px", height: 48, fontSize: 14,
                fontWeight: 400, letterSpacing: ".25px", color: "#1C1B1F",
                cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: "#49454F" }}>delete</span>
              Delete
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Exercise list ─────────────────────────────────────────────────────────────

interface ExerciseListProps {
  dataset:           Dataset | null;
  historyByExercise: Record<string, HistoryData>;
  onRowClick:        (row: Row) => void;
  onEdit:            (row: Row) => void;
  onDelete:          (id: string) => void;
}

function ExerciseList({ dataset, historyByExercise, onRowClick, onEdit, onDelete }: ExerciseListProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  if (!dataset) return <p className="type-body" style={{ padding: 16 }}>Loading…</p>;
  if (dataset.rows.length === 0) return <p className="type-body" style={{ padding: 16 }}>No exercises yet.</p>;

  return (
    <div
      ref={listRef}
      style={{
        background: "#FFFBFE",
        borderRadius: 12,
        boxShadow: "0px 1px 2px rgba(0,0,0,.3), 0px 1px 3px 1px rgba(0,0,0,.15)",
        overflow: "hidden",
        marginTop: 16,
      }}
    >
      {dataset.rows.map((row) => (
        <ExerciseRow
          key={row.id}
          row={row}
          history={historyByExercise[row.exercise as string]}
          menuOpen={openMenuId === row.id}
          onToggleMenu={() => setOpenMenuId(openMenuId === row.id ? null : row.id)}
          onClick={() => { setOpenMenuId(null); onRowClick(row); }}
          onEdit={() => { setOpenMenuId(null); onEdit(row); }}
          onDelete={() => { setOpenMenuId(null); onDelete(row.id); }}
        />
      ))}
    </div>
  );
}

// ── ExerciseView ──────────────────────────────────────────────────────────────

interface ExerciseViewProps {
  row:         Row;
  history:     HistoryData | undefined;
  sessionDate: string;          // "YYYY-MM-DD" — used to determine initial completed state
  onBack:      () => void;
  onSave:      (data: Record<string, unknown>) => Promise<ApiError | null>;
}

function ExerciseView({ row, history, sessionDate, onBack, onSave }: ExerciseViewProps) {
  const [name,    setName]    = useState(row.exercise as string);
  const [weight,  setWeight]  = useState(row.weight_kg != null ? String(row.weight_kg) : "");
  const initReps = [1, 2, 3, 4, 5].map(i => String((row as Record<string, unknown>)[`set${i}_reps`] ?? ""));
  const [reps,    setReps]    = useState(initReps);
  const [comment,   setComment]   = useState(String(row.comment ?? ""));

  // Past sessions: sets with reps already start as completed (checkmark shown).
  // Today's session: start uncompleted — user marks sets as they do them.
  const today = new Date().toISOString().split("T")[0];
  const isPast = sessionDate < today;
  const [completed, setCompleted] = useState(
    [0, 1, 2, 3, 4].map(i => isPast && parseInt(initReps[i]) > 0)
  );

  // Exclude this exercise's own row from history to avoid a duplicate bar
  // (the current row is represented via liveRow instead)
  const filteredHistory: HistoryData | undefined = history
    ? { rows: history.rows.filter(r => r.id !== row.id) }
    : undefined;
  const [busy,      setBusy]      = useState(false);
  const [error,     setError]     = useState<ApiError | null>(null);

  const liveRow: Record<string, unknown> = {
    workout_date: "Today",
    set1_reps: completed[0] ? (parseInt(reps[0]) || 0) : 0,
    set2_reps: completed[1] ? (parseInt(reps[1]) || 0) : 0,
    set3_reps: completed[2] ? (parseInt(reps[2]) || 0) : 0,
    set4_reps: completed[3] ? (parseInt(reps[3]) || 0) : 0,
    set5_reps: completed[4] ? (parseInt(reps[4]) || 0) : 0,
  };

  function adjustRep(i: number, delta: number) {
    setReps(prev => {
      const next = [...prev];
      next[i] = String(Math.max(0, (parseInt(next[i]) || 0) + delta));
      return next;
    });
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    const data = {
      exercise:  name.trim(),
      weight_kg: weight !== "" ? parseFloat(weight) : null,
      set1_reps: reps[0] !== "" ? parseInt(reps[0]) : null,
      set2_reps: reps[1] !== "" ? parseInt(reps[1]) : null,
      set3_reps: reps[2] !== "" ? parseInt(reps[2]) : null,
      set4_reps: reps[3] !== "" ? parseInt(reps[3]) : null,
      set5_reps: reps[4] !== "" ? parseInt(reps[4]) : null,
      comment:   comment || null,
    };
    const err = await onSave(data);
    if (err) setError(err);
    setBusy(false);
  }

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="btn-text" onClick={onBack}>← Back</button>
        <div style={{ flex: 1 }} />
      </div>

      {error && <ErrorCard error={error} />}

      {/* Exercise name */}
      <div style={{ padding: "0 16px 16px" }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          style={{
            width: "100%", border: "none", borderBottom: "2px solid #6750A4",
            fontSize: 22, fontWeight: 500, color: "#1C1B1F",
            background: "transparent", padding: "4px 0", outline: "none",
            letterSpacing: ".15px",
          }}
        />
      </div>

      {/* Weight */}
      <div style={{ padding: "0 16px 16px", display: "flex", alignItems: "center", gap: 8 }}>
        <label style={{ fontSize: 14, color: "#49454F", minWidth: 60 }}>Weight</label>
        <div style={{
          display: "flex", alignItems: "center",
          border: "1px solid #CAC4D0", borderRadius: 8, overflow: "hidden",
          flex: "0 0 140px",
        }}>
          <input
            type="number"
            value={weight}
            onChange={e => setWeight(e.target.value)}
            placeholder="—"
            style={{
              flex: 1, border: "none", padding: "8px 12px",
              fontSize: 16, color: "#1C1B1F", background: "transparent", outline: "none",
            }}
          />
          <span style={{ paddingRight: 12, fontSize: 14, color: "#49454F" }}>kg</span>
        </div>
      </div>

      <div style={{ height: 1, background: "#CAC4D0", margin: "0 16px 16px" }} />

      {/* Sets */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "0 16px 16px" }}>
        {[0, 1, 2, 3, 4].map(i => {
          const done = completed[i];
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "10px 12px",
              border: `1px solid ${done ? "#6750A4" : "#E6E1E5"}`,
              borderRadius: 8,
              background: done ? "rgba(103,80,164,.06)" : "#FFFBFE",
              transition: "all 0.15s",
            }}>
              <span style={{ flex: "0 0 44px", fontSize: 14, fontWeight: 500, color: done ? "#6750A4" : "#49454F" }}>
                Set {i + 1}
              </span>
              <button
                onClick={() => adjustRep(i, -1)}
                style={{
                  width: 32, height: 32, borderRadius: 16, border: "none",
                  background: "#E7E0EC", cursor: "pointer", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, color: "#49454F",
                }}
              >−</button>
              {/* Input with "reps" suffix inside */}
              <div style={{ flex: 1, position: "relative", display: "flex", alignItems: "center" }}>
                <input
                  type="number"
                  value={reps[i]}
                  onChange={e => {
                    const next = [...reps];
                    next[i] = e.target.value;
                    setReps(next);
                  }}
                  placeholder="0"
                  style={{
                    width: "100%", textAlign: "center", border: "1px solid #CAC4D0",
                    borderRadius: 8, padding: "6px 40px 6px 8px", fontSize: 16,
                    color: "#1C1B1F", background: "transparent", outline: "none",
                    boxSizing: "border-box",
                  }}
                />
                <span style={{
                  position: "absolute", right: 10, fontSize: 12,
                  color: "#79747E", pointerEvents: "none",
                }}>reps</span>
              </div>
              <button
                onClick={() => adjustRep(i, 1)}
                style={{
                  width: 32, height: 32, borderRadius: 16, border: "none",
                  background: "#E7E0EC", cursor: "pointer", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, color: "#49454F",
                }}
              >+</button>
              <button
                onClick={() => setCompleted(prev => { const n = [...prev]; n[i] = !n[i]; return n; })}
                style={{
                  width: 36, height: 36, borderRadius: 18, border: "none", flexShrink: 0,
                  background: done ? "#6750A4" : "#E7E0EC", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "background 0.15s",
                }}
                aria-label={done ? "Unmark set" : "Mark set done"}
              >
                <span className="material-symbols-rounded" style={{ fontSize: 18, color: done ? "#fff" : "#49454F" }}>
                  {done ? "check" : "close"}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      <div style={{ height: 1, background: "#CAC4D0", margin: "0 16px 16px" }} />

      {/* History chart */}
      <div style={{ padding: "0 16px 16px" }}>
        <HistoryChart
          history={filteredHistory}
          size="full"
          liveRow={completed.some(c => c) ? liveRow : undefined}
        />
      </div>

      <div style={{ height: 1, background: "#CAC4D0", margin: "0 16px 16px" }} />

      {/* Comment */}
      <div style={{ padding: "0 16px 16px" }}>
        <label style={{ display: "block", fontSize: 14, color: "#49454F", marginBottom: 8 }}>
          Comment
        </label>
        <textarea
          value={comment}
          onChange={e => setComment(e.target.value)}
          placeholder="Add notes about your workout…"
          rows={3}
          style={{
            width: "100%", border: "1px solid #CAC4D0", borderRadius: 8,
            padding: "10px 12px", fontSize: 14, color: "#1C1B1F",
            background: "#FFFBFE", outline: "none", resize: "vertical",
            fontFamily: "inherit", boxSizing: "border-box",
          }}
        />
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 12, padding: "0 16px 24px" }}>
        <button
          className="btn-filled"
          onClick={handleSave}
          disabled={busy}
          style={{ flex: 1 }}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button className="btn-text" onClick={onBack}>Cancel</button>
      </div>
    </div>
  );
}

// ── Session list ──────────────────────────────────────────────────────────────

interface SessionListProps {
  dataset:    Dataset | null;
  onRowClick: (row: Row) => void;
  onDelete:   (id: string) => void;
  onCopy:     (row: Row) => void;
}

function SessionList({ dataset, onRowClick, onDelete, onCopy }: SessionListProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  if (!dataset) return <p className="type-body" style={{ padding: 16 }}>Loading…</p>;
  if (dataset.rows.length === 0) return <p className="type-body" style={{ padding: 16 }}>No sessions yet.</p>;

  function fmtDate(val: unknown) {
    const d = new Date(String(val));
    return isNaN(d.getTime()) ? String(val) : d.toLocaleDateString(undefined, { dateStyle: "medium" });
  }

  return (
    <div
      ref={listRef}
      style={{
        background: "#FFFBFE",
        borderRadius: 12,
        boxShadow: "0px 1px 2px rgba(0,0,0,.3), 0px 1px 3px 1px rgba(0,0,0,.15)",
        overflow: "hidden",
        marginTop: 16,
      }}
    >
      {dataset.rows.map(row => (
        <div
          key={row.id}
          onClick={() => { setOpenMenuId(null); onRowClick(row); }}
          style={{
            display: "flex", alignItems: "center",
            padding: "14px 16px", borderBottom: "1px solid #CAC4D0",
            gap: 12, cursor: "pointer", position: "relative",
            transition: "background 200ms", background: "transparent",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "rgba(103,80,164,.08)")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          {/* Leading icon */}
          <div style={{
            width: 40, height: 40, flexShrink: 0, background: "#E7E0EC",
            borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 20, color: "#49454F" }}>
              calendar_today
            </span>
          </div>

          {/* Text */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 16, fontWeight: 500, color: "#1C1B1F", letterSpacing: ".15px" }}>
              {String(row.split ?? "")}
            </div>
            <div style={{ fontSize: 14, color: "#49454F", letterSpacing: ".25px" }}>
              {fmtDate(row.workout_date)}
            </div>
          </div>

          {/* Exercise count chip */}
          <div style={{
            flexShrink: 0, background: "#E7E0EC", borderRadius: 12,
            padding: "2px 10px", fontSize: 12, color: "#49454F",
          }}>
            {row.exercise_count} ex
          </div>

          {/* ⋮ menu */}
          <div style={{ flexShrink: 0, position: "relative" }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setOpenMenuId(openMenuId === row.id ? null : row.id)}
              style={{
                width: 40, height: 40, border: "none", borderRadius: "50%",
                background: "transparent", color: "#49454F", cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
              aria-label="More options"
            >
              <span className="material-symbols-rounded" style={{ fontSize: 24 }}>more_vert</span>
            </button>

            {openMenuId === row.id && (
              <div style={{
                position: "absolute", top: "calc(100% + 4px)", right: 0,
                minWidth: 160, background: "#ECE6F0", borderRadius: 4,
                boxShadow: "0 2px 6px 2px rgba(0,0,0,.15), 0 1px 2px rgba(0,0,0,.3)",
                padding: "8px 0", zIndex: 100,
              }}>
                <div
                  onClick={() => { setOpenMenuId(null); onCopy(row); }}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "0 12px", height: 48, fontSize: 14,
                    fontWeight: 400, letterSpacing: ".25px", color: "#1C1B1F", cursor: "pointer",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <span className="material-symbols-rounded" style={{ fontSize: 18, color: "#49454F" }}>content_copy</span>
                  Copy
                </div>
                <div style={{ height: 1, background: "#CAC4D0", margin: "4px 0" }} />
                <div
                  onClick={() => { setOpenMenuId(null); onDelete(row.id); }}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "0 12px", height: 48, fontSize: 14,
                    fontWeight: 400, letterSpacing: ".25px", color: "#B3261E", cursor: "pointer",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <span className="material-symbols-rounded" style={{ fontSize: 18, color: "#B3261E" }}>delete</span>
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

// ── View state ────────────────────────────────────────────────────────────────

type View = "sessions" | "exercises" | "exercise-view" | "session-create" | "exercise-add";

// ── Component ─────────────────────────────────────────────────────────────────

export default function WorkoutSessions() {
  const [view,              setView]             = useState<View>("sessions");
  const [selectedSession,   setSelectedSession]  = useState<Row | null>(null);
  const [selectedExercise,  setSelectedExercise] = useState<Row | null>(null);
  const [exerciseDataset,   setExerciseDataset]  = useState<Dataset | null>(null);
  const [exerciseLoading,   setExerciseLoading]  = useState(false);
  const [exerciseError,     setExerciseError]    = useState<ApiError | null>(null);
  const [mutateError,       setMutateError]      = useState<ApiError | null>(null);
  const [historyByExercise, setHistoryByExercise] = useState<Record<string, HistoryData>>({});

  const { dataset: sessionDataset, error: sessionError, refresh: refreshSessions } =
    useDataset("/workout/sessions");

  // ── Exercise + history loading ───────────────────────────────────────────────

  async function loadExercises(sessionId: string) {
    setExerciseLoading(true);
    setExerciseError(null);
    const res = await apiFetch<Dataset>(`/workout/sessions/${sessionId}/exercises`);
    if (isApiError(res)) {
      setExerciseError(res);
      setExerciseLoading(false);
      return;
    }
    setExerciseDataset(res);
    setExerciseLoading(false);

    // Fetch history for all unique exercise names in parallel
    const names = [...new Set(res.rows.map(r => r.exercise as string))];
    const results = await Promise.all(
      names.map(name =>
        apiFetch<HistoryData>(`/workout/exercises/history?name=${encodeURIComponent(name)}`)
      )
    );
    const map: Record<string, HistoryData> = {};
    names.forEach((name, i) => {
      const r = results[i];
      if (!isApiError(r)) map[name] = r;
    });
    setHistoryByExercise(map);
  }

  // ── Mutations ───────────────────────────────────────────────────────────────

  async function handleSessionCreate(data: Record<string, unknown>) {
    const res = await apiFetch<Dataset>("/workout/sessions", {
      method: "POST",
      body:   JSON.stringify(data),
    });
    if (isApiError(res)) return res;
    const sessionsRes = await apiFetch<Dataset>("/workout/sessions");
    if (!isApiError(sessionsRes) && sessionsRes.rows.length > 0) {
      setSelectedSession(sessionsRes.rows[0]);
      setExerciseDataset(res);
      setView("exercises");
    } else {
      refreshSessions();
      setView("sessions");
    }
  }

  async function handleExerciseAdd(data: Record<string, unknown>) {
    if (!selectedSession) return;
    const res = await apiFetch<Dataset>(
      `/workout/sessions/${selectedSession.id}/exercises`,
      { method: "POST", body: JSON.stringify(data) },
    );
    if (isApiError(res)) return res;
    setExerciseDataset(res);
    setView("exercises");
  }

  async function handleExerciseSave(data: Record<string, unknown>): Promise<ApiError | null> {
    if (!selectedExercise) return null;
    const res = await apiFetch<Dataset>(
      `/workout/exercises/${selectedExercise.id}`,
      { method: "PATCH", body: JSON.stringify(data) },
    );
    if (isApiError(res)) return res;
    setExerciseDataset(res);
    setSelectedExercise(null);
    setView("exercises");
    // Refresh history in background — doesn't block navigation
    const exerciseName = (data.exercise as string) || (selectedExercise.exercise as string);
    apiFetch<HistoryData>(`/workout/exercises/history?name=${encodeURIComponent(exerciseName)}`)
      .then(histRes => {
        if (!isApiError(histRes)) {
          setHistoryByExercise(prev => ({ ...prev, [exerciseName]: histRes }));
        }
      });
    return null;
  }

  async function handleSessionDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<unknown>(`/workout/sessions/${id}`, { method: "DELETE" });
    if (isApiError(res)) { setMutateError(res); return; }
    refreshSessions();
  }

  async function handleSessionCopy(row: Row) {
    setMutateError(null);
    // Fetch all exercises from the source session
    const exRes = await apiFetch<Dataset>(`/workout/sessions/${row.id}/exercises`);
    if (isApiError(exRes) || exRes.rows.length === 0) return;

    const exercises = exRes.rows;
    const today = new Date().toISOString().split("T")[0];
    const first = exercises[0];

    // Create new session with today's date and the first exercise
    const createRes = await apiFetch<Dataset>("/workout/sessions", {
      method: "POST",
      body: JSON.stringify({
        workout_date: today,
        split:        row.split,
        exercise:     first.exercise,
        weight_kg:    first.weight_kg ?? null,
        set1_reps:    first.set1_reps ?? null,
        set2_reps:    first.set2_reps ?? null,
        set3_reps:    first.set3_reps ?? null,
        set4_reps:    first.set4_reps ?? null,
        set5_reps:    first.set5_reps ?? null,
        comment:      first.comment   ?? null,
      }),
    });
    if (isApiError(createRes)) { setMutateError(createRes); return; }

    // Get the new session id (first row after creation — sorted by date DESC)
    const sessionsRes = await apiFetch<Dataset>("/workout/sessions");
    if (isApiError(sessionsRes) || sessionsRes.rows.length === 0) return;
    const newSession = sessionsRes.rows[0];

    // Add remaining exercises sequentially
    let lastDataset: Dataset = createRes;
    for (const ex of exercises.slice(1)) {
      const addRes = await apiFetch<Dataset>(
        `/workout/sessions/${newSession.id}/exercises`,
        {
          method: "POST",
          body: JSON.stringify({
            exercise:  ex.exercise,
            weight_kg: ex.weight_kg ?? null,
            set1_reps: ex.set1_reps ?? null,
            set2_reps: ex.set2_reps ?? null,
            set3_reps: ex.set3_reps ?? null,
            set4_reps: ex.set4_reps ?? null,
            set5_reps: ex.set5_reps ?? null,
            comment:   ex.comment   ?? null,
          }),
        },
      );
      if (!isApiError(addRes)) lastDataset = addRes;
    }

    refreshSessions();
    setSelectedSession(newSession);
    setExerciseDataset(lastDataset);
    setHistoryByExercise({});
    setView("exercises");
    // Load history for the copied exercises in the background
    const names = [...new Set(exercises.map(e => e.exercise as string))];
    const results = await Promise.all(
      names.map(n => apiFetch<HistoryData>(`/workout/exercises/history?name=${encodeURIComponent(n)}`))
    );
    const map: Record<string, HistoryData> = {};
    names.forEach((n, i) => { if (!isApiError(results[i])) map[n] = results[i] as HistoryData; });
    setHistoryByExercise(map);
  }

  async function handleExerciseDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<Dataset>(`/workout/exercises/${id}`, { method: "DELETE" });
    if (isApiError(res)) { setMutateError(res); return; }
    setExerciseDataset(res);
    if (view === "exercise-view") setView("exercises");
  }

  // ── Navigation ──────────────────────────────────────────────────────────────

  function openSession(row: Row) {
    setSelectedSession(row);
    setHistoryByExercise({});
    loadExercises(row.id);
    setView("exercises");
  }

  function openExerciseView(row: Row) {
    setSelectedExercise(row);
    setView("exercise-view");
  }

  function backToSessions() {
    setView("sessions");
    setSelectedSession(null);
    setExerciseDataset(null);
    setExerciseError(null);
    setMutateError(null);
    setHistoryByExercise({});
  }

  function backToExercises() {
    setSelectedExercise(null);
    setView("exercises");
  }

  // ── Views ────────────────────────────────────────────────────────────────────

  if (view === "session-create") {
    return (
      <div className="page">
        <CreateForm
          title="New Workout Session"
          fields={SESSION_FIELDS}
          submitLabel="Start Session"
          onCancel={() => setView("sessions")}
          onSubmit={handleSessionCreate}
        />
      </div>
    );
  }

  if (view === "exercise-add") {
    return (
      <div className="page">
        <CreateForm
          title="Add Exercise"
          fields={EXERCISE_FIELDS}
          submitLabel="Add Exercise"
          onCancel={() => setView("exercises")}
          onSubmit={handleExerciseAdd}
        />
      </div>
    );
  }

  if (view === "exercise-view" && selectedExercise) {
    const sessionDate = (selectedSession?.workout_date as string) ?? new Date().toISOString().split("T")[0];
    return (
      <ExerciseView
        row={selectedExercise}
        history={historyByExercise[selectedExercise.exercise as string]}
        sessionDate={sessionDate}
        onBack={backToExercises}
        onSave={handleExerciseSave}
      />
    );
  }

  if (view === "exercises") {
    const session = selectedSession;
    const heading = session
      ? `${session.split as string} — ${session.workout_date as string}`
      : "Exercises";
    return (
      <div className="page">
        <div className="page-toolbar">
          <button className="btn-text" onClick={backToSessions}>← Sessions</button>
          <h1 className="type-headline">{heading}</h1>
          <button className="btn-filled" onClick={() => setView("exercise-add")}>+</button>
        </div>

        {exerciseError && <ErrorCard error={exerciseError} />}
        {mutateError   && <ErrorCard error={mutateError} />}

        {exerciseLoading && !exerciseDataset && (
          <p className="type-body" style={{ padding: 16 }}>Loading…</p>
        )}

        <ExerciseList
          dataset={exerciseDataset}
          historyByExercise={historyByExercise}
          onRowClick={openExerciseView}
          onEdit={openExerciseView}
          onDelete={handleExerciseDelete}
        />
      </div>
    );
  }

  // ── Sessions list (default) ──────────────────────────────────────────────────

  if (sessionError) return <ErrorCard error={sessionError} />;

  return (
    <div className="page">
      <div className="page-toolbar">
        <h1 className="type-headline">Workout Sessions</h1>
        <button className="btn-filled" onClick={() => setView("session-create")}>+ New Session</button>
      </div>

      {mutateError && <ErrorCard error={mutateError} />}

      <SessionList
        dataset={sessionDataset}
        onRowClick={openSession}
        onDelete={handleSessionDelete}
        onCopy={handleSessionCopy}
      />
    </div>
  );
}
