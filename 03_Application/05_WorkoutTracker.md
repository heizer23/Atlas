
# WorkoutTracker Application

## Purpose
Track workouts as structured, queryable events to support reflection,
trend analysis, and later automation.

This is the first real Atlas application and serves as a reference
implementation for contract-first development.

## Scope
- Single-user
- Local-first
- Postgres-backed
- No auth, no sharing, no UI polish (yet)

## Access / UI

Phase 1:
- Minimal web application.
- Server-side rendered HTML.
- Runs locally alongside the platform (Postgres).

Technology direction (non-binding):
- HTTP-based access.
- No frontend framework.
- Simple forms for data entry, simple tables for browsing.

Access model:
- Desktop: localhost access.
- Pi: local network access only (no public exposure).

## Data Contract (Authoritative)

**Stability rule:** Code is disposable; data contracts are not.

Code is disposable; data contracts are not
The WorkoutTracker application is bound to the following schema:

- `02_Platform/01_Postgres/ObjectSchemas/workout_schema.sql`

This file defines:
- all durable domain objects
- their structure and constraints
- the write surface of the application

This schema is considered **stable**.
Changes require:
- an explicit reason
- an update to this document
- a conscious contract evolution (not an ad-hoc edit).
## Domain Objects (Semantic Layer)

This section defines the **meaning** of the objects and how they map to the schema.
It must not introduce fields that are not present in the SQL contract.

### Workout
A training session. Semantics:
- groups multiple performed sets
- has a session context (e.g. split/tag) and optional notes

SQL mapping:
- see tables in `workout_schema.sql` (Workout/session table + relations)

### ExerciseSet
One performed set of an exercise. Semantics:
- identifies the exercise performed
- records the measured performance for that set (e.g. reps/weight)
- belongs to exactly one Workout

SQL mapping:
- see tables in `workout_schema.sql` (set table + FK to Workout)
