# Design Review — EssayCards (Sprint14_SectionProgressionAndRevalidation)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is layer-correct (03_Application, no platform leakage, no new exposure) and unusually complete. Pass rule, cascade, revalidation branching and derived-state logic are each defined once and are consistent across architecture, scaffolding, schema and test spec. Every designer-flagged draft deviation is defensible and documented. One user-facing decision is left open for the implementer (the revalidation grade control) and must be pinned. A few cross-artifact wording and scaffold hazards are listed below as minor items. Both JSON artifacts parse cleanly on careful reading (balanced braces/brackets, no trailing commas, no unescaped inner quotes), but I could not execute a parser.

## Confirmed Problems
1. **Revalidation grade control left to implementer choice**
   - Severity: Major
   - Location: `10_architecture.json` internal_flow step 16 ("Grade controls may be the standard four or a two-way Correct/Incorrect pair mapped to good/again - either way..."); `10_test_spec.md` "[UI] Revalidation session shows remaining count and completes"
   - Why it is a problem: The grade control is the only user input to the central revalidation protocol. The server fixes the semantics (`again` = incorrect; `hard`/`good`/`easy` = correct, `10_architecture.json` contracts.invariants "REVALIDATION CARD HANDLING"). The UI design offers two materially different input models and picks neither. With four buttons, a user pressing "Hard" silently gets a "preserved, no FSRS change" outcome. That is a non-obvious consequence of an unstated mapping. The [UI] scenario ("answers all three") cannot be written deterministically for either model.
   - Impact: Two implementers would ship different UX. A user could believe "Hard" tightens scheduling when it changes nothing. The UI test cannot assert a specific control set.
   - Likely Cause (Design Phase): Ambiguous Definition. A UI decision was deferred with "either way" because the server contract was already safe under both options.

2. **Schema header contradicts the backfill's historical verdicts**
   - Severity: Minor
   - Location: `10_schema.sql` header lines 22-23 ("`passed` columns record the verdict computed at write time under the threshold in force then") vs section 1 (lines 36-41, historical rows re-graded at `score >= 5` / literal 420) and section 4 (grandfathers guided score >= 3 as unlocked)
   - Why it is a problem: The Sprint12 threshold in force at write time was score >= 3. The backfill applies the new 70% rule retroactively, so a historical guided 3 is stored `passed = false` while its section is simultaneously grandfathered as guided-passed. `10_test_spec.md` "Backfill records stored verdicts under the 70% rule" (false, false, true, true) matches the SQL, so the comment is the outlier. The history UI will show "not passed" next to an unlocked section.
   - Impact: Misleading documentation for later agents. Some user confusion in the history UI (accepted in `10_architecture.json` risks).

3. **Forecast counts cards the focus queue will not serve**
   - Severity: Minor
   - Location: `10_architecture.json` interfaces GET /flashcards/stats ("purpose": forecast "matches the focus session it accompanies") vs its boundary_construction ("needs_revalidation cards remain counted")
   - Why it is a problem: Flagged cards stay in the `due_now` band while `/due` and `open_count` exclude them, so one screen can show inconsistent figures. The purpose line states a guarantee that the rule below it contradicts (R-CON-BP-08).
   - Impact: The Review page forecast overstates "due now" after a cascade. The revalidation session hides the panel, but normal focus sessions do not.

## Recommended Improvements
1. **Reword the stats purpose line**
   - Location: `10_architecture.json` interfaces GET /flashcards/stats purpose
   - Improvement: State plainly that the forecast excludes locked cards but includes flagged cards (FSRS due dates unchanged), or exclude flagged cards for consistency with `open_count`. Pick one.
   - Why: Removes the self-contradiction with no extra mechanism.
2. **Correct the schema header**
   - Location: `10_schema.sql` header lines 20-24
   - Improvement: Say that the one-time backfill re-grades historical rows under the 70% rule (literal 420), and that rows written from this sprint on carry the verdict in force at write time.
   - Why: Aligns the comment with the SQL and the test spec.
