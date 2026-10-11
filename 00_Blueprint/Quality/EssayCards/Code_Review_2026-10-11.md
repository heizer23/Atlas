# Code Review — EssayCards — whole component, emphasis on Sprint15 (`ea206ec`) + UI pass (`89c8362`)

**Verdict:** APPROVED
**Date:** 2026-10-11
**Reviewer:** atlas_code_reviewer
**Scope:** `03_Application/EssayCards` backend, frontend, schema, tests. Line-level review was limited to the diffs of `ea206ec` (Sprint15: `backend/routers/essays.py`, `backend/routers/review_stats.py`, `src/ShellEntry.tsx`, `tests/test_essays.py`, `tests/test_review_stats.py`) and `89c8362` (UI pass: `src/ShellEntry.tsx`, `tests/ui/button_nav_inventory.spec.ts`). For the rest of the component I did targeted sweeps: GET response shapes against the live service (all 16 list/detail GETs return `Dataset`), SQL construction (every f-string interpolation is a module constant or a parameterised fragment, with no user input), mutation transaction ordering (no early `return api_error` after a write), error-path probes, and the `get_db` lifecycle. No uncommitted changes under the component. `b8860ff` / `e15ddca` only touch `CLAUDE.md` / `docs/`.

**Evidence run:**
- `docker exec atlas-essaycards-test pytest tests/ -q` gave **344 passed**, 0 failed, in 108 s. The container's copies of the 4 Sprint15 backend/test files are byte-identical to the repo.
- The previously known time-dependent examinations failure no longer reproduces.
- The Playwright `[UI]` specs were not run.
- Frontend deploy: `02_Platform/Atlas_Shell/dist/` (mtime 2026-10-11 19:09:57) is newer than `src/ShellEntry.tsx` (18:23:44), so it is verified.
- No `Atlas_Shell/nginx.conf` / `Dockerfile` change is involved.
- `atlas-essaycards` was created 2026-10-09 13:54 local, which matches the `ea206ec` commit time, so the running backend has Sprint15.

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `backend/routers/sentence_feedback.py:120-121` (Pydantic `SentenceFeedbackUpdate` body); `backend/routers/essays.py:492` (`include_examinations: bool`); root cause `02_Platform/packages/platform_errorhandling/logFastapi.py:14` | **R-CON-BP-04** says "On error: return `ApiError` … Never return a bespoke error shape." Two calls return FastAPI's default `422 {"detail":[...]}` instead of `ApiError`: `PATCH .../sentence-feedback` with `{}` (verified live), and `GET .../export?include_examinations=maybe`. The platform handler only registers `Exception`, not `RequestValidationError`. EssayCards' raw-`Request` endpoints (ingest, upsert, review) avoid this deliberately; the Sprint13 PATCH and the new Sprint15 query param do not. Nothing breaks today, because the frontend only ever sends well-formed bodies and `true`. A single platform-level `RequestValidationError` handler is the proportionate fix, rather than more per-endpoint raw parsing. |
| 2 | `essays.py:265` `get_essay`, `:439` `export_essay`, `:492` `export_section`; `examinations.py:164`, `:212`; `nuggets.py:293`; `flashcards.py` `/{id}/export`; `_upsert_question` section lookup | A malformed (non-UUID) path id returns **500 INTERNAL_ERROR** instead of the documented 404. I verified this live for 7 routes. Postgres raises `invalid input syntax for type uuid`. Other endpoints in the same component already guard against this: `progress.py:51` `_is_uuid`, `examinations.py:113`, `flashcards.py:62`, and `sentence_feedback.py` (which compares on `id::text`). The `ApiError` envelope is kept, so no consumer breaks. It only shows up on hand-typed URLs, and it adds noise to the error logs. |
| 3 | `tests/test_review_stats.py` (Sprint15 `_expected_orals` / `test_summary_rows_carry_oral_counts_per_window`) | The test oracle re-runs the same `UNION ALL … examined_at >= now() - interval` SQL as `_orals_aggregate`. It therefore cannot catch a definitional error the two share, such as a wrong window or a missing table. The fixtures also seed no exam inside the 24 h window (the newest is `now() - 2 days`), so `day` is only ever checked as `0 == 0`. Sprint15 still has real coverage: the guided/unguided split, sum consistency and window monotonicity are asserted, and the export tests are good (they cover default key absence, guided-only oldest-first, the empty list and the ingest round-trip). |
| 4 | `docs/export_insert.md`, `docs/sprint_history.md` | The component docs (split out of `CLAUDE.md` on 2026-10-11, after Sprint15) do not mention Sprint15 at all. Missing items are `include_examinations` / `focus_section_examinations`, the "Improve section" flow, and the `orals_count` / `guided_orals_count` / `unguided_orals_count` summary columns. `CLAUDE.md` tells agents to "Read the matching doc before changing that area", so the next change to section export starts from a stale description (R-CON-BP-01 legibility). The authoritative design record for now is `Sprint15_StatsOralsAndImproveSection/05_fast_path_plan.md`. |
| 5 | `Sprint15_StatsOralsAndImproveSection/` | This is a process observation, not a code defect. The sprint is committed and its tests pass, but `99_sprint_log.md` still says `IMPLEMENTATION_IN_PROGRESS` (already counted in `Rule_Audit_2026-10-11.md` item 5). There is also no `10_test_spec.md`, although R-PRO-BP-01 §11 says it "remains required under the same condition as §1" and the component exposes an API. See Rule Friction. |

