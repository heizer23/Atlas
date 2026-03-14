import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App, { registerPage } from "./App";
import Tasks from "./pages/Tasks";
import WorkoutSessions from "./pages/WorkoutSessions";

// ── Register application pages ────────────────────────────────────────────────
registerPage("tasks",   "Tasks",   Tasks);
registerPage("workout", "Workout", WorkoutSessions);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