3. **Pin per-dot interaction for section dots**
   - Location: `10_scaffolding.json` EssayProgressDot / SectionProgressDots
   - Improvement: Only EssayProgressDot states `stopPropagation` against row navigation. Say the same for SectionProgressDots.
   - Why: Section dots sit inside the same navigable row, so tap precedence is otherwise unspecified (the nested-interactive pattern seen in Sprint13).

## Scaffold-Only Observations
1. **Existing fixture inserts will violate `passed NOT NULL`**
   - Location: `10_scaffolding.json` tests/fixtures.sql entry; `10_schema.sql` section 1
   - Observation: `passed boolean NOT NULL` has no default. `tests/fixtures.sql` inserts into `section_examinations` without `passed` at lines 137, 365 and 390, so every test fails at fixture load. Neither the fixtures.sql scaffold entry nor internal_flow step 18 mentions updating these inserts.
   - Impact on implementation: The implementer will hit this immediately and must add `passed` to all three inserts. Easy to fix, but it should be listed.
2. **`10_schema.sql` carries its own `begin;` / `commit;`**
   - Location: `10_schema.sql` lines 33 and 228; canonical `schema.sql` wraps everything in one `begin;` (line 1) / `commit;` (line 638)
   - Observation: Folding the file in verbatim nests transactions: a warning on the inner `begin`, and an early commit that ends the outer transaction.
   - Impact on implementation: The implementer must strip them when folding in. The scaffold only says "folds in".
3. **`ESSAY_EXAMINATION_SCHEMA` omits `id`**
   - Location: `10_scaffolding.json` routers/examinations.py private_objects vs `10_architecture.json` GET /essays/{id}/examinations row_shape ("id, examined_at, ...")
   - Observation: The architecture row_shape includes `id`; the scaffold schema column list does not.
   - Impact on implementation: Minor Dataset schema mismatch. `score_percent` and `summarize_cascades` are also scaffolded but absent from the architecture `interfaces.provides` list.
4. **`next_step` null rule is ambiguous in one place**
   - Location: `10_architecture.json` internal_flow step 7 ("null when violet/blue-complete")
   - Observation: Mixes the section and essay ladders. The essay value `unguided_essay_oral` applies when the essay is Blue. A zero-card guided-passed section reports `flashcards_established` forever, although it can never turn green.
   - Impact on implementation: A misleading tooltip in the empty-section edge case only.

## Hard Rule Violations
1. **R-CON-BP-09 Cross-Artifact Truth Consistency**
   - Rule Source: `.claude/rules/R-CON-BP.md`
   - Location: `10_schema.sql` header lines 22-23 vs section 1 backfill (Problem 2)
   - Violation: The artifact presents two interpretations of how historical `passed` verdicts are defined.
   - Required Fix: Correct the header comment (Recommended Improvement 2). Non-blocking, since the SQL and test spec agree.
2. **R-CON-BP-08 Contract Self-Containment**
   - Rule Source: `.claude/rules/R-CON-BP.md`
   - Location: `10_architecture.json` GET /flashcards/stats purpose vs boundary_construction (Problem 3)
   - Violation: The contract's stated guarantee depends on reading past a contradicting rule.
   - Required Fix: Reword per Recommended Improvement 1. Non-blocking.

R-CON-AL-01 to -06, R-CON-BP-04/07/10/11, R-OPS-BP-02 and the layer, dependency and platform-boundary rules were checked with no violation:
- R-CON-AL-04/05: no PATCH or clearable field is introduced. Omit-vs-null on `section_anchor_slug` is fully defined and has test scenarios.
- R-CON-AL-06: server `now()` and the external `examined_at` are each declared, and import-order application is documented.
- R-CON-AL-02: every allowed parameter combination yields a constructible, possibly empty Dataset.
- R-OPS-BP-02: no new ports or exposure.

