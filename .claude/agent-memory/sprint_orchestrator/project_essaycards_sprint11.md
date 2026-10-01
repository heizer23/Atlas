---
name: project_essaycards_sprint11
description: EssayCards Sprint11_ReviewStats — read-only review-performance stats endpoint/UI; full pipeline, zero corrections, TESTS_PASSING
metadata:
  type: project
---

Sprint11_ReviewStats (EssayCards, 03_Application): new read-only
`GET /api/essaycards/review-stats/summary` (day/7d/30d rolling windows off
server `now()`, scheduler-agnostic aggregation of the existing Sprint10
`review_events` table) plus `ReviewStatsView` at `/essaycards/stats`. Full
R-PRO-BP-01 pipeline requested explicitly (no fast path) — draft already
pre-resolved the three judgment calls (window semantics, null-vs-zero
recall_rate, scheduler-agnostic scope) by citing existing in-app precedent, so
the whole run was a single clean pass: DRAFT_READY → DESIGN_CREATED (design
reviewer verdict APPROVED, zero blocking issues) → DESIGN_APPROVED →
IMPLEMENTATION_IN_PROGRESS → TESTS_PASSING. No corrector cycle, no fix loop.

**Pattern worth reusing:** designer deliberately did NOT copy forward the
stale `00_architecture/architecture.json`/`scaffolding.json` seed baseline
(now 5+ sprints out of date, still FSRS/Sprint10-scoped) into this sprint's
`10_architecture.json`/`10_scaffolding.json` — scoped the new artifacts to
only this sprint's diff, referencing the read-only dependency table by name
only. Reviewer explicitly confirmed this is legitimate and consistent with
Sprint09_Nuggets and Sprint10_DualSchedulerAB doing the same thing for the
same reason, not an R-CON-BP-09/R-CON-BP-01 violation — an orchestrator
should not flag "didn't touch 00_architecture baseline" as a defect on its
own for this component.

**Fixture care:** implementer attached new `review_events` fixture rows to
*existing* established test cards rather than inserting new flashcards,
specifically to avoid perturbing `test_experiment.py`/`test_flashcards.py`'s
hardcoded exact-count assertions (both do unscoped global aggregation over
shared tables). Logged as EVD-2026-09-26-001. Relevant if a future sprint
in this component adds more `review_events`-consuming fixtures.

One unrelated pre-existing `test_examinations.py` failure (a hardcoded date
now trailing a fixture's relative-now() row) was independently reconfirmed by
the test runner and correctly did not block this sprint's TESTS_PASSING
verdict — worth knowing this flake is still latent in the suite as of
2026-09-26 if it recurs in a later sprint's run.

Stopped at TESTS_PASSING per instructions — `/sprint-close` intentionally not
invoked (human gate, out of scope for the orchestrator).
