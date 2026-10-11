# Rule System Audit — 2026-10-11

**Verdict:** The constitutional rules are mostly earning their keep. The friction comes from process routing (a mandatory re-review after every change) and from agent and design templates that keep producing the same defects. The rule text itself is a smaller cause.
**Reviewer:** atlas_rule_auditor
**Evidence window:** 2026-04-09 → 2026-10-09, all components with sprint artifacts (13 components across 02_Platform and 03_Application). Read: 60 evidence entries (`agent_rule_evidence.md`, excluding the schema stub), 1 logged rule conflict plus 1 logged process deviation, 51 design reviews covering 28 sprints, 23 correction files, 33 sprint logs (state, fix_iterations, fast_path, and durations where v2), 3 architecture audits, 2 implementation reviews, 19 test reports (counted and traced through the sprint logs, not read individually), and the agent files `sprint_design_reviewer`, `sprint_design_application` (persistence template), `sprint_orchestrator`, and `sprint_design_corrector` (routing). Sprints initiated on or before 2026-04-09 are treated as exempt from R-PRO-BP-01.

## Summary
- **Working well.** R-CON-AL-03, R-CON-BP-04, R-CON-BP-06, R-CON-BP-09/10/11 and R-CON-AL-06 caught defects that would have crashed, rendered wrongly, or misrouted. Examples: the HabitTracker date-serialization crash, the StoryReader app never registering, a missing `id` on Dataset rows, a flat-vs-nested row shape mismatch, and timezone encoding. Only 3 of 33 logged sprints needed a test fix loop, and each needed just 1 iteration.
- **The fast path (R-PRO-BP-01 §11) works.** All 3 post-§11 fast-path sprints are compliant: `05_fast_path_plan.md` is present, `fast_path: true` is set, and the eligibility criteria are named in the log.
- **Friction 1, mandatory re-review.** 20 of 23 re-reviews found nothing new. All 7 re-reviews that followed wording-only or zero-blocking corrections found nothing. Two first reviews explicitly said "no re-review required" and a re-review ran anyway.
- **Friction 2, R-CON-BP-09.** It is the most-cited rule (33 mentions in 22 review files). Its catches are real, but about 5 of its blocking uses were prose-only drift. The root cause is that the design templates restate the same fact (signatures, enums, row shapes, persistence flags) in several places.
- **Friction 3, the reviewer agent.** `sprint_design_reviewer` loads rule files that no longer exist, uses a template that conflicts with R-PRO-BP-02 (30 of 51 reviews used the agent template), and defines "Critical" as "violates architecture rules", which inflates severity.
- **Cost check.** Logged agent time for the design chain (design + review + correction) is about 23,200s, against about 25,500s for implementation. Review plus correction alone is about 12,900s. The user preference says verification effort should not rival development effort, and here it does.
- **Top 3 changes:** (1) Scope down re-review to verdicts with blocking or behavior-changing corrections. (2) Add a blocking threshold to R-CON-BP-09 and have the templates declare each fact once. (3) Fix the reviewer and designer agent templates. Item 3 is not a rule change.

## Rule Scorecard

Counts are review-file mentions (total/files) across the 51 reviews and 23 corrections, unless noted otherwise. "Catch" means the cited finding was a real defect (crash, wrong render, misleading consumer, exposure) that was confirmed by correction or later implementation.