## Open Uncertainties
1. **Pass threshold on the 0-6 scale (draft deviation)**
   - Location: `10_architecture.json` invariants "PASS RULE", open_questions[0]
   - Uncertainty: 70% resolves to score >= 5, so 66.7% (score 4) fails. This is stricter than Sprint12's >= 3. I verified the arithmetic and that all four oral kinds, the package echo, the prompts and the stored `passed` flow from one function.
   - Why it matters: Behavioural, not structural. The design is correct as specified, but the product owner must confirm 5/6 before implementation.
   - Suggested owner: Product
2. **Cascade trigger limited to Essay Violet (draft deviation)**
   - Location: `10_architecture.json` invariants "UNGUIDED PASS SEMANTICS", open_questions[1]
   - Uncertainty: Draft section 13 reads as "any failed unguided essay oral", but section 12 and the acceptance criteria scope it to a retake at Violet. The design follows section 12; a first-ever failure is history-only.
   - Why it matters: I consider the reading sound and the test spec covers both cases ("Failing the unguided essay oral when not violet is history only"). It still needs product confirmation.
   - Suggested owner: Product
3. **Queue exclusion of flagged cards and `open_count` change (draft deviation)**
   - Location: `10_architecture.json` invariants "REVALIDATION QUEUE VS NORMAL QUEUE" and "CATEGORY STATS", open_questions[4]
   - Uncertainty: The draft says category stats stay unchanged, but `open_count` now excludes locked and flagged cards. Excluding flagged cards from `/due` fits "outside the new unlock/revalidation logic". Changing `open_count` is a deliberate deviation. The test spec "Category-level counts are preserved" covers only `progress_*`, and a separate scenario covers `open_count`.
   - Why it matters: A category "Study" button on a fully locked essay opens an empty session, and the overview would otherwise overstate open cards.
   - Suggested owner: Product
4. **Breaking removal of the nine Sprint12 learning fields (draft deviation)**
   - Location: `10_architecture.json` provides GET /essays, risks[4]
   - Uncertainty: I grepped for `learning_level`, `milestone_*`, `PASS_SCORE_THRESHOLD`, `cards_seen_count` and `cards_future_safe_count`. They occur only in the EssayCards `src/ShellEntry.tsx`, `backend/routers/essays.py`, `CLAUDE.md`, tests, and the stale `00_architecture/scaffolding.json` design copy. The scaffold covers each live consumer. The only residual risk is a stale cached frontend bundle, which is already noted.
   - Why it matters: Acceptable under R-CON-BP-09 because the sole consumer is reworked in-sprint.
   - Suggested owner: Implementer (grep before declaring done, as already deferred)
5. **Grandfathering rule and import-order semantics**
   - Location: `10_schema.sql` section 4; `10_architecture.json` invariants "TIME AUTHORITY", open_questions[3]
   - Uncertainty: Product has not confirmed that existing sections with reviewed cards or a guided exam >= 3 are unlocked. An older-dated failing result imported later can cascade against a newer pass, as the design documents. Cards moved between sections by the markdown CLI could also land in a locked section; this is not addressed.
   - Why it matters: A wrong grandfathering rule empties a user's queue, and the design mitigates this with a dedicated migration test.
   - Suggested owner: Product
6. **Concurrency guard wording**
   - Location: `10_architecture.json` internal_flow step 6 ("FOR UPDATE ... or its absence handled by insert-first")
   - Uncertainty: Two options are named without a choice. Either works, because the cascade requires an existing row.
   - Why it matters: Minor. The implementer should use insert-if-absent then `SELECT ... FOR UPDATE`.
   - Suggested owner: Implementer

## Minimal Change Set
1. In `10_architecture.json` step 16 and `10_scaffolding.json` ReviewSessionView, choose one revalidation grade control (the standard four buttons, or Correct/Incorrect mapped to good/again). Document the resulting meaning of "Hard" if the four buttons are kept. Update the `[UI] Revalidation session` scenario in `10_test_spec.md` to name that control.

## Approval Condition
- `10_architecture.json` step 16, `10_scaffolding.json` ReviewSessionView and the `[UI] Revalidation session` scenario in `10_test_spec.md` all name the same single grade-control set, with the grade-to-correct/incorrect mapping stated.
