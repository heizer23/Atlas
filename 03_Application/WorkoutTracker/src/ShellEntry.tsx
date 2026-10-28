/**
 * WorkoutTracker ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 * All platform imports use the @platform-ui alias.
 *
 * Routes covered:
 *   /workout                     → Session tab (archetype chooser / active workout) — SessionView.tsx
 *   /workout/log                 → Log: finished sessions, archetype filter           — LogView.tsx
 *   /workout/log/exercise?name=  → Exercise history across archetypes (read-only)     — ExerciseHistoryView.tsx
 *   /workout/log/:sessionId      → Session detail (read-only; explicit Edit mode)     — SessionDetailView.tsx
 *   /workout/performance         → Performance view
 *   /workout/settings            → Settings view
 */

import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import SessionView from "./SessionView";
import LogView from "./LogView";
import ExerciseHistoryView from "./ExerciseHistoryView";
import SessionDetailView from "./SessionDetailView";
import { installFreezeLog } from "./freezeLog";
import "./workout.css";

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
    const stopFreezeLog = installFreezeLog();
    return () => {
      stopFreezeLog();
      delete document.body.dataset.app;
    };
  }, []);

  return (
    <Routes>
      <Route path="/" element={<SessionView />} />
      <Route path="/log" element={<LogView />} />
      <Route path="/log/exercise" element={<ExerciseHistoryView />} />
      <Route path="/log/:sessionId" element={<SessionDetailView />} />
      <Route path="/performance" element={<PerformanceView />} />
      <Route path="/settings" element={<SettingsView />} />
    </Routes>
  );
}
