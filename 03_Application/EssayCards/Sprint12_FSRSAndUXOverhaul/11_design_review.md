# Design Review — EssayCards FSRS-Only Scheduling & UX Overhaul (Sprint12_FSRSAndUXOverhaul)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design's hardest constraints are satisfied with high confidence: the due-queue WHERE/ORDER BY is verified byte-for-byte unchanged (confirmed against `backend/routers/flashcards.py`'s live SQL), the Classic→FSRS migration never writes `next_due_at`/`review_interval`/`last_reviewed_at`, backs up scheduler-assignment data before destroying it inside the same transaction, and names its FSRS-state synthesis as an explicit approximation rather than a reconstruction (R-OPS-BP-01). The 0–4 learning-level milestones are closure-complete per R-CON-AL-02/03, including the zero-card non-vacuity requirement. Three issues must be fixed before implementation: a self-contradictory function signature for the legacy-migration helper (repeated four times across the two artifacts), a stats-page reuse plan that is not achievable against `ReviewStatsPanel`'s actual prop contract, and a completeness claim (the button/nav inventory) that depends on content with no durable sprint-folder home. `10_test_spec.md` correctly includes three `[UI]`-labeled scenarios, satisfying the UI test coverage requirement for the `.tsx` files in `10_scaffolding.json`.

## Confirmed Problems

1. **Phase A button/nav inventory has no durable artifact, but deferred verification depends on it**
   - Severity: Major
   - Location: `10_architecture.json §deferrals.reviewer` ("Confirm every button/action in the Phase A investigation A4 inventory is reachable somewhere post-consolidation"); `99_sprint_log.md`'s process note ("Phase A investigation findings live in the session scratchpad ... not as a sprint-folder artifact")
   - Why it is a problem: `10_architecture.json` repeatedly cites "the Phase A investigation A4 inventory" as the completeness baseline for button consolidation (contracts.invariants, deferrals.reviewer), but that inventory exists only as a file in one Claude session's `/tmp` scratchpad — explicitly *not* written to the sprint folder, per the sprint log's own note. R-CON-BP-01 requires that "later agents must be able to inspect, reason about, and extend the system from explicit artifacts alone." A reviewer, implementer, or test-writer working from a fresh session (the normal case — scratchpad directories are session-scoped) has no way to open or verify against this document at all.
   - Impact: The `deferrals.reviewer` instruction to "confirm every button/action ... is reachable" is unexecutable by any agent that does not happen to share this exact session's scratchpad. In this review, the content happened to be independently readable and was cross-checked against `internal_flow` steps 9–11 and `10_scaffolding.json`'s `ShellEntry.tsx` entry — the mapping is in fact complete (every A4 action is accounted for) — but that confirmation was incidental, not something the design made possible by its own artifacts.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the sprint adopted Sprint10's "non-canonical scratchpad-only Phase A investigation" precedent (itself not flagged in `Sprint10_DualSchedulerAB/11_design_review.md`) without recognizing that a *deferred reviewer instruction* pointing at that content turns an informal research step into a load-bearing, unverifiable contract.

2. **Stats-page "Scheduled reviews (forecast)" reuse plan does not match `ReviewStatsPanel`'s actual contract**
   - Severity: Major
   - Location: `10_architecture.json §internal_flow` step 13 (`stats_page_rework`: "reuses ReviewStatsPanel's existing FORECAST_COLUMNS rendering against system-wide GET /flashcards/stats"); `10_scaffolding.json`'s `ShellEntry.tsx` entry (`ReviewStatsView` description, same claim; `ReviewStatsPanel`/`FORECAST_COLUMNS` absent from the file's `private_objects` diff)
   - Why it is a problem: `ReviewStatsPanel` (`src/ShellEntry.tsx:2285-2328`) is not a standalone forecast renderer — its props are `topic`, `essayId`, `sectionId`, `refreshToken`, `reviewed`, `backlog`, `newRemaining`, `sessionForecast`, and it renders both the session-scoped "Current" zone (session review/backlog/new counts) and the "Upcoming" forecast zone together from those props. None of `reviewed`/`backlog`/`newRemaining`/`sessionForecast` has any meaningful value on the standalone stats page (`ReviewStatsView`), which has no active review session. The scaffold does not list `ReviewStatsPanel` or `FORECAST_COLUMNS` as `[CHANGED]`, so no extraction/refactor that would make reuse possible is actually scoped.
   - Impact: An implementer following the scaffold literally would have to either (a) invent fake session-state values to satisfy `ReviewStatsPanel`'s props, rendering a misleading "Session: 0" metric on a page with no session, or (b) silently duplicate the `FORECAST_COLUMNS` rendering logic — the opposite of the stated "reuse" intent and undiscoverable from the artifacts as written.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the design asserted component reuse by name without checking the target component's actual prop contract against the new call site's available data.

