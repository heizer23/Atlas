---
name: project_habittracker_sprint01
description: HabitTracker Sprint01_Core — new app, design review found Dataset-plus-sibling-field serialization gap
metadata:
  type: project
---

HabitTracker Sprint01_Core (03_Application, port 8027) is a new component: daily habit
review/definitions/reporting. Progression: DRAFT_READY → DESIGN_CREATED (designer flagged an
open question about the `period_summary` field on `GET /api/habittracker/reports`) →
DESIGN_REVIEWED_CHANGES_REQUIRED (verdict APPROVED_WITH_CHANGES, 2026-10-01).

**Why:** the reviewer found that returning a `Dataset` plus an additive top-level `period_summary`
sibling field has no specified serialization mechanism. The canonical `platform_contracts.Dataset`
(`02_Platform/packages/platform_contracts/contracts.py`) is a plain pydantic `BaseModel` with only
`meta`/`schema_`/`rows` and no `extra="allow"` — passing `period_summary` as a constructor kwarg
would be silently dropped. This is an R-CON-BP-08 (contract self-containment) / R-CON-BP-04 gap:
the designer correctly flagged the deviation as a risk but didn't resolve the mechanism.

A working precedent already exists: `03_Application/EssayCards/backend/routers/review_stats.py`
uses `response_model=None` + `dataset.model_dump()` + manual `JSONResponse` to add sibling fields
beside a Dataset. The corrector should point the HabitTracker reports endpoint at this pattern.

**How to apply:** when a reviewer approves-with-changes a GET endpoint that returns `Dataset` plus
extra top-level fields, expect the corrector step to adopt the `response_model=None` +
`model_dump()` + `JSONResponse` pattern unless a new mechanism is explicitly justified. Also:
Sprint01_Core's reviewer reused the shorter R-PRO-BP-02 Blocking/Non-Blocking/Approval-Condition
format over its own agent-prompt template, citing the same already-logged conflict as EssayCards
Sprint11 (`00_Blueprint/Quality/agent_rule_conflicts.md`, 2026-09-26 entry) rather than adding a
duplicate conflict-log entry — this is now the second occurrence of that exact conflict.

See [[feedback_skip_specs_stage]] for routing baseline. Next expected step: sprint_design_corrector
→ loop back through sprint_design_reviewer.

**Update (2026-10-01, 13_design_review.md):** second review round after the corrector applied the
`response_model=None` + `model_dump()` + `JSONResponse` dict-merge fix. Verdict again
APPROVED_WITH_CHANGES — the corrector resolved the original gap but, by specifying the mechanism in
code-level detail, exposed a new Critical defect one layer down: `period_summary.period_start`/
`period_end` are raw `datetime.date` objects (needed as SQL bind params in the same step) that get
merged into the response dict *after* `dataset.model_dump(mode="json")` already ran — so they skip
pydantic's serializer entirely and hit Starlette's default `json.dumps`, which throws `TypeError` on
every single call to `GET /reports`. Flagged as R-CON-AL-03 (Invariant Realizability). Fix is narrow:
`.isoformat()` the two fields or run `jsonable_encoder()` over the merged dict before `JSONResponse`.

**Pattern worth remembering:** when a corrector resolves a design review's blocking issue by naming a
previously-abstract mechanism in full code-level detail (not just picking the pattern, but writing out
the actual merge/serialization steps), expect a second review pass to find a new, more concrete defect
in the layer the correction just made explicit — the act of specifying surfaces what was previously
hidden by vagueness. Don't assume a correction that satisfies the prior review's exact wording is
automatically clean; the reviewer should (and did) re-derive invariant realizability from scratch
rather than just checking the named fix was applied literally.

