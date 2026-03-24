# FoodTracker Sprint Conventions

This file declares approved deviations from the canonical Atlas sprint process (R-PRO-BP-01).
The sprint orchestrator must read this file before applying canonical stage requirements to FoodTracker sprints.

---

## 1. Skipped stage: `10_specs/` and `reviewer-specs-readiness`

**Overrides:** R-PRO-BP-01 §2 (`DRAFT_READY → SPECS_READY` transition), §3 (allowed state transitions from `DRAFT_READY`), §4 (required artifacts for `SPECS_READY`).

**Deviation:** The `10_specs/` folder and `design_specs.md` artifact are not produced for FoodTracker sprints. The `reviewer-specs-readiness` agent is not invoked. The sprint transitions directly from `DRAFT_READY` to `DESIGN_CREATED`.

**How the orchestrator must route:** After confirming `00_input/draft.md` exists, route directly to the application designer (`designer-application`). Do not require `10_specs/design_specs.md` as a blocking artifact.

**Rationale:** FoodTracker has an established domain context and stable sprint patterns. The spec-readiness stage was introduced after several FoodTracker sprints were already underway. The designer reads `00_input/draft.md` directly and produces design artifacts without a separate spec document. This has been validated across multiple successful sprints.

---

## 2. Scope of this deviation

This deviation applies to all FoodTracker sprints, including sprints initiated before and after 2026-03-24. Sprint folders produced before the R-PRO-BP-01 prospective date are not violations; this file governs future sprints by declaring the permanent approved deviation for this application.