Correctness checks on the recent diff that passed (for traceability):
- `_orals_aggregate`: `exam_type` exists on both tables, with CHECK `('guided','unguided')`, so guided + unguided = total. Interval literals come from the constant `_WINDOWS`. Time basis is persisted `examined_at` against server `now()`, as declared in `05_fast_path_plan.md`.
- `export_section`: the guided-only filter and `examined_at asc` ordering match the plan. `isoformat()` is applied before `JSONResponse`, so the non-pydantic-sibling serialization pattern does not recur. The default package is unchanged.
- `handleImproveSection`: the error path keeps `ok:false`, so the button does not toggle to "Import". It reuses the sessionStorage drop-detection key on purpose.
- The UI pass moved "Due for review" off the essays header. It is still reachable via `shellConfig.ts` mobile and desktop nav. `gradeBtnGoodStyle` sets `on-primary` text, so contrast holds.

## Rule Friction

| Rule | Classification | Evidence | Cost / Benefit | Recurrence |
|------|----------------|----------|----------------|------------|
| R-CON-BP-04 (error envelope) | **Missing** (platform enforcement gap) | The rule text says "Never return a bespoke error shape". `logFastapi.py:14` handles only `Exception`. Live: `PATCH .../sentence-feedback {}` gives 422 `{"detail":[...]}`. | The rule is right, and it points at a real inconsistency. But compliance is left to each endpoint's author. EssayCards pays a per-endpoint tax: raw-`Request` + manual parsing on ingest, upsert and review, documented as a "deliberate deviation" in `CLAUDE.md`. It still leaked twice (a Sprint13 PATCH and a Sprint15 query param). The leak is a platform capability gap, not a design-review gap. | Also seen in EVD-2026-08-27-001 (same component, Sprint01, flagged at design time). Now 3 endpoints across 3 sprints. |
| R-PRO-BP-01 §11 (fast path) + §1 (`10_test_spec.md` required if API) | **Ambiguous / conflicting** | §11: "`10_test_spec.md` remains required under the same condition as §1". All 3 fast-path sprints in the repo (EssayCards S15, StoryReader S02, S03) have only `00_draft.md`, `05_fast_path_plan.md` and `99_sprint_log.md`. `Rule_Audit_2026-10-11.md:9` nevertheless rates "All 3 post-§11 fast-path sprints are compliant". | S15's plan has a "Tests" section that names each scenario, and the tests implement it. A separate `10_test_spec.md` would duplicate it for a 5-file change. That is pure ceremony, and practice (3/3) plus the audit have already treated it as optional. The rule text and its enforcement disagree. Suggest that §11 explicitly let a `## Tests` section in `05_fast_path_plan.md` satisfy the test-spec requirement. | 3/3 fast-path sprints. Not previously logged. |
| R-PRO-BP-01 §5 (verdict vocabulary) | **Ambiguous** | The `APPROVED_WITH_CHANGES` row maps to `DESIGN_REVIEWED_CHANGES_REQUIRED` and "means every listed change is non-behavioral". | For an implementation review with only non-blocking *behavioral* suggestions (items 1–2), none of the defined verdicts fits. `APPROVED_WITH_CHANGES` is reserved for non-behavioral changes, and `CHANGES_REQUIRED` implies blocking. I chose `APPROVED` with the items listed as non-blocking. This costs no extra artifacts, only interpretation. | First observed (prior EssayCards implementation reviews were plain `APPROVED`). |
| R-CON-AL-01 / R-CON-AL-06 | **Helped** | `05_fast_path_plan.md` states params, default, ordering, the empty result (`[]` / 0), the window boundary and the time basis for both changed endpoints. | The code matched every stated clause, which made verification quick. | — |
| Report path (agent definition vs caller/memory) | **Ambiguous** | The `atlas_code_reviewer` definition specifies `Code_Review_<date>.md`. The caller asked for `Architecture_Audit_<date>.md`, a convention that originates in the architecture-audit memory note. | I followed the agent definition, because this is a code review, not an architecture audit. The cost is a one-time naming question for whoever looks for the file. | First observed. |

No friction observed for R-CON-BP-03, R-CON-AL-04/05 (the only PATCH is a single-flag explicit-value set with no nullable field), R-CON-PL-01/02 (no platform change) or R-OPS-BP-02 (no new ports; still bound to `127.0.0.1:8024`; SQL parameterised).

## Approval Condition

None — approved as-is. Items 1–4 are recommended follow-ups. Item 1 is best done once in `platform_errorhandling` rather than in EssayCards.
