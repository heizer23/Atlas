/**
 * WorkoutTracker ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 * All platform imports use the @platform-ui alias.
 *
 * Routes covered:
 *   /workout              → Sessions list (Log tab)
 *   /workout/performance  → Performance view
 *   /workout/history      → History view
 *   /workout/settings     → Settings view
 */

import { useState, useEffect, useRef } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import { useDataset } from "@platform-ui/hooks/useDataset";
import CreateForm from "@platform-ui/components/CreateForm";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { Row, FormField, Dataset, ApiError } from "@platform-ui/api/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type HistoryData = { rows: Row[] };

// ── Form field definitions ────────────────────────────────────────────────────

const SESSION_FIELDS: FormField[] = [
  { key: "workout_date", label: "Date",        type: "date",   required: true },
  { key: "split",        label: "Split",       type: "string", required: true, placeholder: "e.g. Push, Pull, Legs" },
  { key: "exercise",     label: "Exercise",    type: "string", required: true },
  { key: "weight_kg",   label: "Weight (kg)", type: "number", placeholder: "optional" },
  { key: "set1_reps",   label: "Set 1 Reps",  type: "number" },
  { key: "set2_reps",   label: "Set 2 Reps",  type: "number" },
  { key: "set3_reps",   label: "Set 3 Reps",  type: "number" },
  { key: "set4_reps",   label: "Set 4 Reps",  type: "number" },
  { key: "set5_reps",   label: "Set 5 Reps",  type: "number" },
  { key: "comment",     label: "Comment",     type: "string" },
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

const SET_COLORS = [
  "var(--atlas-chart-1)",
  "var(--atlas-chart-2)",
  "var(--atlas-chart-3)",
  "var(--atlas-chart-4)",
  "var(--md-sys-color-secondary)",
];

// ── HistoryChart ──────────────────────────────────────────────────────────────

function HistoryChart({
  history,
  size,
  liveRow,
}: {
  history: HistoryData | undefined;
  size: "mini" | "full";
  liveRow?: Record<string, unknown>;
}) {
  if (!history) {
    if (size === "mini") {
      return (
        <div
          style={{
            flex: "1 1 0",
            minWidth: 0,
            overflow: "hidden",
            display: "flex",
            alignItems: "flex-end",
            gap: 5,
            height: 46,
          }}
        >
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 20,
                background: "var(--md-sys-color-outline-variant)",
                borderRadius: "3px 3px 0 0",
              }}
            />
          ))}
        </div>
      );
    }
    return (
      <div
        style={{
          height: 200,
          background: "var(--md-sys-color-surface-variant)",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--md-sys-color-on-surface-variant)",
          fontSize: 14,
        }}
      >
        Loading history…
      </div>
    );
  }

  const baseRows = (
    size === "mini" ? history.rows.slice(-8) : history.rows
  ) as Record<string, unknown>[];
  const data =
    size === "full" && liveRow ? [...baseRows, liveRow] : baseRows;

  if (size === "mini") {
    return (
      <div
        style={{ flex: "1 1 0", minWidth: 0, overflow: "hidden", height: 46 }}
      >
        <ResponsiveContainer width="100%" height={46}>
          <BarChart
            data={data}
            margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
            barCategoryGap="20%"
          >
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

  return (
    <div style={{ background: "var(--md-sys-color-surface-variant)", borderRadius: 8, padding: 16 }}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="0" stroke="var(--md-sys-color-outline-variant)" vertical={false} />
          <XAxis dataKey="workout_date" axisLine={false} tickLine={false} tick={false} />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "var(--md-sys-color-on-surface-variant)", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--md-sys-color-surface)",
              border: "1px solid var(--md-sys-color-outline-variant)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(label) => String(label)}
            formatter={(value, name) => [
              `${value} reps`,
              String(name).replace("_reps", "").replace("set", "Set "),
            ]}
          />
          {SET_COLORS.map((color, si) => (
            <Bar
              key={si}
              dataKey={`set${si + 1}_reps`}
              stackId="a"
              fill={color}
              radius={si === 4 ? [4, 4, 0, 0] : undefined}
            >
              {data.map((entry, di) => (
                <Cell
                  key={di}
                  fill={color}
                  fillOpacity={
                    (entry as Record<string, unknown>)._active ? 1 : 0.38
                  }
                />
              ))}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Exercise row ──────────────────────────────────────────────────────────────

interface ExerciseRowProps {
  row: Row;
  history: HistoryData | undefined;
  menuOpen: boolean;
  onToggleMenu: (e: React.MouseEvent) => void;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function ExerciseRow({
  row,
  history,
  menuOpen,
  onToggleMenu,
  onClick,
  onEdit,
  onDelete,
}: ExerciseRowProps) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        padding: "12px 16px",
        minHeight: 80,
        borderBottom: "1px solid var(--md-sys-color-outline-variant)",
        gap: 12,
        cursor: "pointer",
        position: "relative",
        transition: "background 200ms",
        background: "transparent",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "color-mix(in srgb, var(--md-sys-color-primary) 8%, transparent)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <div style={{ flex: "0 0 100px", flexShrink: 0 }}>
        <div
          style={{
            fontSize: 16,
            fontWeight: 500,
            lineHeight: "24px",
            color: "var(--md-sys-color-on-surface)",
            letterSpacing: ".15px",
          }}
        >
          {String(row.exercise ?? "")}
        </div>
        {row.weight_kg != null && (
          <div
            style={{
              fontSize: 14,
              fontWeight: 400,
              lineHeight: "20px",
              color: "var(--md-sys-color-on-surface-variant)",
              letterSpacing: ".25px",
            }}
          >
            {String(row.weight_kg)} kg
          </div>
        )}
      </div>

      <HistoryChart history={history} size="mini" />

      <div
        style={{ flexShrink: 0, position: "relative" }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onToggleMenu}
          style={{
            width: 40,
            height: 40,
            border: "none",
            borderRadius: "50%",
            background: "transparent",
            color: "var(--md-sys-color-on-surface-variant)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
          aria-label="More options"
        >
          <span className="material-symbols-rounded" style={{ fontSize: 24 }}>
            more_vert
          </span>
        </button>

        {menuOpen && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              right: 0,
              minWidth: 168,
              background: "var(--md-sys-color-surface-variant)",
              borderRadius: 4,
              boxShadow: "0 2px 6px 2px rgba(0,0,0,.15), 0 1px 2px rgba(0,0,0,.3)",
              padding: "8px 0",
              zIndex: 100,
            }}
          >
            <div
              onClick={onEdit}
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
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: "var(--md-sys-color-on-surface-variant)" }}>
                edit
              </span>
              Edit
            </div>
            <div style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "8px 0" }} />
            <div
              onClick={onDelete}
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
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(28,27,31,.08)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: "var(--md-sys-color-on-surface-variant)" }}>
                delete
              </span>
              Delete
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── ExerciseList ──────────────────────────────────────────────────────────────

interface ExerciseListProps {
  dataset: Dataset | null;
  historyByExercise: Record<string, HistoryData>;
  onRowClick: (row: Row) => void;
  onEdit: (row: Row) => void;
  onDelete: (id: string) => void;
}

function ExerciseList({
  dataset,
  historyByExercise,
  onRowClick,
  onEdit,
  onDelete,
}: ExerciseListProps) {
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

  if (!dataset)
    return <p className="type-body">Loading…</p>;
  if (dataset.rows.length === 0)
    return <p className="type-body">No exercises yet.</p>;

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
        <ExerciseRow
          key={row.id}
          row={row}
          history={historyByExercise[row.exercise as string]}
          menuOpen={openMenuId === row.id}
          onToggleMenu={() =>
            setOpenMenuId(openMenuId === row.id ? null : row.id)
          }
          onClick={() => {
            setOpenMenuId(null);
            onRowClick(row);
          }}
          onEdit={() => {
            setOpenMenuId(null);
            onEdit(row);
          }}
          onDelete={() => {
            setOpenMenuId(null);
            onDelete(row.id);
          }}
        />
      ))}
    </div>
  );
}

