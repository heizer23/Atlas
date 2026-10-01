# Design Review — Review Stats — Sprint11_ReviewStats

**Verdict:** APPROVED
**Date:** 2026-09-26
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` §`sprint_note` / `contracts.consumes` | Verified, not a defect: the designer's choice to scope `10_architecture.json`/`10_scaffolding.json` to this sprint's diff only, referencing `essaycards.review_events` purely as a read dependency, and to deliberately not copy forward the stale `00_architecture/architecture.json`/`scaffolding.json` seed baseline, is consistent with the identical, explicitly-documented precedent set by `Sprint09_Nuggets` and `Sprint10_DualSchedulerAB` (`Sprint10_DualSchedulerAB/10_architecture.json` §`sprint_note`: "This sprint's artifacts are therefore NOT copied from that stale seed"). No R-CON-BP-09 (cross-artifact consistency) or R-CON-BP-01 (machine legibility) violation: the sprint-diff artifacts are internally consistent, the read-only dependency on `review_events` is explicitly named with its owning sprint, and `03_Application/EssayCards/CLAUDE.md` remains the up-to-date cumulative source of truth an implementer/auditor would consult for full system context. |
| 2 | `10_architecture.json` §`risks` | The query's outer `WHERE reviewed_at >= now() - interval '30 days'` restriction cannot use an index scan (no index leads with `reviewed_at`); this is already correctly self-identified as a risk with an owner (`open_questions` → `architecture`) rather than hidden — acceptable at current volume, no action required for approval. |
| 3 | `10_architecture.json` §`interfaces.exposed_surfaces` / `backend/routers/experiment.py` (existing) | Confirmed no duplication or modification of `GET /experiment/summary`: the new endpoint's query never reads, filters, or groups on `review_events.scheduler`, and applies no `prior_review_interval` filter — both forbidden actions are explicitly listed in `dependencies.forbidden` and independently verified against the live `experiment.py` file during this review. |

## Approval Condition

None — approved as-is.

---

### Verification notes (supporting detail, non-blocking)

- **R-CON-AL-06 (time authority):** Verified — `00_draft.md` §1 and `10_architecture.json` §`contracts.invariants`/`interfaces.exposed_surfaces.query_behavior.time_basis` both state server-only `now()`, computed fresh per request, with no client-supplied time input anywhere in the feature or its query construction (single SQL statement, no parameters).
- **R-CON-AL-01/02 (query behavior explicitness / scope-mode closure):** Verified — the endpoint accepts no parameters; `query_behavior` in `10_architecture.json` explicitly states defaults, ordering, grouping, boundary construction, empty-result and zero-fill behavior. The single no-parameter case is trivially closed.
- **R-CON-BP-04 (Dataset contract):** Verified — `GET /api/essaycards/review-stats/summary` is a read endpoint returning `Dataset` via the same `_dataset_response`/`ColumnSchema`/`DatasetMeta` pattern as `backend/routers/experiment.py`, imported from `platform_contracts` rather than redefined locally.
- **R-CON-BP-06 (consumer pattern fidelity):** Verified against the live `03_Application/EssayCards/src/shellConfig.ts` — the new nav entry (`order: 5`, immediately after the existing `essaycards-experiment` entry at `order: 4`) uses the exact same `mobilePrimaryNav`/`desktopNav` array + `AppRegistry.register` shape already in use; no new nav mechanism introduced. The new `<Route path="/stats">` addition matches the existing flat `<Routes>` block in `src/ShellEntry.tsx`.
- **R-CON-BP-07 (canonical artifact path):** Verified — `GET /api/essaycards/review-stats/summary` is stated identically across `10_architecture.json` (`contracts.provides`, `interfaces.exposed_surfaces.name`) and `10_test_spec.md`; the frontend's `apiFetch('/essaycards/review-stats/summary')` call is consistent with the existing convention where `apiFetch` implicitly prefixes `/api/essaycards` (confirmed against every other `apiFetch(...)` call site in `src/ShellEntry.tsx`, including `ExperimentDashboardView`'s identical `/essaycards/experiment/summary`). No path divergence found.
- **UI test coverage:** `10_scaffolding.json` lists `src/ShellEntry.tsx` (`.tsx`, changed) in scope; `10_test_spec.md` contains one `[UI]` scenario ("Stats page shows three window cards with grade breakdown") describing observable user-facing behavior. Requirement satisfied.
- **Layer correctness:** Application-layer classification is correctly justified (`10_architecture.json` §`classification.why_application`/`not_platform`) — the window definitions, grade vocabulary, and scheduler-agnostic aggregation are EssayCards-specific interpretations with no reusable/platform capability introduced; no infrastructure leakage into Platform.
- **Persistence consistency:** No `10_schema.sql` present, correctly — `persistence.owns_persistent_state: false` and the design only reads the existing, unmodified `essaycards.review_events` table (schema verified against the live `schema.sql`).