## Recommended Improvements

1. **Persist the Phase A A4 inventory (or its essential content) as a sprint-folder artifact**
   - Location: `03_Application/EssayCards/Sprint12_FSRSAndUXOverhaul/` (no such file currently exists)
   - Improvement: Fold the button/nav inventory table into `10_architecture.json` itself (e.g., as a `contracts.invariants` entry or an explicit `button_inventory` block) or write it as a named sprint-folder file, so `deferrals.reviewer`'s verification instruction is executable from the canonical artifact set alone.
   - Why: R-CON-BP-01 requires architecture to be legible to later agents from explicit artifacts, not from an incidentally-shared `/tmp` scratchpad.

2. **Scope the forecast-zone reuse to what `ReviewStatsPanel` can actually provide, or extract a shared sub-component**
   - Location: `10_architecture.json §internal_flow` step 13; `10_scaffolding.json`'s `ShellEntry.tsx` entry
   - Improvement: Either (a) extract `FORECAST_COLUMNS`' rendering into a props-decoupled component (taking only `stats: Record<string, number> | null`) that both `ReviewStatsPanel` and the new `ReviewStatsView` zone import, with the extraction explicitly scaffolded, or (b) have `ReviewStatsView` fetch `GET /flashcards/stats` and render the six-bucket forecast with new, purpose-built markup instead of claiming reuse of `ReviewStatsPanel`.
   - Why: Makes the "no new npm dependency, reuse existing rendering" intent actually achievable without inventing session state that doesn't exist on the stats page.

## Scaffold-Only Observations

1. **New `ESSAY_OVERVIEW_SCHEMA` fields lack declared `ColumnSchema` types**
   - Location: `10_scaffolding.json` — `backend/routers/essays.py` entry, `ESSAY_OVERVIEW_SCHEMA` purpose text
   - Observation: The four `milestone_*` booleans, `learning_level`, the two `*_count` integers, and the two `*_passed_at` dates are named but not typed (the existing schema entries for `oral_score`/`oral_date` being removed do specify `type="number"`/`type="date"`). `platform_contracts.ColumnType` is an open string, so any type name is technically legal, but omitting it leaves the boolean-vs-number-vs-date choice to the implementer's inference.
   - Impact on implementation: Low risk — types are inferable from field names — but worth stating explicitly for consistency with every other `ColumnSchema` entry in this file.

## Hard Rule Violations

