import { useState, useEffect, useCallback } from "react";
import { getRequestLog } from "../api/client";

// Toggle with Ctrl+Shift+D. Shows last 50 API requests + platform gap events.
export default function DebugPanel() {
  const [open,    setOpen]    = useState(false);
  const [entries, setEntries] = useState(getRequestLog());
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = useCallback((e: KeyboardEvent) => {
    if (e.ctrlKey && e.shiftKey && e.key === "D") {
      e.preventDefault();
      setOpen(o => !o);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", toggle);
    return () => window.removeEventListener("keydown", toggle);
  }, [toggle]);

  // Refresh log on open
  useEffect(() => {
    if (open) setEntries([...getRequestLog()]);
  }, [open]);

  function toggleEntry(i: number) {
    setExpanded(s => {
      const next = new Set(s);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  }

  if (!open) return null;

  return (
    <div className="debug-panel open">
      <div className="debug-panel-header">
        <span className="type-title">Debug Panel</span>
        <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "center" }}>
          <button className="btn-text" onClick={() => setEntries([...getRequestLog()])}>
            Refresh
          </button>
          <button className="icon-btn" onClick={() => setOpen(false)} title="Close">
            <span className="material-symbols-rounded">close</span>
          </button>
        </div>
      </div>

      <div className="debug-panel-body">
        {entries.length === 0 && (
          <p className="type-label" style={{ padding: "var(--space-md)", color: "var(--md-sys-color-on-surface-variant)" }}>
            No requests yet.
          </p>
        )}
        {entries.map((entry, i) => {
          const isGap = entry.url.startsWith("[PLATFORM GAP]");
          const statusOk = entry.status >= 200 && entry.status < 300;
          return (
            <div key={i} className="debug-entry">
              <div className="debug-entry-header" onClick={() => toggleEntry(i)}>
                {isGap ? (
                  <span className="debug-status err">[GAP]</span>
                ) : (
                  <span className={`debug-status ${statusOk ? "ok" : "err"}`}>
                    {entry.status || "ERR"}
                  </span>
                )}
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {entry.method} {entry.url}
                </span>
                {!isGap && (
                  <span style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
                    {entry.duration}ms
                  </span>
                )}
                <span style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
                  {entry.request_id}
                </span>
              </div>
              {expanded.has(i) && (
                <div className="debug-entry-body">
                  {JSON.stringify(entry.response, null, 2)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
