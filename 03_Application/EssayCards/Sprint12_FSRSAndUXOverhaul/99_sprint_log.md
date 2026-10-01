# Sprint Log — Sprint12_FSRSAndUXOverhaul

```json
{
  "sprint_name": "Sprint12_FSRSAndUXOverhaul",
  "component_name": "EssayCards",
  "layer": "03_Application",
  "log_format": "v2",
  "current_state": "SPRINT_COMPLETE",
  "last_agent": "/sprint-close",
  "next_agent": null,
  "blocking": false,
  "block_reason": null,
  "fix_iterations": 1
}
```

> Note: the `sprint_orchestrator` subagent that launched `sprint_implement` was itself terminated
> mid-run by a session rate limit (HTTP 429) shortly after dispatching that stage — the background
> `sprint_implement` agent it had already spawned continued independently and completed normally
> (per its own Activity Report). Since `sprint_orchestrator` is the sole owner of this file
> (R-PRO-BP-01 §7) and did not survive to record that completion, the top-level session resumed
> orchestration duty for the remainder of this sprint — same precedent as `Sprint09_Nuggets`/
> `Sprint10_DualSchedulerAB`'s manually-coordinated runs. The `IMPLEMENTATION_IN_PROGRESS` entry
> below is transcribed from `sprint_implement`'s own Activity Report (read/write lists, agent_version,
> duration) and independently spot-verified (full backend suite re-run: 266/266 pass; all 7 new/changed
> Playwright specs re-run: 7/7 pass; container logs checked for clean startup) before being recorded.

> Note: `00_draft.md`'s "Note" section and the mission instructions explicitly request following the
> `Sprint10_DualSchedulerAB` precedent: non-canonical Phase A parallel investigation before design, and
> a non-canonical Phase D independent implementation review after `TESTS_PASSING`. Neither step is a
> canonical R-PRO-BP-01 state transition. Phase A investigation findings live in the session scratchpad
> (`/tmp/.../scratchpad/sprint12_phaseA_investigation.md`), not as a sprint-folder artifact, and were
> passed to `sprint_design_application` as required reading — identical convention to Sprint10. Phase D
> (if reached) will be filed to `00_Blueprint/Quality/EssayCards/Sprint12_FSRSAndUXOverhaul_Implementation_Review.md`,
> additive due diligence that does not gate `TESTS_PASSING`, same as Sprint10.

## Log

(Phase A investigation — four parallel read-only agents — completed before the first canonical
transition below; not logged as a state transition per R-PRO-BP-01 §11/Sprint10 precedent, since it
produces no sprint-folder artifact and does not change `current_state`.)

- 2026-10-01T00:00:00Z `DRAFT_READY` → `DESIGN_CREATED` [sprint_design_application@2026-04-11] 880s
  read: Sprint12_FSRSAndUXOverhaul/00_draft.md, scratchpad/sprint12_phaseA_investigation.md, Sprint10_DualSchedulerAB/10_architecture.json, 10_scaffolding.json, 10_schema.sql, 10_test_spec.md, schema.sql, backend/scheduling.py, backend/routers/flashcards.py, backend/routers/experiment.py, backend/routers/essays.py, backend/routers/examinations.py, backend/routers/review_stats.py, backend/examinations.py, backend/main.py, backend/ingest.py, backend/exploration.py, src/ShellEntry.tsx, src/shellConfig.ts, 02_Platform/Atlas_Shell/src/types.ts, platform-ui/components/BarChart.tsx, Sidebar.tsx, BottomNav.tsx, MoreMenu.tsx, pyproject.toml, CLAUDE.md
  wrote: Sprint12_FSRSAndUXOverhaul/10_architecture.json, 10_scaffolding.json, 10_schema.sql, 10_test_spec.md
- 2026-10-01T00:00:00Z `DESIGN_CREATED` → `DESIGN_REVIEWED_CHANGES_REQUIRED` [sprint_design_reviewer@2026-04-11] 450s — APPROVED_WITH_CHANGES: (1) estimate_initial_fsrs_state signature inconsistent (2-arg vs 3-arg) across architecture.json/scaffolding.json [Hard Rule Violation, R-CON-BP-09/10]; (2) Phase A button/nav inventory only in session-scoped /tmp scratchpad, not a sprint-folder artifact [Major]; (3) stats page plan reuses ReviewStatsPanel props that don't exist on the scope-free stats page, no refactor scaffolded [Major]
  read: Sprint12_FSRSAndUXOverhaul/00_draft.md, 10_architecture.json, 10_scaffolding.json, 10_schema.sql, 10_test_spec.md, 99_sprint_log.md, CLAUDE.md, .claude/rules/R-CON-PL.md, R-CON-AL.md, R-OPS-BP.md, R-CON-BP.md, R-PRO-BP.md, 00_Blueprint/Quality/agent_rule_evidence.md, schema.sql, Atlas_Shell/src/types.ts, shellConfig.ts, BottomNav.tsx, platform_contracts/contracts.py, backend/routers/essays.py, backend/main.py, backend/routers/flashcards.py, backend/scheduling.py, src/ShellEntry.tsx, scratchpad/sprint12_phaseA_investigation.md, Sprint10_DualSchedulerAB/11_design_review.md
  wrote: Sprint12_FSRSAndUXOverhaul/11_design_review.md, 00_Blueprint/Quality/agent_rule_evidence.md