| Rule | Catches | Cost | Ambiguity | Assessment | Confidence |
|---|---|---|---|---|---|
| R-CON-BP-01 Architecture as AI Interface | 2 indirect (S12 scratchpad artifact; Atlas_Shell CSS leak in an audit) | Low | Used as a catch-all justification in audits for stale docs and duplication | KEEP | Medium |
| R-CON-BP-02 Contracts and Boundaries | 0 in reviews (0 ID mentions); 2 audit co-citations | None | Overlaps BP-01, BP-08, BP-09; never the sole basis | KEEP: silently satisfied via the architecture.json `interfaces`/`dependencies` template sections | Low |
| R-CON-BP-03 Durable State | 1 strong: TaskTracker inline DDL drifting from schema.sql (EVD-2026-04-09-001, audit) | Low | Audits stretched it to stale `CurrentArchitecture/` and exception records, which are documentation, not state | KEEP (benefit of the doubt) | Medium |
| R-CON-BP-04 UI Data Contract | 5 or more: ApiError bypass (EVD-2026-08-27-001), missing row `id` (EVD-2026-09-24-002, S14), FoodTracker field rename (audit), proxy shapes (EVD-2026-04-09-002/006) | Medium: the contract cannot express nested lists or sibling fields, so every app works around it (EVD-2026-08-28-001, EVD-2026-04-09-007, EVD-2026-10-01-004/005/006; HabitTracker took 3 rounds) | Proxy endpoints (resolved by v0.5) | KEEP + contract amendment (decision 4) | High |
| R-CON-BP-06 Consumer Pattern Fidelity | 1 strong: StoryReader `main.tsx` import omitted, so the app would never register (EVD-2026-09-24-001) | None | None | KEEP | Medium |
| R-CON-BP-07 Canonical Artifact Path | 2 real (Calendar runtime `schema.sql`; EssayCards stale path copied from CLAUDE.md, EVD-2026-08-27-002) | 3 wording-only (StorageTracker S01, FoodTracker S08, EssayCards S10 non-blocking) | `schema_artifact`: sprint delta vs runtime path is undefined in the template | KEEP; fix the template (see Template section) | Medium |
| R-CON-BP-08 Contract Self-Containment | 2 real (HabitTracker sibling-field mechanism; S12 scratchpad inventory) | Low | Overlaps BP-09 | KEEP | Medium |
| R-CON-BP-09 Cross-Artifact Truth | 6 or more real: StorageTracker row shape, NumericSeries LIST_SCHEMA, S03 enum, S12 signature, FoodTracker audit rename, S14 | High: about 5 blocking uses were prose-only (TaskTracker S07 param text, PersonalDevelopment ownership flag, FoodTracker S07 exception list, FoodTracker S08, S03 round 2 deferral text). Each forced a correction plus re-review | No blocking threshold; "intra-artifact" reading used | REWORD (blocking threshold) | High |
| R-CON-BP-10 Input Sufficiency | 3 (S12 signature, HabitTracker `anchor_date`, StoryReader step 7) | Low | Co-cited with AL-03 every time it blocks | KEEP | Medium |
| R-CON-BP-11 Behavioral Completeness | 3 (StorageTracker S02 x2, S03 transaction boundary) | 1 wording-only (FoodTracker S08) | None | KEEP | Medium |
| R-CON-PL-01 Platform Boundary | 2 audit catches (TaskTracker direct `labels.*` query; Atlas_Shell app CSS) | None | None | KEEP | Low (only 3 platform sprints) |
| R-CON-PL-02 Dependency Direction | 0 | None | None | INSUFFICIENT EVIDENCE | n/a |
| R-CON-AL-01 Query Behavior Explicitness | 1 (PersonalDevelopment schema columns); 1 audit minor | Low | 9-item checklist, satisfied via the `query_behavior` template block | KEEP | Medium |
| R-CON-AL-02 Scope-Mode Closure | 0 findings; 3 explicit "verified" lines | None | Overlaps BP-11 and AL-03 | INSUFFICIENT EVIDENCE (likely silently satisfied) | Low |
| R-CON-AL-03 Invariant Realizability | 3 strong: S09 main-spine titles (critical), HabitTracker date serialization (critical, would crash), HabitTracker `anchor_date` | Low | Overlaps BP-10 | KEEP | High |
| R-CON-AL-04 Partial Update Semantics | 0 new defects; evidence says it is "well internalized" (EVD-2026-09-21-002) | None | None | KEEP (working silently) | Medium |
| R-CON-AL-05 Round-Trip Completeness | 1 (S09 `nugget_id` UI half, a real feature fix) | Low | None | KEEP | Low |
| R-CON-AL-06 Time Authority | 1 strong (NumericSeries S03 timezone, EVD-2026-04-12-002); 1 non-blocking (Calendar) | Low | None | KEEP | Medium |
| R-OPS-BP-01 Surface Violations | Enables self-reporting; 7 review mentions | Low | Designers surface a fixable defect as a "risk" and stop there (EVD-2026-09-21-003, EVD-2026-10-01-004) | KEEP (see Conflicts) | Medium |
| R-OPS-BP-02 Security | 0 review findings; 28 compose bindings on 127.0.0.1; 3 explicit verifications | None | None | KEEP (working); 2 possible escapes (see Escapes) | Medium |
| R-PRO-BP-01 §3/§5 Re-review routing | Re-reviews found 3 new issues, all after substantive corrections | 20/23 re-reviews were pass-throughs; 7/7 after wording-only corrections | Reviewer's "no re-review required" is overridden by routing | SCOPE DOWN | High |
| R-PRO-BP-01 §1/§10 Required artifacts and UI scenario | 2 (FoodTracker S06 missing `10_schema.sql`/test spec); the manual UI pass found 3 real UX bugs (EVD-2026-08-28-003) | 1 ceremony-only loop (TaskTracker S09) | None | KEEP (cost covered by the §3 scope-down) | Medium |
| R-PRO-BP-01 §6 `/sprint-close` gate | n/a | 13 of 33 logged sprints never reached `SPRINT_COMPLETE` (including committed work) | Rule vs practice | KEEP; decision 8 | Medium |
| R-PRO-BP-01 §7 Orchestrator file ownership | n/a | 1 deviation: "orchestrator-inline" test fix (Notifications S01) | None | INSUFFICIENT EVIDENCE (single incident) | Low |
| R-PRO-BP-01 §11 Fast path | Replaced 3 ad hoc deviations; 3 compliant uses | Minimal | Orchestrator template has no fast-path awareness | KEEP | High |
| R-PRO-BP-02 Review/evidence structure | The evidence store is the backbone of this audit (60 entries, 13 components) | Severity carries no signal (57/60 "major", including EVD-2026-10-05-005 "small, unambiguous deviations") | Reviewer template conflict (logged 2026-09-26, unresolved) | KEEP; minor REWORD (severity) | High |