// ── ExerciseView ──────────────────────────────────────────────────────────────

interface ExerciseViewProps {
  row: Row;
  history: HistoryData | undefined;
  onBack: () => void;
  onSave: (data: Record<string, unknown>) => Promise<ApiError | null>;
}

function ExerciseView({ row, history, onBack, onSave }: ExerciseViewProps) {
  const [name, setName] = useState(row.exercise as string);
  const [weight, setWeight] = useState(
    row.weight_kg != null ? String(row.weight_kg) : ""
  );
  const initReps = [1, 2, 3, 4, 5].map((i) =>
    String((row as Record<string, unknown>)[`set${i}_reps`] ?? "")
  );
  const [reps, setReps] = useState(initReps);
  const [comment, setComment] = useState(String(row.comment ?? ""));
  const [completed, setCompleted] = useState(
    [0, 1, 2, 3, 4].map((i) => parseInt(initReps[i]) > 0)
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const filteredHistory: HistoryData | undefined = history
    ? { rows: history.rows.filter((r) => r.id !== row.id) }
    : undefined;

  const liveRow: Record<string, unknown> = {
    workout_date: "Today",
    _active: true,
    set1_reps: completed[0] ? parseInt(reps[0]) || 0 : 0,
    set2_reps: completed[1] ? parseInt(reps[1]) || 0 : 0,
    set3_reps: completed[2] ? parseInt(reps[2]) || 0 : 0,
    set4_reps: completed[3] ? parseInt(reps[3]) || 0 : 0,
    set5_reps: completed[4] ? parseInt(reps[4]) || 0 : 0,
  };

  function adjustRep(i: number, delta: number) {
    setReps((prev) => {
      const next = [...prev];
      next[i] = String(Math.max(0, (parseInt(next[i]) || 0) + delta));
      return next;
    });
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    const data = {
      exercise: name.trim(),
      weight_kg: weight !== "" ? parseFloat(weight) : null,
      set1_reps: reps[0] !== "" ? parseInt(reps[0]) : null,
      set2_reps: reps[1] !== "" ? parseInt(reps[1]) : null,
      set3_reps: reps[2] !== "" ? parseInt(reps[2]) : null,
      set4_reps: reps[3] !== "" ? parseInt(reps[3]) : null,
      set5_reps: reps[4] !== "" ? parseInt(reps[4]) : null,
      comment: comment || null,
    };
    const err = await onSave(data);
    if (err) setError(err);
    setBusy(false);
  }

  return (
    <div className="page">
      <div className="page-toolbar">
        <button className="icon-btn" onClick={onBack} aria-label="Back">
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
      </div>

      {error && <ErrorCard error={error} />}

      <div style={{ padding: "0 0 16px" }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{
            width: "100%",
            border: "none",
            borderBottom: "2px solid var(--md-sys-color-primary)",
            fontSize: 22,
            fontWeight: 500,
            color: "var(--md-sys-color-on-surface)",
            background: "transparent",
            padding: "4px 0",
            outline: "none",
            letterSpacing: ".15px",
          }}
        />
      </div>

      <div
        style={{
          padding: "0 0 16px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <label style={{ fontSize: 14, color: "var(--md-sys-color-on-surface-variant)", minWidth: 60 }}>
          Weight
        </label>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            border: "1px solid var(--md-sys-color-outline-variant)",
            borderRadius: 8,
            overflow: "hidden",
            flex: "0 0 140px",
          }}
        >
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder="—"
            style={{
              flex: 1,
              border: "none",
              padding: "8px 12px",
              fontSize: 16,
              color: "var(--md-sys-color-on-surface)",
              background: "transparent",
              outline: "none",
            }}
          />
          <span style={{ paddingRight: 12, fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}>
            kg
          </span>
        </div>
      </div>

      <div style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "0 0 16px" }} />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          padding: "0 0 16px",
        }}
      >
        {[0, 1, 2, 3, 4].map((i) => {
          const done = completed[i];
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 12px",
                border: `1px solid ${done ? "var(--md-sys-color-primary)" : "var(--md-sys-color-outline-variant)"}`,
                borderRadius: 8,
                background: done ? "color-mix(in srgb, var(--md-sys-color-primary) 6%, transparent)" : "var(--md-sys-color-surface)",
                transition: "all 0.15s",
              }}
            >
              <span
                style={{
                  flex: "0 0 44px",
                  fontSize: 14,
                  fontWeight: 500,
                  color: done ? "var(--md-sys-color-primary)" : "var(--md-sys-color-on-surface-variant)",
                }}
              >
                Set {i + 1}
              </span>
              <button
                onClick={() => adjustRep(i, -1)}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 16,
                  border: "none",
                  background: "var(--md-sys-color-surface-variant)",
                  cursor: "pointer",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  color: "var(--md-sys-color-on-surface-variant)",
                }}
              >
                −
              </button>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <input
                  type="number"
                  value={reps[i]}
                  onChange={(e) => {
                    const next = [...reps];
                    next[i] = e.target.value;
                    setReps(next);
                  }}
                  placeholder="0"
                  style={{
                    width: "100%",
                    textAlign: "center",
                    border: "1px solid var(--md-sys-color-outline-variant)",
                    borderRadius: 8,
                    padding: "6px 40px 6px 8px",
                    fontSize: 16,
                    color: "var(--md-sys-color-on-surface)",
                    background: "transparent",
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
                <span
                  style={{
                    position: "absolute",
                    right: 10,
                    fontSize: 12,
                    color: "var(--md-sys-color-on-surface-variant)",
                    pointerEvents: "none",
                  }}
                >
                  reps
                </span>
              </div>
              <button
                onClick={() => adjustRep(i, 1)}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 16,
                  border: "none",
                  background: "var(--md-sys-color-surface-variant)",
                  cursor: "pointer",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  color: "var(--md-sys-color-on-surface-variant)",
                }}
              >
                +
              </button>
              <button
                onClick={() =>
                  setCompleted((prev) => {
                    const n = [...prev];
                    n[i] = !n[i];
                    return n;
                  })
                }
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 18,
                  border: "none",
                  flexShrink: 0,
                  background: done ? "var(--md-sys-color-primary)" : "var(--md-sys-color-surface-variant)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "background 0.15s",
                }}
                aria-label={done ? "Unmark set" : "Mark set done"}
              >
                <span
                  className="material-symbols-rounded"
                  style={{ fontSize: 18, color: done ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-on-surface-variant)" }}
                >
                  {done ? "check" : "close"}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      <div style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "0 0 16px" }} />

      <div style={{ padding: "0 0 16px" }}>
        <HistoryChart
          history={filteredHistory}
          size="full"
          liveRow={completed.some((c) => c) ? liveRow : undefined}
        />
      </div>

      <div style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "0 0 16px" }} />

      <div style={{ padding: "0 0 16px" }}>
        <label
          style={{
            display: "block",
            fontSize: 14,
            color: "var(--md-sys-color-on-surface-variant)",
            marginBottom: 8,
          }}
        >
          Comment
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add notes about your workout…"
          rows={3}
          style={{
            width: "100%",
            border: "1px solid var(--md-sys-color-outline-variant)",
            borderRadius: 8,
            padding: "10px 12px",
            fontSize: 14,
            color: "var(--md-sys-color-on-surface)",
            background: "var(--md-sys-color-surface)",
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
      </div>

      <div style={{ display: "flex", gap: 12, padding: "0 0 24px" }}>
        <button
          className="btn-filled"
          onClick={handleSave}
          disabled={busy}
          style={{ flex: 1 }}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button className="btn-text" onClick={onBack}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── SessionList ───────────────────────────────────────────────────────────────

interface SessionListProps {
  dataset: Dataset | null;
  onRowClick: (row: Row) => void;
  onDelete: (id: string) => void;
  onCopy: (row: Row) => void;
}

function SessionList({
  dataset,
  onRowClick,
  onDelete,
  onCopy,
}: SessionListProps) {
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
            setOpenMenuId(null);
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
            style={{ flexShrink: 0, position: "relative" }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() =>
                setOpenMenuId(openMenuId === row.id ? null : row.id)
              }
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

            {openMenuId === row.id && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 4px)",
                  right: 0,
                  minWidth: 160,
                  background: "var(--md-sys-color-surface-variant)",
                  borderRadius: 4,
                  boxShadow:
                    "0 2px 6px 2px rgba(0,0,0,.15), 0 1px 2px rgba(0,0,0,.3)",
                  padding: "8px 0",
                  zIndex: 100,
                }}
              >
                <div
                  onClick={() => {
                    setOpenMenuId(null);
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
                    content_copy
                  </span>
                  Copy
                </div>
                <div
                  style={{ height: 1, background: "var(--md-sys-color-outline-variant)", margin: "4px 0" }}
                />
                <div
                  onClick={() => {
                    setOpenMenuId(null);
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

// ── LogView (sessions list — default /workout route) ──────────────────────────

function LogView() {
  const navigate = useNavigate();

  const [selectedSession, setSelectedSession] = useState<Row | null>(null);
  const [selectedExercise, setSelectedExercise] = useState<Row | null>(null);
  const [exerciseDataset, setExerciseDataset] = useState<Dataset | null>(null);
  const [exerciseLoading, setExerciseLoading] = useState(false);
  const [exerciseError, setExerciseError] = useState<ApiError | null>(null);
  const [mutateError, setMutateError] = useState<ApiError | null>(null);
  const [historyByExercise, setHistoryByExercise] = useState<Record<string, HistoryData>>({});
  const [innerView, setInnerView] = useState<
    "sessions" | "exercises" | "exercise-view" | "session-create" | "exercise-add"
  >("sessions");

  const { dataset: sessionDataset, error: sessionError, refresh: refreshSessions } =
    useDataset("/workout/sessions");

  // Suppress unused warning — navigate is available for future sub-routing needs
  void navigate;

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
    const names = [...new Set(res.rows.map((r) => r.exercise as string))];
    const results = await Promise.all(
      names.map((name) =>
        apiFetch<HistoryData>(
          `/workout/exercises/history?name=${encodeURIComponent(name)}`
        )
      )
    );
    const map: Record<string, HistoryData> = {};
    names.forEach((name, i) => {
      const r = results[i];
      if (!isApiError(r)) map[name] = r;
    });
    setHistoryByExercise(map);
  }

  async function handleSessionCreate(data: Record<string, unknown>) {
    const res = await apiFetch<Dataset>("/workout/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (isApiError(res)) return res;
    const sessionsRes = await apiFetch<Dataset>("/workout/sessions");
    if (!isApiError(sessionsRes) && sessionsRes.rows.length > 0) {
      setSelectedSession(sessionsRes.rows[0]);
      setExerciseDataset(res);
      setInnerView("exercises");
    } else {
      refreshSessions();
      setInnerView("sessions");
    }
  }

  async function handleExerciseAdd(data: Record<string, unknown>) {
    if (!selectedSession) return;
    const res = await apiFetch<Dataset>(
      `/workout/sessions/${selectedSession.id}/exercises`,
      { method: "POST", body: JSON.stringify(data) }
    );
    if (isApiError(res)) return res;
    setExerciseDataset(res);
    setInnerView("exercises");
  }

  async function handleExerciseSave(
    data: Record<string, unknown>
  ): Promise<ApiError | null> {
    if (!selectedExercise) return null;
    const res = await apiFetch<Dataset>(
      `/workout/exercises/${selectedExercise.id}`,
      { method: "PATCH", body: JSON.stringify(data) }
    );
    if (isApiError(res)) return res;
    setExerciseDataset(res);
    setSelectedExercise(null);
    setInnerView("exercises");
    const exerciseName =
      (data.exercise as string) || (selectedExercise.exercise as string);
    apiFetch<HistoryData>(
      `/workout/exercises/history?name=${encodeURIComponent(exerciseName)}`
    ).then((histRes) => {
      if (!isApiError(histRes)) {
        setHistoryByExercise((prev) => ({ ...prev, [exerciseName]: histRes }));
      }
    });
    return null;
  }

  async function handleSessionDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<unknown>(`/workout/sessions/${id}`, {
      method: "DELETE",
    });
    if (isApiError(res)) {
      setMutateError(res);
      return;
    }
    refreshSessions();
  }

  async function handleSessionCopy(row: Row) {
    setMutateError(null);
    const exRes = await apiFetch<Dataset>(
      `/workout/sessions/${row.id}/exercises`
    );
    if (isApiError(exRes) || exRes.rows.length === 0) return;
    const exercises = exRes.rows;
    const today = new Date().toISOString().split("T")[0];
    const first = exercises[0];
    const createRes = await apiFetch<Dataset>("/workout/sessions", {
      method: "POST",
      body: JSON.stringify({
        workout_date: today,
        split: row.split,
        exercise: first.exercise,
        weight_kg: first.weight_kg ?? null,
        set1_reps: first.set1_reps ?? null,
        set2_reps: first.set2_reps ?? null,
        set3_reps: first.set3_reps ?? null,
        set4_reps: first.set4_reps ?? null,
        set5_reps: first.set5_reps ?? null,
        comment: first.comment ?? null,
      }),
    });
    if (isApiError(createRes)) {
      setMutateError(createRes);
      return;
    }
    const sessionsRes = await apiFetch<Dataset>("/workout/sessions");
    if (isApiError(sessionsRes) || sessionsRes.rows.length === 0) return;
    const newSession = sessionsRes.rows[0];
    let lastDataset: Dataset = createRes;
    for (const ex of exercises.slice(1)) {
      const addRes = await apiFetch<Dataset>(
        `/workout/sessions/${newSession.id}/exercises`,
        {
          method: "POST",
          body: JSON.stringify({
            exercise: ex.exercise,
            weight_kg: ex.weight_kg ?? null,
            set1_reps: ex.set1_reps ?? null,
            set2_reps: ex.set2_reps ?? null,
            set3_reps: ex.set3_reps ?? null,
            set4_reps: ex.set4_reps ?? null,
            set5_reps: ex.set5_reps ?? null,
            comment: ex.comment ?? null,
          }),
        }
      );
      if (!isApiError(addRes)) lastDataset = addRes;
    }
    refreshSessions();
    setSelectedSession(newSession);
    setExerciseDataset(lastDataset);
    setHistoryByExercise({});
    setInnerView("exercises");
    const names = [...new Set(exercises.map((e) => e.exercise as string))];
    const results = await Promise.all(
      names.map((n) =>
        apiFetch<HistoryData>(
          `/workout/exercises/history?name=${encodeURIComponent(n)}`
        )
      )
    );
    const map: Record<string, HistoryData> = {};
    names.forEach((n, i) => {
      if (!isApiError(results[i])) map[n] = results[i] as HistoryData;
    });
    setHistoryByExercise(map);
  }

  async function handleExerciseDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<Dataset>(`/workout/exercises/${id}`, {
      method: "DELETE",
    });
    if (isApiError(res)) {
      setMutateError(res);
      return;
    }
    setExerciseDataset(res);
    if (innerView === "exercise-view") setInnerView("exercises");
  }

  function openSession(row: Row) {
    setSelectedSession(row);
    setHistoryByExercise({});
    loadExercises(row.id);
    setInnerView("exercises");
  }

  if (innerView === "session-create") {
    return (
      <div className="page">
        <CreateForm
          title="New Workout Session"
          fields={SESSION_FIELDS}
          submitLabel="Start Session"
          onCancel={() => setInnerView("sessions")}
          onSubmit={handleSessionCreate}
        />
      </div>
    );
  }

  if (innerView === "exercise-add") {
    return (
      <div className="page">
        <CreateForm
          title="Add Exercise"
          fields={EXERCISE_FIELDS}
          submitLabel="Add Exercise"
          onCancel={() => setInnerView("exercises")}
          onSubmit={handleExerciseAdd}
        />
      </div>
    );
  }

  if (innerView === "exercise-view" && selectedExercise) {
    return (
      <ExerciseView
        row={selectedExercise}
        history={historyByExercise[selectedExercise.exercise as string]}
        onBack={() => {
          setSelectedExercise(null);
          setInnerView("exercises");
        }}
        onSave={handleExerciseSave}
      />
    );
  }

  if (innerView === "exercises") {
    const heading = selectedSession
      ? `${selectedSession.split as string} — ${selectedSession.workout_date as string}`
      : "Exercises";
    return (
      <div className="page">
        <div className="page-toolbar">
          <button
            className="icon-btn"
            aria-label="Back to sessions"
            onClick={() => {
              setInnerView("sessions");
              setSelectedSession(null);
              setExerciseDataset(null);
              setExerciseError(null);
              setMutateError(null);
              setHistoryByExercise({});
            }}
          >
            <span className="material-symbols-rounded">arrow_back</span>
          </button>
          <h1 className="type-headline">{heading}</h1>
          <button
            className="icon-btn filled"
            aria-label="Add exercise"
            onClick={() => setInnerView("exercise-add")}
          >
            <span className="material-symbols-rounded">add</span>
          </button>
        </div>

        {exerciseError && <ErrorCard error={exerciseError} />}
        {mutateError && <ErrorCard error={mutateError} />}

        {exerciseLoading && !exerciseDataset && (
          <p className="type-body">Loading…</p>
        )}

        <ExerciseList
          dataset={exerciseDataset}
          historyByExercise={historyByExercise}
          onRowClick={(row) => {
            setSelectedExercise(row);
            setInnerView("exercise-view");
          }}
          onEdit={(row) => {
            setSelectedExercise(row);
            setInnerView("exercise-view");
          }}
          onDelete={handleExerciseDelete}
        />
      </div>
    );
  }

  // Default: sessions list
  if (sessionError) return <ErrorCard error={sessionError} />;

  return (
    <div className="page">
      <div className="page-header">
        <button
          className="icon-btn filled"
          aria-label="New session"
          onClick={() => setInnerView("session-create")}
        >
          <span className="material-symbols-rounded">add</span>
        </button>
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

// ── Placeholder views for Performance, History, Settings ──────────────────────

function PerformanceView() {
  return (
    <div className="page">
      <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
        Performance analytics coming soon.
      </p>
    </div>
  );
}

function HistoryView() {
  return (
    <div className="page">
      <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
        Full workout history coming soon.
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
  return (
    <Routes>
      <Route path="/" element={<LogView />} />
      <Route path="/performance" element={<PerformanceView />} />
      <Route path="/history" element={<HistoryView />} />
      <Route path="/settings" element={<SettingsView />} />
    </Routes>
  );
}