- 2026-10-01T00:00:00Z `DESIGN_REVIEWED_CHANGES_REQUIRED` → `DESIGN_CREATED` [sprint_design_corrector@2026-04-11] 273s — fixed estimate_initial_fsrs_state signature to consistent 3-arg form across architecture.json; added self-contained button_nav_inventory block to architecture.json replacing the unreachable scratchpad reference; scaffolded new props-decoupled ForecastGrid component extracted from ReviewStatsPanel, used by both ReviewStatsPanel and the new ReviewStatsView
  read: Sprint12_FSRSAndUXOverhaul/11_design_review.md, 00_draft.md, 10_architecture.json, 10_scaffolding.json, 10_schema.sql, src/ShellEntry.tsx, src/shellConfig.ts
  wrote: Sprint12_FSRSAndUXOverhaul/10_architecture.json, 10_scaffolding.json, 12_design_corrections.md
- 2026-10-01T00:00:00Z `DESIGN_CREATED` → `DESIGN_APPROVED` [sprint_design_reviewer@2026-04-11] 149s — APPROVED; all three prior issues verified genuinely fixed against live code (signature consistency, self-contained button_nav_inventory block, ForecastGrid extraction mechanically achievable); no Major/Critical regressions; two pre-existing Open Uncertainties carried forward non-blocking
  read: Sprint12_FSRSAndUXOverhaul/00_draft.md, 10_architecture.json, 10_scaffolding.json, 10_schema.sql, 10_test_spec.md, 11_design_review.md, 12_design_corrections.md, src/shellConfig.ts, src/ShellEntry.tsx
  wrote: Sprint12_FSRSAndUXOverhaul/13_design_review.md
