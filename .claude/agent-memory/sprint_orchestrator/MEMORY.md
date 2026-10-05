# Sprint Orchestrator — Memory Index

## Project
- [Notifications Sprint1 Pattern](project_notifications_sprint1.md) — First Platform-layer Notifications sprint; two-agent (Atlas Claude / Android Claude) delivery split via FCM payload boundary
- [CalendarConnector Sprint02 Pattern](project_calendar_connector_sprint2.md) — OAuth scope upgrade sprint; AWAITING_HUMAN_REVIEW; two operator deployment actions required before end-to-end testing
- [CalendarConnector Sprint03 Pattern](project_calendar_connector_sprint3.md) — Event lifecycle sprint (create/update/delete + Postgres event index); DRAFT_READY; three open questions unresolved in draft
- [TaskTracker Sprint02 Pattern](project_tasktracker_sprint02.md) — Effort field + mobile row + editable detail; DESIGN_APPROVED; human gate required before sprint_implement
- [LinkingEngine Sprint01 Pattern](project_linking_engine_sprint01.md) — Generic object-linking Platform service; AWAITING_HUMAN_REVIEW; pre-existing app code reconciled with design artifacts

- [LabelEngine Sprint01 Pattern](project_labelengine_sprint01.md) — Minimal label/object many-to-many; AWAITING_HUMAN_REVIEW; human gate required before sprint_implement_reviewer; design gap (AttachLabelRequest.object_type) resolved by implementer
- [LabelEngine Sprint02 Pattern](project_labelengine_sprint02.md) — Batch read endpoint (POST /api/objects/labels/batch); AWAITING_HUMAN_REVIEW; route ordering risk mitigated; fixes F-001 TaskTracker boundary violation
- [LabelEngine Sprint02_ReverseLookup Pattern](project_labelengine_sprint02_reverselookup.md) — GET /api/labels/used surgical addition; IMPLEMENTATION_IN_PROGRESS; one review cycle; ORDER BY lower() fix
- [NumericSeries Sprint01 Pattern](project_numericseries_sprint01.md) — Time-series measurement tracker; recharts sparkline; AWAITING_HUMAN_REVIEW; open question resolved as 404 on unknown label external write
- [NumericSeries Sprint02 Pattern](project_numericseries_sprint02.md) — Chronos by-name write + UX polish; SPRINT_COMPLETE (tests passed)
- [NumericSeries Sprint03 Pattern](project_numericseries_sprint03.md) — Catalog + batch ingestion + SVG sparkline + Chronos skill; IMPLEMENTATION_IN_PROGRESS; test-runner blocked on Bash; container rebuild required
- [StorageTracker Sprint01 Pattern](project_storagetracker_sprint01.md) — Household item tracker; SPRINT_COMPLETE; full automated loop; port 8022 (8020 taken by Notifications); tests written but run inside Docker
- [FoodTracker Sprint06 Pattern](project_foodtracker_sprint06.md) — Search/scale/averages; IMPLEMENTATION_IN_PROGRESS; food-tracker-test container newly added, needs build before test run; schema.sql backfilled with Sprint04 columns
- [FoodTracker Sprint07 Pattern](project_foodtracker_sprint07.md) — quantity_g→base_quantity rename; IMPLEMENTATION_IN_PROGRESS; container rebuild + migration 006 required before test run
- [TaskTracker Sprint09 Pattern](project_tasktracker_sprint09.md) — Scheduled status + tab; IMPLEMENTATION_IN_PROGRESS; container rebuild + migration 009 required before test run; tests self-sufficient (no fixtures.sql)
- [WorkoutTracker Sprint01 Pattern](project_workouttracker_sprint01.md) — Frontend-only UX fixes (dropdown overflow, RepChip, chart date fix); IMPLEMENTATION_IN_PROGRESS; shell rebuild required; all tests manual
- [Calendar Sprint01 Pattern](project_calendar_sprint01.md) — Atlas-owned timeblocking calendar (NOT CalendarConnector); IMPLEMENTATION_IN_PROGRESS; container build required; FullCalendar added to Shell; port 8023
- [EssayCards Sprint01 Pattern](project_essaycards_sprint01.md) — New app: essay reader + SRS flashcards; DESIGN_APPROVED, stopped by request before implementation; port 8024; recurring ApiError-bypass gap found in Pydantic body-model mutation endpoints (fixed by dropping Pydantic body model, no prior working precedent in repo)
- [EssayCards Sprint02 Pattern](project_essaycards_sprint02.md) — JSON ingest endpoint + shared upsert refactor; TESTS_PASSING; fully unattended single-pass loop (0 correction/fix loops); designer caught scope item already built in prior sprint's live code
- [StoryReader Sprint01 Pattern](project_storyreader_sprint01.md) — New app: mobile markdown reader + tap-to-save reactions; TESTS_PASSING; one correction cycle (missing main.tsx import + missing Dataset `id` field); placeholder-rename correctly deferred (no file-move tool); central `01_System/test/compose.test.yml` missing this component's `-test` entry (non-blocking, needs human fix); port 8026
- [EssayCards Sprint11 Pattern](project_essaycards_sprint11.md) — Review-stats read-only endpoint + UI; TESTS_PASSING, zero corrections/fix loops; confirms not-copying-forward-stale-00_architecture-baseline is legitimate (precedent: Sprint09/Sprint10); pre-existing test_examinations.py date flake reconfirmed, non-blocking
- [HabitTracker Sprint01 Pattern](project_habittracker_sprint01.md) — New app: daily habit review/definitions/reporting; DESIGN_REVIEWED_CHANGES_REQUIRED; port 8027; Dataset+sibling-field (period_summary) serialization gap (R-CON-BP-08), EssayCards review_stats.py precedent cited; 2nd occurrence of reviewer-template-vs-R-PRO-BP-02 conflict
- [EssayCards Sprint13 Pattern](project_essaycards_sprint13.md) — Review/Stats rework + sentence feedback; DESIGN_APPROVED, stopped there (multi-area + new schema + reshaped endpoint = deliberate human checkpoint, not auto-chain to implement); 1 correction cycle (reviewedCount dual-purpose-variable gap, sentence-tap-vs-nested-link-click-precedence gap); StoryReader interaction-pattern-reuse done correctly (not blind data-model copy); platform-ui BarChart per-bar-label gap surfaced as open_question not silently patched

## Feedback
- [Skip specs reviewer stage](feedback_skip_specs_stage.md) — DRAFT_READY routes directly to designer; sprint_specs_reviewer is never used

## Reference
