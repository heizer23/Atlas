import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App, { registerPage } from "./App";
import Tasks from "./pages/Tasks";

// ── Register application pages ────────────────────────────────────────────────
registerPage("tasks", "Tasks", Tasks);

// ── Add further pages here as applications are built ─────────────────────────
// import WorkoutSessions from "./pages/WorkoutSessions";
// registerPage("workout", "Workout", WorkoutSessions);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
