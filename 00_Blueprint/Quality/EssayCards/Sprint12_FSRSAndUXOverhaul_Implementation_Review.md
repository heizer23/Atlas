# Implementation Review — EssayCards — Sprint12_FSRSAndUXOverhaul

**Verdict:** APPROVED
**Date:** 2026-10-01
**Reviewer:** independent-review-agent (Phase D, per `00_draft.md`'s "Note" section, following the `Sprint10_DualSchedulerAB` precedent)

## Scope

Independent adversarial review of the implemented code (working tree against `main`,
not yet committed) for a large, high-risk sprint: FSRS becomes the sole scheduler
(replacing Sprint10's dual Classic/FSRS A/B experiment), a derived 0–4 essay
`learning_level`, essay/section button consolidation (`ActionMenu` + category
collapse), and a reworked stats page. All claims below were checked directly against
`git diff main -- 03_Application/EssayCards/`, the current file contents, and the
test files — not accepted from `10_architecture.json` / `11_design_review.md` /
`13_design_review.md` / `50_test_report.md` at face value, though all were read
first for context, along with `00_draft.md`, `12_design_corrections.md`, and
`99_sprint_log.md`.

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| _(None)_ | | | |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `src/ShellEntry.tsx::ActionMenu` | The dropdown is keyboard-*operable* (native `<button>` elements, Tab-reachable, Escape-to-close, `role=menu`/`menuitem`, `aria-expanded`) but does not implement arrow-key roving focus within the open menu, which a strict ARIA menu pattern would include. The draft only required "usable with touch and keyboard, with clear expanded/collapsed states," which this meets; flagging only as a possible follow-up polish item, not a gap against the stated requirement. |
| 2 | `backend/routers/essays.py::_learning_progress_subquery_sql` | `PASS_SCORE_THRESHOLD = 3` (of a 0–6 exam scale) is a named, documented design decision (`10_architecture.json` cites the existing `EXAM_PROMPT_INTRO` rubric language), not left implicit — but the constant itself is inlined as a literal `3` in the SQL (with a comment) rather than a Python-level named constant. Purely a style observation; the value is unambiguous and correctly commented at both occurrences. |

_(Both items are informational; neither blocks approval.)_

## Findings Detail (most important)

1. **Migration safety — verified, including the rerun-safety fix the sprint log
   claims.** `schema.sql`'s Sprint12 block (lines ~498–530) creates
   `essaycards.pre_fsrs_migration_backup_sprint12` guarded by **both** the backup
   table's own absence **and** the source `scheduler` column's continued existence —
   correctly handling all three cases an idempotently-rerun startup file must
   survive: first run on an upgrading DB (columns present, gets backed up), any
   rerun after that (backup table now exists, no-op), and a brand-new DB that never
   had the Sprint10 columns (second guard prevents an `UndefinedColumn` failure, since
   no `ADD COLUMN` statements for them were reproduced in this file — confirmed by
   reading the file's own "Sprint10_DualSchedulerAB (retired)" comment block). This
   is exactly the bug class the sprint log describes fixing ("dead Sprint10 ADD
   COLUMN/backfill statements that would re-add/re-drop columns and hard-fail on
   `review_events` every restart") — independently confirmed absent from the current
   file, not merely asserted. `tests/test_migration.py` exercises this with direct
   DB assertions (`test_backup_table_snapshots_pre_migration_scheduler_data_once`,
   `test_scheduler_columns_are_dropped_...`).
   `backend/migrate_fsrs_state.py::migrate_legacy_fsrs_state` is independently
   idempotent on top of this: its candidate `SELECT` filters on `fcs.flashcard_id is
   null` (no existing state), and its `INSERT` additionally carries `ON CONFLICT
   (flashcard_id) DO NOTHING` as a second idempotency layer.
   `test_legacy_fsrs_backfill_is_idempotent_on_rerun` asserts byte-identical state
   and a single row after two runs. Both migration never write
   `next_due_at`/`review_interval`/`last_reviewed_at` — confirmed by reading every
   `UPDATE`/`INSERT` statement in both files; `estimate_initial_fsrs_state` takes
   those fields as read-only inputs only.

2. **Due-queue selection/ordering preservation — verified untouched.**
   `git diff main -- backend/routers/flashcards.py` shows the only change to
   `list_due_flashcards`'s SQL is the removal of `frs.scheduler` from the `SELECT`
   list (the dropped column) — grepping the full diff for `where`/`order by` (case-
   insensitive) returns zero hits inside this function. The `RECENT`/`BACKLOG`
   split, the 24-hour review-vs-focus interval gate, and all tie-breakers are
   byte-for-byte unchanged. `GET /flashcards/stats` is not touched by this sprint's
   diff at all.

3. **Milestone/level correctness — verified, including the zero-card non-vacuity
   requirement.** `_learning_progress_subquery_sql` computes `card_counts.total`
   from a live join (not cached), and both card milestones are gated
   `cc.total > 0 and ...` — a zero-card essay has `total = 0`, so both card
   milestones evaluate `False` regardless of any other state. This is independently
   confirmed by `test_essay_with_zero_cards_has_card_milestones_false_and_level_bounded_by_exam_milestones`,
   which is a genuinely adversarial test: it uses a fixture essay with zero cards
   but a **passing** guided exam on both sections specifically to prove the card and
   exam milestones don't get conflated (`learning_level == 1`, not higher). The exam
   milestones correctly require per-section coverage (`sc.n = count(latest rows)`)
   and a per-section minimum score (`not exists (... where score < 3)`), not an
   average — matching the draft's "milestones... calculate correctly" requirement.
   All nine fields are computed by one shared SQL fragment reused identically by
   list and detail endpoints (no duplicated logic to drift).

4. **Button/nav consolidation completeness — verified against the actual code, not
   just the design artifact.** Cross-checked every row of `10_architecture.json
   §button_nav_inventory` (21 entries) against the current `src/ShellEntry.tsx` and
   `src/shellConfig.ts` directly: the essay-header `ActionMenu`'s primary/secondary
   construction (`hasCards` branch for Study vs. Question-overview-as-primary,
   `status === 'complete'` gate on both oral-exam secondary items, `sections.length
   > 0` gate on + New nugget) matches the inventory's claims exactly; the
   section-end `ActionMenu` (Review this section primary; Export/Insert secondary)
   likewise; `shellConfig.ts`'s `mobilePrimaryNav`/`desktopNav`/`secondaryMenu`
   match the inventory's nav-regrouping claims exactly, including the Experiment
   entry's full removal (grepped — zero remaining references to an experiment route
   anywhere in `ShellEntry.tsx`/`shellConfig.ts` outside one historical code
   comment). `secondaryMenu` is a pre-existing field on the Shell's own `AppConfig`
   type (`02_Platform/Atlas_Shell/src/types.ts`), genuinely consumed by
   `MoreMenu.tsx` — not an invented interface (R-CON-BP-06 satisfied). The
   `tests/ui/button_nav_inventory.spec.ts` added during the fix-iteration loop
   walks this inventory as actual Playwright assertions, closing the coverage gap
   the test-runner correctly flagged in its first pass.

5. **Scope discipline — clean.** `git diff main -- 03_Application/EssayCards/`
   contains zero references to "Descartes" (grepped the full diff). The habit
   tracker is a separate component untouched by this diff. The only file changed
   outside `03_Application/EssayCards/` by this sprint's own work is
   `00_Blueprint/Quality/agent_rule_evidence.md` (the design review's required
   evidence-store append, per R-PRO-BP-02) — `03_Application/ClaudeConsole/
   src/ShellEntry.tsx` and the rotated `02_Platform/Postgres/*.dump` files visible
   in the broader `git status` predate this sprint and are unrelated (confirmed
   against the sprint log's own `read`/`wrote` file lists, none of which name
   ClaudeConsole or the Postgres dumps).

6. **Open design uncertainties — both resolved correctly in the implementation.**
   `13_design_review.md` carried forward two unresolved Open Uncertainties.
   (a) `migrate_legacy_fsrs_state()`'s placement in `main.py`'s startup retry loop:
   verified it sits inside the existing `try` block, after `init_schema()` and
   before the `return`, so a migration failure is retried through the same
   10-attempt/3s loop as a DB-not-ready failure — not dead code, not outside the
   retry net. (b) The bootstrap `review_card()` call's `review_datetime`: verified
   it is timestamped at the card's own `last_reviewed_at`, not wall-clock "now" —
   making `estimate_initial_fsrs_state` a deterministic, reproducible function of
   the card's own history alone, consistent with the "safe to rerun" invariant.

7. **R-CON-AL compliance spot-check — clean.** `backend/routers/review_stats.py`'s
   module docstring and each endpoint's docstring explicitly declare time basis
   (Postgres `now()`, UTC calendar days for `/activity`), zero-fill behavior (always
   exactly 3 / 30 / 6 rows respectively), ordering, and the `recall_rate: null`
   vs. `0` distinction for an empty window (R-CON-AL-01). `GET /review-stats/activity`
   and `/intervals` use `generate_series` LEFT JOIN patterns to guarantee the
   zero-filled row count independent of data presence — verified by reading the SQL,
   not just the docstring's claim.

8. **Atomicity — unchanged from Sprint10's independently-verified pattern.**
   `POST /flashcards/{id}/review` still reads `now()` once and performs the
   `flashcard_review_state` UPDATE, the `fsrs_card_state` upsert (now unconditional,
   since FSRS is the only scheduler), and the `review_events` insert inside one
   `with get_db() as conn: with conn.cursor() as cur: ... conn.commit()` block.

9. **Design-review process quality.** Both Major findings from `11_design_review.md`
   (the `estimate_initial_fsrs_state` 2-arg/3-arg signature inconsistency, and the
   `ReviewStatsPanel` prop-contract mismatch for the reused forecast zone) are
   verifiably fixed in the final code: `estimate_initial_fsrs_state` is
   consistently 3-argument everywhere (`backend/scheduling.py`,
   `backend/migrate_fsrs_state.py`'s call site), and a standalone `ForecastGrid`-
   style rendering exists in the stats page independent of `ReviewStatsPanel`'s
   session-scoped props (confirmed via the stats endpoints' independent, props-free
   SQL/response shapes in `review_stats.py`).

## Approval Condition

None — approved as-is. No Critical or Major issues found on independent
re-verification of the diff. No evidence-store entry required from this review;
the two non-blocking items above are both low-severity style/polish observations
that do not rise to Major.