## Friction Findings

### F1 — R-PRO-BP-01 §3/§5: every APPROVED_WITH_CHANGES forces a correction and a full re-review (SCOPE DOWN)
- **Evidence.**
  - 28 reviewed sprints. 20 needed at least one correction round, for 23 correction files and 23 re-reviews.
  - 20 of 23 re-reviews returned APPROVED with no new finding. The 3 that found something (EssayCards S03 `13_`, HabitTracker `13_` and `15_`) all followed corrections that changed a mechanism or contract.
  - Zero-blocking reviews still looped: `LabelEngine/Sprint02_ReverseLookup/11_design_review.md` and `StorageTracker/Sprint01_Core/11_design_review.md` both say Blocking Issues: _(None)_.
  - Two reviews waived re-review in writing, and a `13_` re-review ran anyway:
    - `StorageTracker/Sprint02_ShoppingTasks/11_design_review.md`: "No re-review required — corrector may apply changes directly."
    - `TaskTracker/Sprint07_LabelFilter/11_design_review.md`: "may proceed to implementation without further review."
  - Wording-only or ceremony-only correction rounds: StorageTracker S01, TaskTracker S07, TaskTracker S09, FoodTracker S07, FoodTracker S08, EssayCards S03 round 2. Every following re-review found nothing (6/6, or 7/7 counting LabelEngine).
- **Cost.** Logged corrector time is 3,595s across 15 runs. Re-reviews are roughly half of the 33 logged reviewer runs (9,292s). Each loop also adds 2 artifacts and an orchestrator turn.
- **Proposed change.** In §5, replace the bullet "`APPROVED_WITH_CHANGES` and `CHANGES_REQUIRED` are equivalent…" with:
  > `CHANGES_REQUIRED` routes to the corrector and then to re-review. `APPROVED_WITH_CHANGES` means every listed change is non-behavioral (wording, cross-reference, artifact presence) and the review's Blocking Issues table is empty. It routes to the corrector, whose `1N_design_corrections.md` must confirm each item was applied. The sprint then moves directly to `DESIGN_APPROVED` without re-review.

  Add the matching `DESIGN_REVIEWED_CHANGES_REQUIRED → DESIGN_APPROVED` (corrector, APPROVED_WITH_CHANGES origin only) transition to §3.
- **Risk.** A corrector introduces a new defect while fixing wording. The data shows the in-correction regressions (S03 deferral, HabitTracker `anchor_date`) happened only in behavior-changing corrections, and those would still be re-reviewed.

### F2 — R-CON-BP-09 has no blocking threshold (REWORD)
- **Evidence.**
  - 33 mentions in 22 review files, the most of any rule.
  - Real catches: the StorageTracker S02 row shape, the NumericSeries S03 LIST_SCHEMA, and the S12 signature restated 4 times (EVD-2026-10-01-001).
  - Prose-only uses that still blocked: the TaskTracker S07 parameter description, the PersonalDevelopment `owns_persistent_state` flag vs notes (EVD-2026-04-30-001), the FoodTracker S07 exception field list (EVD-2026-04-14-004), and the S03 deferral wording (EVD-2026-08-30-002).
  - The user's own calibration (memory note on HabitTracker `elapsed_days`) already distinguishes "will definitely crash" from "prose admits a crashing literal reading but an obvious correct alternative exists".
