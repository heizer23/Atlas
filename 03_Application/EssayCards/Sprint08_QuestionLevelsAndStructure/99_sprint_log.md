# Sprint Log — Sprint08_QuestionLevelsAndStructure

```json
{
  "sprint_name": "Sprint08_QuestionLevelsAndStructure",
  "component_name": "EssayCards",
  "layer": "03_Application",
  "log_format": "v2",
  "current_state": "IMPLEMENTATION_IN_PROGRESS",
  "last_agent": "direct (no orchestrator)",
  "next_agent": null,
  "blocking": false,
  "block_reason": null
}
```

## Log

- 2026-09-09 direct implementation from `00_draft.md` at user request (offered the full
  R-PRO-BP-01 pipeline vs. direct implementation explicitly; user chose direct) — the
  design → design-review → implement → test-runner agent pipeline was not run. Recorded
  here for traceability (R-OPS-BP-01), matching the precedent set by
  `Sprint05_ReviewQueueOrdering`.
  read: schema.sql, backend/ingest.py, backend/routers/essays.py,
        backend/routers/flashcards.py, backend/exploration.py,
        backend/routers/examinations.py, backend/database.py, src/ShellEntry.tsx,
        tests/test_essays.py, tests/conftest.py, CLAUDE.md
  wrote: schema.sql, backend/routers/essays.py, backend/routers/flashcards.py,
         tests/test_questions.py, src/ShellEntry.tsx, CLAUDE.md,
         Sprint08_QuestionLevelsAndStructure/00_draft.md
- Migration: `alter table essaycards.flashcards add column if not exists level integer
  not null default 2` + guarded `ck_flashcards_level check (level >= 1)`, applied
  automatically by `init_schema()` on container start against BOTH the production
  (`atlas`) and test (`atlas_test`) databases. No IDs changed, no rows deleted,
  `flashcard_review_state` untouched. Verified against live production data
  post-deploy: existing cards read back with `level: 2`, unchanged question/answer/id.
- New endpoints: `GET /essays/{essay_id}/questions`, `GET /essays/{essay_id}/export`,
  `POST /flashcards/upsert`, `GET /flashcards/{flashcard_id}/export`.
- New frontend views: `QuestionOverviewView` (`/essaycards/essays/:id/questions`),
  `QuestionImportView` (`/essaycards/questions/import`); "Export essay" button added to
  `ReaderView`.
- Tests: `docker exec atlas-essaycards-test pytest tests/test_questions.py -v` → 22
  passed. Full suite: 176 passed, 1 pre-existing unrelated failure
  (`test_examinations.py::test_import_stores_new_result_without_overwriting_history` —
  stale hardcoded date, fails identically on a clean tree, unrelated to this sprint).
- Frontend: `npx vite build` (used as the type-check/build gate throughout this app, same
  as every prior EssayCards frontend change) passed clean. A repo-wide `tsc -b` run was
  attempted and failed identically (`Cannot find module 'react'`, etc.) for every
  unrelated app (Calendar, Chronicle, FoodTracker, ...), confirming it is a pre-existing
  environment issue, not something introduced here.
- Containers `atlas-essaycards`, `atlas-essaycards-test`, and `atlas-shell` rebuilt and
  redeployed.
