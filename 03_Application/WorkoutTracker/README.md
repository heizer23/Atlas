# WorkoutTracker MVP

Minimal FastAPI workout logger.

## Setup

1.  Ensure `01_System/secrets.env` exists (with `ATLAS_PG_*` vars).
2.  Install dependencies:
    ```bash
    pip install .
    ```

## Running (Windows)

Use the provided PowerShell script:

```powershell
.\run_local.ps1
```

Access at [http://localhost:8000](http://localhost:8000).

## DB Schema

Contract: `02_Platform/01_Postgres/ObjectSchemas/workout_schema.sql`.
Single table `workout.workout_log` with `workout_id` for session grouping.