Also: the reviewer's "identical mechanism as EssayCards" claim-check recurred — EssayCards'
`review_stats.py` only demonstrates `response_model=None`/`model_dump`/`JSONResponse`, never the
sibling-field dict-merge itself, so citing it as full precedent overstates what it proves. Same
pattern logged in [[reference_essaycards_dual_scheduler_review]] (Sprint12 "restated function
signatures must be diffed against the one authoritative declaration").

**Update (2026-10-01, 15_design_review.md):** third review round, still APPROVED_WITH_CHANGES. The
corrector's `.isoformat()` fix for `period_start`/`period_end` was verified correct and consistently
applied in all 3 locations (architecture ui_contract Mechanism clause, internal_flow step 11,
scaffolding reports.py entry) — the Critical defect from round 2 is genuinely closed. But the "Pattern
worth remembering" above predicted exactly what happened next: the same audit found a *third* sibling
field, `period_summary.anchor_date`, undergoing the identical str→date transition (for
`resolve_report_period`) that was never given the same `.isoformat()` treatment, plus the str→date
conversion itself was never declared as an explicit internal_flow step at all (R-CON-AL-03 +
R-CON-BP-10). This is a direct recurrence of EVD-2026-10-01-005's own `recurrence_hint` prediction,
materializing inside the correction meant to close it — logged as `EVD-2026-10-01-006` reusing the
`non_pydantic_sibling_field_bypasses_json_serialization` pattern name.

**Escalated lesson:** when a manually-built response dict merges multiple fields that each require a
raw→JSON-safe conversion, a corrector that fixes the one(s) named in the review is not sufficient —
every field in that same dict literal undergoing any type transition needs to be audited together, not
one-at-a-time across successive review rounds. If this shape appears again, consider recommending the
corrector apply `jsonable_encoder()` over the whole merged dict once, rather than enumerating per-field
`.isoformat()` calls — it would have prevented all three rounds in a single fix.

**Update (2026-10-01, 17_design_review.md): verdict APPROVED — design phase closed after 4 review
rounds (11→17) + 3 correction rounds (12, 14, 16).** The fourth reviewer audited all 7
`period_summary` fields individually and confirmed the `anchor_date` fix from `16_design_corrections.md`
closed the gap; the other 4 fields (`period`, `dates`, `confirmed_days`, `elapsed_days`) were never
ambiguous (no parallel differently-typed candidate existed for them), so the recurring pattern was
fully bounded at 3 fields, not open-ended. One non-blocking observation remained on `elapsed_days`
wording (admits a literal crashing reading, but an obvious correct alternative also satisfies the
prose — a *weaker* ambiguity class than the three Hard Rule Violations already resolved, correctly not
escalated). State moved DESIGN_CREATED → DESIGN_APPROVED; next_agent sprint_implement.

Full 4-round review arc also logged by the design reviewer itself in the user's global memory at
`reference_habittracker_sprint01_review.md` (not this sprint_orchestrator memory store) — a reusable
lesson for future reviews of similar `response_model=None` + manual `JSONResponse` sibling-field
designs.

**Update (2026-10-01, implementation + tests): sprint reached TESTS_PASSING, orchestration stopped
per [[feedback_sprint_process_overhead]].** `sprint_implement` built the full component (backend
`review_logic.py` canonical shared module, `habits`/`reviews`/`reports` routers, frontend Daily
Review/Habit Definitions/Reports pages, shell wiring) and self-reported 28/28 tests passing — but
returned no Activity Report block (files_read/files_written logged as `(unreported)` in
`99_sprint_log.md`; worth checking in future HabitTracker sprints whether this agent version
consistently omits it). `sprint_test_runner` independently re-ran the suite twice (not taken on
faith) and confirmed TESTS_PASSING: 28/28 pass, all 30 non-UI `10_test_spec.md` scenarios mapped with
no gaps, 3 `[UI — manual]` scenarios correctly recorded as MANUAL not PASS. One non-blocking gap
noted: `01_System/test/compose.test.yml` has no `habittracker-test` entry (only the component-local
`compose.yml` does) — same class of gap previously seen in [[project_storyreader_sprint01]]. One
implementer deviation logged as `EVD-2026-10-01-007` (fixtures.sql convention conflict for a
starter-seed test needing a genuinely empty `habits` table, resolved with an isolated local
truncate in that one test). Sprint is at TESTS_PASSING, ready for human `/sprint-close`; not yet
closed as of this update.