- 2026-10-01T11:15:00Z `DESIGN_APPROVED` → `IMPLEMENTATION_IN_PROGRESS` [sprint_implement@2026-04-11] 2951s — FSRS made sole scheduler (ClassicScheduler/compute_next_due_at/decide_scheduler_assignment removed; DESIRED_RETENTION + estimate_initial_fsrs_state added, reading FACTOR/DECAY off the live fsrs.Scheduler instance rather than hardcoding v4-era constants, per design's "confirm against installed source" instruction); new backend/migrate_fsrs_state.py backfill wired into main.py startup; schema.sql folds in backup table, scheduler-column drops, exam_type column; fixed a rerun-safety bug found during testing (dead Sprint10 ADD COLUMN/backfill statements that would re-add/re-drop columns and hard-fail on review_events every restart); learning-progress subquery shared by essay list/detail; exam_type threaded through examinations; new /review-stats/activity + /review-stats/intervals endpoints; experiment.py + test_experiment.py deleted only after full suite green; frontend ActionMenu/LearningLevelBadge/category-collapse/ForecastGrid extraction/reworked ReviewStatsView/regrouped nav. 266 backend tests + 7 Playwright UI tests pass; both containers rebuilt/redeployed; live migration confirmed clean (147 cards backfilled, 0 skipped, idempotent on restart).
  read: Sprint12_FSRSAndUXOverhaul/00_draft.md, 10_architecture.json, 10_scaffolding.json, 10_schema.sql, 10_test_spec.md, 11_design_review.md, 12_design_corrections.md, 13_design_review.md, 99_sprint_log.md, backend/scheduling.py, backend/routers/flashcards.py, backend/routers/experiment.py, backend/routers/essays.py, backend/routers/examinations.py, backend/routers/review_stats.py, backend/examinations.py, backend/main.py, backend/ingest.py, backend/exploration.py, backend/database.py, schema.sql, src/ShellEntry.tsx, src/shellConfig.ts, pyproject.toml, tests/fixtures.sql, tests/conftest.py, tests/test_scheduling.py, tests/test_flashcards.py, tests/test_migration.py, tests/test_ingest.py, tests/test_exploration.py, tests/test_essays.py, tests/test_examinations.py, tests/test_review_stats.py, tests/ui/review_stats.spec.ts, CLAUDE.md, 02_Platform/Atlas_Shell/platform-ui/components/BarChart.tsx, LineChart.tsx, platform-ui/api/types.ts, Atlas_Shell/src/types.ts, navigation/MoreMenu.tsx, vite.config.ts, tsconfig.json, Dockerfile, compose.yml, Dockerfile, 01_System/test/compose.test.yml, 01_System/config.env
  wrote: backend/scheduling.py, backend/migrate_fsrs_state.py, backend/main.py, backend/routers/flashcards.py, backend/ingest.py, backend/exploration.py, backend/examinations.py, backend/routers/examinations.py, backend/routers/essays.py, backend/routers/review_stats.py, schema.sql, CLAUDE.md, src/ShellEntry.tsx, src/shellConfig.ts, tests/fixtures.sql, tests/test_scheduling.py, tests/test_migration.py, tests/test_flashcards.py, tests/test_ingest.py, tests/test_exploration.py, tests/test_essays.py, tests/test_examinations.py, tests/test_review_stats.py, tests/ui/review_stats.spec.ts, tests/ui/category_collapse.spec.ts, tests/ui/essay_action_menu.spec.ts, tests/ui/learning_level_badge.spec.ts (deleted backend/routers/experiment.py, tests/test_experiment.py)
- 2026-10-01T12:08:00Z `IMPLEMENTATION_IN_PROGRESS` → `TESTS_FAILED_FIXABLE` [sprint_test_runner@2026-04-15] 209s — 28 scenarios mapped; 26/28 PASS (266/266 backend pytest, 7/7 Playwright), 2 MISSING COVERAGE (not behavioral failures — runtime manually confirmed correct in both cases): (1) no test asserts `GET /experiment/summary` now 404s after its router deletion; (2) no automated test walks the full `§button_nav_inventory` to confirm every pre-existing action survived consolidation (source-inspected as present, but unverified by a test). Classified FIXABLE per default (no design artifact is wrong). Next: sprint_implement adds the two missing tests, re-run test stage.
  read: Sprint12_FSRSAndUXOverhaul/10_test_spec.md, 10_scaffolding.json, 99_sprint_log.md, compose.yml, 01_System/test/compose.test.yml, tests/test_shell_proxy.py, tests/ui/essay_action_menu.spec.ts, tests/ui/category_collapse.spec.ts, tests/ui/learning_level_badge.spec.ts, src/ShellEntry.tsx, tests/test_flashcards.py, tests/test_migration.py, tests/test_essays.py, tests/test_examinations.py, tests/test_review_stats.py, tests/test_ingest.py, 10_architecture.json
  wrote: Sprint12_FSRSAndUXOverhaul/50_test_report.md
- 2026-10-01T12:16:00Z `TESTS_FAILED_FIXABLE` → `IMPLEMENTATION_IN_PROGRESS` [sprint_implement@2026-04-11] 302s — fix_iterations 0→1. Added `test_experiment_summary_route_is_fully_removed` (tests/test_migration.py, asserts 404) and new Playwright spec tests/ui/button_nav_inventory.spec.ts walking the full §button_nav_inventory (overview page actions, essay-header ActionMenu primary/secondary items incl. guided/unguided exam and conditional +New nugget, section-end ActionMenu, desktop nav regrouping). Test-coverage-only iteration, no scheduling/migration/UI behavior touched. 267/267 backend tests pass (266+1), 11/11 Playwright pass (7+4).
  read: Sprint12_FSRSAndUXOverhaul/50_test_report.md, 99_sprint_log.md, 10_test_spec.md, 10_architecture.json, tests/test_shell_proxy.py, tests/ui/essay_action_menu.spec.ts, tests/ui/category_collapse.spec.ts, tests/ui/learning_level_badge.spec.ts, tests/fixtures.sql, tests/conftest.py, tests/test_migration.py, src/ShellEntry.tsx, src/shellConfig.ts, CLAUDE.md, 02_Platform/Atlas_Shell/playwright.config.ts, navigation/MoreMenu.tsx, navigation/BottomNav.tsx, navigation/Sidebar.tsx, shell/ShellLayout.tsx, 01_System/test/compose.test.yml, 01_System/config.env, 01_System/secrets.env
  wrote: tests/test_migration.py, tests/ui/button_nav_inventory.spec.ts
- 2026-10-01T12:22:00Z `IMPLEMENTATION_IN_PROGRESS` → `TESTS_PASSING` [sprint_test_runner@2026-04-15] 127s — fix iteration 1 re-run: 28 scenarios, 28/28 PASS, 0 FAIL, 0 MISSING. 267/267 backend pytest, 11/11 Playwright. Recommended next: /sprint-close.
  read: Sprint12_FSRSAndUXOverhaul/10_test_spec.md, 50_test_report.md, 10_architecture.json, 99_sprint_log.md, compose.yml, 01_System/test/compose.test.yml, tests/test_migration.py
  wrote: Sprint12_FSRSAndUXOverhaul/50_test_report.md
- 2026-10-01 `TESTS_PASSING` → `SPRINT_COMPLETE` [/sprint-close]