- **Cost.** About 5 correction loops were triggered by prose drift where no implementer reading changes code or data.
- **Proposed change.** Append to R-CON-BP-09:
  > A contradiction is blocking when two readings of the artifacts would lead an implementer to different code, schema, or persisted state. Contradictions confined to descriptive prose (risks, notes, rationale) where the authoritative field (schema, signature, row_shape, internal_flow) is unambiguous are non-blocking and are corrected without re-review.
- **Risk.** Low. Reviewers keep the ability to block on any contradiction that affects behavior.

### F3 — R-PRO-BP-02 severity field carries no information (minor REWORD)
- **Evidence.**
  - 57 of 60 entries are `major`. The rule allows only critical/major, so implementer notes about trivial deviations are forced to `major` (EVD-2026-10-05-005).
  - The schema header in `agent_rule_evidence.md` lists `implementation_review` and `minor | informational` and omits `execution_issue`. Both contradict R-PRO-BP-02.
- **Proposed change.** In R-PRO-BP-02, allow `severity: minor` for `run_type: implementer_note | execution_issue`, and align the evidence file header with the rule.
- **Risk.** Negligible.

## Rules That Are Earning Their Keep
- **R-CON-AL-03.**
  - HabitTracker: raw `date` objects merged after `model_dump()` would raise `TypeError` in JSONResponse (EVD-2026-10-01-005, critical).
  - EssayCards S09: main-spine-only nugget references would always render as unresolved (EVD-2026-09-21-001, critical).
- **R-CON-BP-04.**
  - Malformed bodies bypassed ApiError (EVD-2026-08-27-001).
  - Dataset rows were missing `id` (EVD-2026-09-24-002, S14).
  - The v0.5 mutation exemption came directly out of audit F-06 (TaskTracker). That is the governance loop working as designed.
- **R-CON-BP-06.** StoryReader would never have registered in the shell (EVD-2026-09-24-001).
- **R-CON-BP-09/10/11.** The bulk of cross-artifact defects: row shapes, schema column keys, signatures, the S03 per-file transaction boundary. The S03 boundary would have broken against psycopg2's whole-transaction abort. A related savepoint gap still escaped to tests (EVD-2026-08-30-004).
- **R-CON-AL-06.** NumericSeries timezone encoding was deferred to the implementer and is now resolved in design.
- **R-CON-BP-03.** Caught the TaskTracker inline DDL drifting from `schema.sql`. Later designs explicitly cite this as the precedent avoided (HabitTracker `11_design_review.md`).
- **R-PRO-BP-01 §11.** Converted recurring undocumented bypasses (EssayCards S05, S08, ClaudeConsole) into 3 auditable fast-path sprints.
- **R-OPS-BP-02 and R-CON-AL-04.** Working silently. 28 of the loopback-capable bindings are on 127.0.0.1, and EVD-2026-09-21-002 states the backend tri-state discipline is internalized.
- **Non-rule catches.** About a third of major findings cited no rule: S10 `was_due` could never be false, S13 dead-code and tap precedence, S12 prop-contract reuse, Calendar asyncpg. The review stage's value is partly reviewer reasoning, not rule enforcement. This argues against adding rules to capture it.

## Template / Agent-Instruction Issues