1. **Cross-Artifact Truth Consistency / Input Sufficiency — `estimate_initial_fsrs_state`'s declared signature omits a required input**
   - Rule Source: `.claude/rules/R-CON-BP.md` (R-CON-BP-09 Cross-Artifact Truth Consistency, R-CON-BP-10 Input Sufficiency)
   - Location: `10_architecture.json §contracts.invariants` (legacy-migration-approximation entry: `"estimate_initial_fsrs_state(review_interval, desired_retention)"`), repeated in `§deferrals.application_implementer`, and in `10_scaffolding.json`'s `migrate_fsrs_state.py` file role (`"estimate_initial_fsrs_state(review_interval, DESIRED_RETENTION)"`) — versus `10_scaffolding.json`'s `backend/scheduling.py` `public_objects` entry for the same function, whose `args` are `["review_interval: timedelta", "last_reviewed_at: datetime", "desired_retention: float = DESIRED_RETENTION"]`
   - Violation: Three separate locations (two in `10_architecture.json`, one more in `10_scaffolding.json`'s own `migrate_fsrs_state.py` description) describe `estimate_initial_fsrs_state` as a two-argument function `(review_interval, desired_retention)`, yet the same invariant text requires the function to produce field `(e) last_review_at — the card's existing last_reviewed_at, used as-is, never recomputed` — an input the two-argument signature never receives. Only the fourth location (the function's own `public_objects` entry) declares the correct three-argument signature. This is both an internal self-contradiction within `10_architecture.json` (R-CON-BP-10: "every helper ... must receive all inputs required to perform its declared behavior ... that dependency must be explicitly declared via function signature") and a cross-artifact inconsistency against `10_scaffolding.json`'s own correct declaration (R-CON-BP-09).
   - Required Fix: Correct all three two-argument occurrences (`10_architecture.json §contracts.invariants`, `§deferrals.application_implementer`, and `10_scaffolding.json`'s `migrate_fsrs_state.py` role text) to the three-argument form `estimate_initial_fsrs_state(review_interval, last_reviewed_at, desired_retention)`, matching the already-correct `backend/scheduling.py` `public_objects` entry.

## Open Uncertainties

1. **Exact placement of `migrate_legacy_fsrs_state()` inside `backend/main.py`'s startup retry loop**
   - Location: `10_architecture.json §deferrals.application_implementer` ("wire it into backend/main.py's startup sequence immediately after init_schema() succeeds"); actual `backend/main.py:40-54`'s `on_startup()`, whose `try` block calls `init_schema()` and then `return`s immediately on success inside a 10-attempt/3s retry loop
   - Uncertainty: "Immediately after `init_schema()` succeeds" is consistent with inserting the call inside the existing `try` block before the `return` (so a migration failure is retried through the same loop as a DB-not-ready failure) — but the design does not state this explicitly, and the literal existing code returns right after `init_schema()`, so a careless edit could place the call after the function's `return` (dead code) or outside the retry loop entirely (no retry on failure).
   - Why it matters: Wrong placement either silently skips the migration call or removes its retry safety net, with no test in `10_test_spec.md` that would catch a startup-ordering mistake (only the migration's own idempotency/correctness is tested, not its wiring into the FastAPI lifecycle).
   - Suggested owner: Implementer

2. **`review_datetime` input to the difficulty-bootstrap `review_card()` call in `estimate_initial_fsrs_state`**
   - Location: `10_architecture.json §contracts.invariants`, legacy-migration-approximation entry (b): "obtained by running the module-level FSRS Scheduler's own `review_card` ONCE on a fresh `fsrs.Card()` with a neutral `Rating.Good`"
   - Uncertainty: `FSRSScheduler.review`'s existing call site passes `review_datetime=now_utc` (the real review time) to `_FSRS_SCHEDULER.review_card`. The design does not state what datetime value this one-time bootstrap call should pass — the migration's current wall-clock time, or the card's `last_reviewed_at` — and whether that choice affects the synthesized difficulty value.
   - Why it matters: An unspecified but library-sensitive input could make the synthesized difficulty non-deterministic or inconsistent across a reran/partial migration, undermining the "safe to rerun" invariant's implicit assumption that recomputation (where it still occurs) is stable.
   - Suggested owner: Implementer

## Minimal Change Set
1. Correct `estimate_initial_fsrs_state`'s declared signature to the three-argument form `(review_interval, last_reviewed_at, desired_retention)` everywhere it appears in `10_architecture.json` (`§contracts.invariants`, `§deferrals.application_implementer`) and in `10_scaffolding.json`'s `migrate_fsrs_state.py` role text, matching the already-correct `backend/scheduling.py` `public_objects` entry.
2. Persist the Phase A A4 button/nav inventory's content into a canonical sprint-folder artifact (folded into `10_architecture.json` or a dedicated file) so `§deferrals.reviewer`'s completeness-verification instruction is executable by an agent with no access to the originating session's scratchpad.
3. Revise `10_architecture.json §internal_flow` step 13 and `10_scaffolding.json`'s `ReviewStatsView` entry so the "Scheduled reviews (forecast)" zone's reuse plan is achievable against `ReviewStatsPanel`'s actual prop contract — either scaffold a props-decoupled forecast sub-component shared by both views, or drop the "reuse" framing and scaffold new markup for that zone.

## Approval Condition
- All three Minimal Change Set items are applied: the `estimate_initial_fsrs_state` signature is consistent across every occurrence in `10_architecture.json` and `10_scaffolding.json`, the Phase A button/nav inventory is backed by a canonical sprint-folder artifact, and the stats-page forecast-zone reuse plan is revised to match `ReviewStatsPanel`'s real prop contract (or replaced with a correctly-scaffolded alternative).
