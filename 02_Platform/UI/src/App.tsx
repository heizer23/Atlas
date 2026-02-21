import { useMemo, useState, useEffect } from "react";
// Use type import for types to avoid runtime issues
import { TableView, type Row, type SpecialAction } from "./components/TableView";

type ViewMode = "sessions" | "exercises";

export default function App() {
  console.log("App component mounting...");

  const [viewMode, setViewMode] = useState<ViewMode>("sessions");
  const [selectedWorkoutId, setSelectedWorkoutId] = useState<string | null>(null);
  const [selectedWorkoutMeta, setSelectedWorkoutMeta] = useState<{ date: string; split: string } | null>(null);

  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const sessionColumns = useMemo(
    () => [
      { key: "workout_id", label: "ID" },
      { key: "workout_date", label: "Date" },
      { key: "split", label: "Split" },
      { key: "exercise_count", label: "Exercises" },
    ],
    []
  );

  const exerciseColumns = useMemo(
    () => [
      { key: "workout_log_id", label: "ID" },
      { key: "exercise", label: "Exercise" },
      { key: "weight_kg", label: "Weight (kg)" },
      { key: "set1_reps", label: "Set 1" },
      { key: "set2_reps", label: "Set 2" },
      { key: "set3_reps", label: "Set 3" },
      { key: "set4_reps", label: "Set 4" },
      { key: "set5_reps", label: "Set 5" },
      { key: "comment", label: "Comment" },
    ],
    []
  );

  const fetchSessions = async () => {
    try {
      console.log("Fetching sessions from API...");
      setLoading(true);
      const response = await fetch("http://localhost:8000/api/workouts");
      console.log("Response received:", response.status);

      if (!response.ok) {
        throw new Error(`Failed to fetch sessions: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log("Data payload:", data);

      if (!Array.isArray(data)) {
        throw new Error("API response is not an array");
      }

      setRows(data);
      setError(null);
    } catch (err) {
      console.error("Error in fetchSessions:", err);
      setError(err instanceof Error ? err.message : "An unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const fetchExercises = async (workoutId: string) => {
    try {
      console.log(`Fetching exercises for workout ${workoutId}...`);
      setLoading(true);
      const response = await fetch(`http://localhost:8000/api/workouts/${workoutId}/exercises`);
      console.log("Response received:", response.status);

      if (!response.ok) {
        throw new Error(`Failed to fetch exercises: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log("Exercise data:", data);

      if (!Array.isArray(data)) {
        throw new Error("API response is not an array");
      }

      setRows(data);
      setError(null);
    } catch (err) {
      console.error("Error in fetchExercises:", err);
      setError(err instanceof Error ? err.message : "An unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (viewMode === "sessions") {
      fetchSessions();
    } else if (viewMode === "exercises" && selectedWorkoutId) {
      fetchExercises(selectedWorkoutId);
    }
  }, [viewMode, selectedWorkoutId]);

  const onDeleteSession = (row: Row) => {
    if (window.confirm(`Are you sure you want to delete session ${row.workout_id}?`)) {
      // TODO: Call DELETE API endpoint
      setRows((prev) => prev.filter((r) => r.workout_id !== row.workout_id));
    }
  };

  const onDeleteExercise = (row: Row) => {
    if (window.confirm(`Are you sure you want to delete exercise ${row.exercise}?`)) {
      // TODO: Call DELETE API endpoint
      setRows((prev) => prev.filter((r) => r.workout_log_id !== row.workout_log_id));
    }
  };

  const viewSessionExercises: SpecialAction = {
    label: "View",
    onClick: (row) => {
      console.log("Viewing exercises for session:", row);
      setSelectedWorkoutId(row.workout_id);
      setSelectedWorkoutMeta({ date: row.workout_date, split: row.split });
      setViewMode("exercises");
    },
  };

  const editExercise: SpecialAction = {
    label: "Edit",
    onClick: (row) => {
      alert(`Edit functionality for exercise ${row.exercise} (ID: ${row.workout_log_id}) - Coming soon!`);
    },
  };

  const backToSessions = () => {
    setViewMode("sessions");
    setSelectedWorkoutId(null);
    setSelectedWorkoutMeta(null);
  };

  if (loading) {
    return (
      <div style={{ padding: 20, fontFamily: "sans-serif" }}>
        <h2>Loading...</h2>
        <p>Please wait while we connect to the server.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, fontFamily: "sans-serif", color: "red" }}>
        <h2>Error Loading Data</h2>
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  // Defensive check before rendering TableView
  if (!rows) {
    return <div>Error: Rows data is missing.</div>;
  }

  if (viewMode === "exercises") {
    return (
      <div className="app-container">
        <div style={{ padding: 16, fontFamily: "system-ui, sans-serif" }}>
          <button onClick={backToSessions} style={{ marginBottom: 16 }}>
            ← Back to Sessions
          </button>
          {selectedWorkoutMeta && (
            <div style={{ marginBottom: 16 }}>
              <strong>Date:</strong> {selectedWorkoutMeta.date} | <strong>Split:</strong> {selectedWorkoutMeta.split}
            </div>
          )}
        </div>
        <TableView
          title="Exercises"
          columns={exerciseColumns}
          rows={rows}
          onDelete={onDeleteExercise}
          special={editExercise}
        />
      </div>
    );
  }

  return (
    <div className="app-container">
      <TableView
        title="Atlas UI – Workout Sessions"
        columns={sessionColumns}
        rows={rows}
        onDelete={onDeleteSession}
        special={viewSessionExercises}
      />
    </div>
  );
}