| # | Defect pattern (blamed on a rule) | Evidence | Real cause | Fix location |
|---|---|---|---|---|
| T1 | Persistence flag and schema path findings (BP-07, BP-09, PRO-BP-01 §1) | EVD-2026-04-14-001, EVD-2026-04-30-001, FoodTracker S08 blocking #2, StorageTracker S01, Calendar S01 | `sprint_design_application.md` template defaults `"owns_persistent_state": true, "schema_artifact": "10_schema.sql"` and has no field for the runtime `schema.sql` path | Designer template: default `false`/`null`; add `runtime_schema_path` |
| T2 | BP-09 restatement drift | S12 signature stated 4 times; S03 `reason` enum in 3 places; StorageTracker row shape in 3 places | Architecture and scaffolding both restate signatures, enums, and row shapes | Designer template: declare once (scaffolding `public_objects`, or `exposed_surfaces.row_shape`) and reference elsewhere |
| T3 | Dataset sibling field / nested list workarounds (BP-04, BP-08, AL-03) | EVD-2026-08-28-001 (StorageTracker, EssayCards, Calendar precedent); EVD-2026-10-01-004/005/006 (HabitTracker, 3 rounds, "one field at a time") | `platform_contracts.Dataset` has no supported sibling or array mechanism | Contract (`UI_Data_Contract.md` + `contracts.py`) or a shared helper; decision 4 |
| T4 | Reviewer artifact format and severity | 30/51 reviews use the agent template vs 23 using the R-PRO-BP-02 table; conflict logged 2026-09-26 and unresolved | `sprint_design_reviewer.md` §Step 3 template; "Critical: Violates architecture rules"; verdict list lacks `CHANGES_REQUIRED` | `sprint_design_reviewer.md` |
| T5 | Reviewer loads non-existent rule files | `sprint_design_reviewer.md` lines 53–59 (`architecture_as_ai_interface.md`, `no_hidden_state.md`, …), also in `sprint_design_application/platform.md` and `sprint_implement.md`; none exist | Stale after the move to `.claude/rules/R-*.md` | Replace with R-* IDs in all four agents |
| T6 | Stale canonical path (BP-07) | EVD-2026-08-27-002 | Root `CLAUDE.md` line 37 still says `02_Platform/03_ErrorHandling/` (does not exist; the real path is `02_Platform/packages/platform_errorhandling`) | `CLAUDE.md` |
| T7 | Incomplete usage enumeration | EVD-2026-04-09-008 (4th call site), EVD-2026-10-05-001 (second consumer of `reviewedCount`), EVD-2026-10-01-003 (prop contract) | Designer does not grep all usages of a changed or removed symbol | Designer agent instruction: "for every removed/renamed/reused symbol, list all usages found by search" |
| T8 | Stale named-contract field lists (BP-09) | EVD-2026-04-14-003/004, EVD-2026-04-09-010 | `ARCHITECTURE_EXCEPTIONS.md` duplicates field lists that live in code | Smallest fix: exception records cite the serializer/type instead of copying field lists |
| T9 | Test-fixture coupling escapes (no rule) | EVD-2026-09-23-002, -003, EVD-2026-09-26-001, EVD-2026-10-05-004 (EssayCards, 4x), EVD-2026-09-24-003, EVD-2026-10-01-007 | Unscoped exact-count assertions; one global fixture world; per-test startup migration | EssayCards test convention (scoped or delta assertions) plus a test-spec template note; not a rule |
| T10 | Load-bearing content in scratchpad | EVD-2026-10-01-002 (S10, S12) | Designer workflow writes "Phase A" investigation to `/tmp` | Designer instruction: deferrals may reference sprint-folder artifacts only |

## Conflicts and Ambiguities
1. **Reviewer template vs R-PRO-BP-02.** Already logged on 2026-09-26 and still recurring in S12–S14. Unresolved.
2. **Reviewer and designer agents vs the rule registry.** They reference non-existent rule files (T5). *Not yet logged; should be logged in `agent_rule_conflicts.md`.*
3. **`sprint_implement_reviewer` agent and post-TESTS_PASSING implementation reviews vs R-PRO-BP-01 §1/§6.**
   - §1 says "No implementation review file", and the human gate is `/sprint-close` only.
   - Two implementation reviews exist (`00_Blueprint/Quality/EssayCards/Sprint10_…`, `Sprint12_…_Implementation_Review.md`). Both are APPROVED with zero blocking issues, so they had a cost and no catch.
   - The user's memory says not to add unrequested post-TESTS_PASSING review phases.
   - The agent file still exists and is referenced in orchestrator memory. *Should be logged.*
4. **R-PRO-BP-01 §7 vs practice.** The Notifications S01 log records an `[orchestrator-inline]` test-file fix. *Single incident; should be logged.*
5. **R-PRO-BP-01 §6 vs practice.** 13 of 33 sprints sit at `IMPLEMENTATION_IN_PROGRESS` or `TESTS_PASSING`, including committed work (e.g. EssayCards S15, commit `ea206ec`).
6. **R-OPS-BP-01 ambiguity.** Designers treat "surfaced as a risk" as satisfying the rule when the fix is in scope and cheap (S09 regex, EVD-2026-09-21-003; HabitTracker mechanism, EVD-2026-10-01-004). There are 2 instances, which is insufficient to justify a reword. Watch for a third.
7. **Overlap: R-CON-BP-10 and R-CON-AL-03.** Co-cited every time BP-10 blocks (S12, HabitTracker 15/17). Double citation is harmless. Merging is not justified by the cost.
8. **Overlap: R-CON-AL-02, R-CON-BP-11 and R-CON-AL-03.** AL-02 has no independent finding.
9. **Registry hygiene.**
   - R-PRO-BP-01 has no `STATUS` line.
   - R-CON-BP-05 is missing with no DEPRECATED stub, contrary to Rule_System §3.
   - No rule uses the `RULE_ID`/`TITLE` header fields that §3 requires.
   - The reviewer agent restates R-PRO-BP-01 §10 (UI scenario = Major blocking) without marking it non-authoritative (§4).
