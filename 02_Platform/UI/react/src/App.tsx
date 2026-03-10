import { useState, useEffect, useCallback, type ComponentType } from "react";
import DebugPanel from "./components/DebugPanel";

// ── Page registry ─────────────────────────────────────────────────────────────
// Applications register their pages here at import time.
// Import the page module in main.tsx, then call registerPage.
//
// Example (in main.tsx):
//   import Tasks from "./pages/Tasks";
//   registerPage("tasks", "Tasks", Tasks);

export const _registry: Record<string, { label: string; component: ComponentType }> = {};

export function registerPage(
  id:        string,
  label:     string,
  component: ComponentType
) {
  _registry[id] = { label, component };
}

// ── Simple hash router ────────────────────────────────────────────────────────
function currentHash(): string {
  return window.location.hash.replace("#", "");
}

export default function App() {
  const [pageId, setPageId] = useState(currentHash);

  const onHashChange = useCallback(() => setPageId(currentHash()), []);

  useEffect(() => {
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [onHashChange]);

  // Default to first registered page if hash is empty or unknown
  const resolvedId =
    _registry[pageId]
      ? pageId
      : Object.keys(_registry)[0] ?? "";

  const current = _registry[resolvedId];

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="nav-brand type-title">Atlas</div>
        {Object.entries(_registry).map(([id, { label }]) => (
          <a
            key={id}
            href={`#${id}`}
            className={`nav-item type-body${resolvedId === id ? " active" : ""}`}
          >
            {label}
          </a>
        ))}
      </nav>

      <main className="app-content">
        {current ? (
          <current.component />
        ) : (
          <p className="type-body" style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
            No pages registered. Import a page and call{" "}
            <code>registerPage()</code> in <code>main.tsx</code>.
          </p>
        )}
      </main>

      <DebugPanel />
    </div>
  );
}
