# Design Review — Calendar

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-05-07
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_architecture.json §dependencies.external_required` / `10_scaffolding.json §files[backend/db.py]` | Pattern consistency (established Atlas convention) | Replace `asyncpg` with `psycopg2`. Every other application in `03_Application` uses `psycopg2` with `RealDictCursor`. Introducing `asyncpg` (async Postgres driver) for this component creates a dependency inconsistency with no justification in the definition. The CLAUDE.md for StorageTracker explicitly requires following TaskTracker patterns; the same expectation applies to new apps. |
| 2 | `10_scaffolding.json §files` | R-CON-BP-07 (Canonical Artifact Path) | Add `schema.sql` to the scaffold as a root-level file (`03_Application/Calendar/schema.sql`). All other Atlas applications (TaskTracker, StorageTracker, FoodTracker) have a `schema.sql` loaded idempotently at startup. The sprint artifact `10_schema.sql` is the source; the implementer must also produce the runtime `schema.sql` at the component root. Without this entry, the implementer has no scaffold signal for the runtime schema loading pattern. |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json §interfaces.exposed_surfaces` | The exposed_surfaces array embeds non-schema fields (`params`, `default_behavior`, `body`, `patch_semantics`) inline. These are useful for the implementer but are not part of the standard `exposed_surfaces` schema. This does not block implementation — the extra fields are additive — but reviewers in future sprints may flag them. |
| 2 | `10_architecture.json §open_questions` | Both open questions include an inline `resolution` field that pre-resolves the question. Resolving open questions inline is fine for implementation clarity; however it means the questions should arguably be removed from `open_questions` and promoted to explicit design decisions. Minor documentation inconsistency — not blocking. |
| 3 | `10_architecture.json §contracts` | R-CON-AL-06 (Time Authority): The design does not explicitly declare the time authority for `start_at` / `end_at`. Given these are user-supplied datetimes the client is the time source — this should be stated to complete the contract. |

## Approval Condition

Update `asyncpg` to `psycopg2` throughout architecture.json and scaffolding.json, and add `03_Application/Calendar/schema.sql` as a scaffold entry.