10. **Orchestrator vs §11.** `sprint_orchestrator.md` has no handling for `05_fast_path_plan.md` or `fast_path: true`. If invoked on a fast-path folder, it would see missing `10_*.json` and could mark the sprint BLOCKED.

## Escapes and Candidate New Checks
- **Port exposure (R-OPS-BP-02).** `02_Platform/CalendarConnector/compose.yml` binds `${CALENDAR_CONNECTOR_PORT:-8021}:8000` on all interfaces with no justification. The service has calendar write capability, and the binding predates the 2026-04-09 process window. `01_System/test/compose.test.yml` binds `0.0.0.0:9080:80` for `atlas-shell-test`, also without justification. By contrast, `Notifications` (`0.0.0.0:8020`, Tailscale comment) and `Atlas_Shell` (`:80`) are deliberate.
  - **Cheap check:** grep `compose*.yml` for `ports:` entries not prefixed `127.0.0.1:` and lacking a justification comment.
  - This is a check, not a new rule.
- **Test-fixture coupling (T9).** Six entries across 3 components. This is the largest recurring escape class, and no rule covers it.
  - **Cheap check:** an EssayCards convention that global aggregate tests assert deltas or fixture-scoped counts, never system-wide literals.
  - Promote to the test-spec template only if it recurs outside EssayCards. It already has, partially (StoryReader, HabitTracker fixture-state conflicts).
- **No new constitutional rules are warranted.** Of the 9 `candidate_response: rule` entries, none recurred, or they were resolved another way:
  - R-CON-BP-04 v0.5 handled the proxy shapes.
  - The `/sprint-close` CurrentArchitecture update handled staleness.
  - The design template's schema.sql promotion handled DDL drift.

## Decisions Needed From Human
1. Should R-PRO-BP-01 §3/§5 be changed so `APPROVED_WITH_CHANGES` with an empty Blocking table goes corrector → `DESIGN_APPROVED` without re-review, with re-review kept for `CHANGES_REQUIRED` (F1)?
2. Should R-CON-BP-09 gain the blocking-threshold sentence in F2 (behavior-affecting contradictions block; prose-only drift does not)?
3. Should `sprint_design_reviewer.md` be updated to use the R-PRO-BP-02 artifact structure, cite R-* rule IDs instead of non-existent files, add `CHANGES_REQUIRED`, and drop "Critical = violates architecture rules" (T4, T5)?
4. Should `UI_Data_Contract.md` / `platform_contracts` get a versioned, supported mechanism for a top-level sibling field and/or a list-valued column, with one shared serialization helper, so apps stop hand-rolling `response_model=None` workarounds (T3)?
5. Should the designer templates default `owns_persistent_state` to `false`/`schema_artifact` to `null`, add a `runtime_schema_path` field, and declare each signature, enum, and row shape once (T1, T2)?
6. Should root `CLAUDE.md`'s error-handling reference be corrected to `02_Platform/packages/platform_errorhandling/` (T6)?
7. Should the CalendarConnector and atlas-shell-test all-interface port bindings be reviewed and either restricted to 127.0.0.1 or given a recorded justification?
8. Should the orchestrator flag sprints left at `TESTS_PASSING`/`IMPLEMENTATION_IN_PROGRESS` (13 of 33 today) as unclosed, so `/sprint-close` stays the real gate?
9. Should `sprint_implement_reviewer` be retired, or marked out-of-pipeline, with post-TESTS_PASSING implementation reviews run only on explicit request?
10. Should EssayCards adopt the "no system-wide literal counts in tests" convention (T9)?
11. Should R-PRO-BP-02 allow `severity: minor` for implementer notes and execution issues, and should the evidence-file header be aligned with the rule (F3)?
12. Should the three unlogged conflicts (Conflicts 2, 3, 4) be entered in `agent_rule_conflicts.md`?
