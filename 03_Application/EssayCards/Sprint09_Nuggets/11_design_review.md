# Design Review — EssayCards (Sprint09_Nuggets)

## Verdict
- Status: CHANGES_REQUIRED
- Summary: The design is thorough, internally consistent, and faithfully implements all seven decisions closed in `00_draft.md`. Two constitutional Application-layer contract gaps (main-spine-only nugget title resolution; missing UI half of the `nugget_id` round trip) must be resolved before implementation, plus one Major usability defect (key case-sensitivity mismatch) that is currently only documented, not fixed. The process deviation on seeding `10_architecture.json`/`10_scaffolding.json` from current reality instead of the stale `00_architecture/` baseline is judged correct and is not a blocking issue.

## Confirmed Problems

1. **`nugget_key` case-sensitivity mismatch is a real, avoidable usability trap, not just a documentation risk**
   - Severity: Major
   - Location: `10_architecture.json §contracts.invariants` (item 4) and `§risks`; `00_draft.md §1`/`§2`; `10_schema.sql` (nuggets table comment)
   - Why it is a problem: `nugget_key` validation (`SLUG_LIKE_RE = ^[a-zA-Z0-9_-]+$`) permits mixed case and the draft explicitly states nuggets get "no auto-slugify, no auto-lowercasing" — mixed case is a first-class supported form, mirroring `slug`/`anchor_slug`/`card_key`. But `extract_nugget_keys`'s reference regex (`\[\[nugget:([a-z0-9_-]+)\]\]`) is lowercase-only, and this same character class also governs `connected_nuggets` resolution in `GET /nuggets/authoring-package` (a nugget's own `body_markdown` referencing another nugget). Any nugget authored with an uppercase character in its key can be created but can *never* be referenced from any Markdown anywhere in the app — a permanent, silent landmine for authors, not a corner case.
   - Impact: A user who names a nugget key with a capital letter (a natural authoring mistake given the permissive validation) gets a nugget that is functionally unreferenceable; the failure only surfaces later as an "unresolved key" validation error at ingest time, with no indication that the root cause is casing. No fixture or test scenario in `10_test_spec.md` exercises an uppercase key, so this would ship unverified.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — two regexes doing related jobs (author-time key validation vs. reference-time key extraction) were specified independently without checking character-class parity.
   - Note: this was surfaced transparently in `risks` per R-OPS-BP-01 rather than hidden, which is correct practice — but transparency about a cheap-to-fix defect is not a substitute for fixing it. Required change: make `extract_nugget_keys`'s key character class match `SLUG_LIKE_RE` (`[a-zA-Z0-9_-]+`) so any valid `nugget_key` is always referenceable.

## Recommended Improvements

1. **Confirm the `10_architecture.json`/`10_scaffolding.json` seeding deviation is closed out at `/sprint-close`**
   - Location: `10_architecture.json §risks` (final entry, "PROCESS DEVIATION")
   - Improvement: The decision to write `10_architecture.json`/`10_scaffolding.json` as full, accurate current-plus-this-sprint descriptions — rather than a fabricated delta against the four-sprints-stale `00_architecture/` seed — is the right call: it better satisfies R-CON-BP-01 (machine-legible, accurate artifacts) and R-CON-BP-09 (cross-artifact truth consistency) than perpetuating a known-stale baseline would. `Sprint03_Images` already flagged this exact staleness and deferred the fix to `/sprint-close`, and it was not fixed for four sprints. Since this sprint's own artifacts are self-sufficient regardless of whether `00_architecture/` is ever regenerated, this is not a blocking condition — but given the repeat-deferral pattern, the corrector/implementer should treat the `/sprint-close` regeneration commitment as a real task this time, not another deferred note.
   - Why: Prevents a third consecutive sprint from re-flagging the same unresolved staleness (`atlas_dev_ref.md`'s EssayCards section is confirmed still generated from the pre-Sprint03 baseline, corroborating the staleness claim).

## Scaffold-Only Observations

1. **`src/ShellEntry.tsx` continues to grow as a single ~2960+ line file**
   - Location: `10_scaffolding.json` (ShellEntry.tsx entry, `role`); `10_architecture.json §risks`/`§deferred_decisions`
   - Observation: This sprint adds a remark plugin, `NuggetLink`, a recursive-stack overlay component, two new export/import view pairs, and multiple type extensions, all to the same file. Already self-flagged as a risk and explicitly deferred (consistent with every prior sprint's convention).
   - Impact on implementation: No functional risk this sprint, but continues to raise the cost of future changes to this file; worth a standalone structural sprint at some point.

## Hard Rule Violations

1. **Invariant Realizability — main-spine-only nugget references cannot be titled client-side**
   - Rule Source: `.claude/rules/R-CON-AL.md` (R-CON-AL-03 — Invariant Realizability)
   - Location: `10_architecture.json §contracts.invariants` (item: "titleMap for a section's rendering..."); `00_draft.md §2`/`§3`
   - Violation: Ingest-time validation (`upsert_document`'s new first step) resolves `[[nugget:key]]` references across **both** `main_spine_markdown` and every section's `body_markdown` — so a nugget referenced only in the main spine (never in any section) is a valid, accepted reference. But the frontend `titleMap` for rendering `main_spine_markdown` is specified as "the client-side union of every section's `nuggets` field" — and `essaycards.section_nuggets` (the only source of a nugget's title alongside its key) is resynced **only** from each section's own `body_markdown` (internal_flow step 4), never from `main_spine_markdown`. A nugget validly referenced only in the main spine therefore has no path to a title in the essay-detail response, so `remarkNuggetRefs` cannot find it in `titleMap` and will render it via the `nugget-missing:<key>` branch — styled as a **broken reference** even though the nugget genuinely exists and was validly accepted at ingest. The invariant text itself ("main_spine_markdown may reference a nugget introduced in any section") is an unstated, unenforced assumption — R-CON-AL-03 explicitly disallows an invariant depending on such a hidden default. No scenario in `10_test_spec.md` exercises this case, and the §10 demonstration content happens to reference every nugget from a section too, so this gap is unexercised anywhere in the design.
   - Required Fix: Either (a) enforce at ingest time that every key referenced in `main_spine_markdown` must also appear in at least one of the essay's own sections (rejecting otherwise), making the stated assumption a real, validated invariant; or (b) add a dedicated `main_spine_nuggets: [{nugget_key, title}]` field (mirroring the per-section `nuggets` field) to the essay-detail/export responses so the title map is always fully derivable regardless of section co-reference. Update `00_draft.md §2`/`§3` and the corresponding architecture/scaffolding sections to reflect whichever fix is chosen, and add a test-spec scenario covering it.

2. **Update Round-Trip Completeness — `nugget_id`'s cleared/omitted UI states are undefined**
   - Rule Source: `.claude/rules/R-CON-AL.md` (R-CON-AL-05 — Update Round-Trip Completeness)
   - Location: `10_architecture.json §contracts.invariants` (`POST /flashcards/upsert`'s `nugget_id` tri-state item); `10_scaffolding.json` (`ui_implementer` deferrals — no `nugget_id` field added to `QuestionOverviewView`'s existing card-edit form)
   - Violation: The backend half of the round trip (omit/null/value) is fully and correctly specified (R-CON-AL-04 is satisfied). But R-CON-AL-05 requires all four aspects — UI representation of empty/cleared state, frontend payload, backend interpretation, persisted state — for every editable field, and none of the scaffolded UI work defines a UI representation for the cleared state or a UI-triggered payload that sends `nugget_id: null`. The only client caller that ever sets `nugget_id` this sprint is the one-way "Generate flashcards from a nugget" import (create-time only, always a value, never null); no UI path exists to assign a nugget to a pre-existing legacy card, or to unlink one from a nugget-linked card, even though the backend was built specifically to support exactly that. This gap is also not listed among `00_draft.md`'s or `10_architecture.json`'s explicit non-goals (contrast with `nugget_freshness_flags`, whose lack of UI surfacing *is* explicitly non-goaled) — so it reads as an unnoticed omission rather than a deliberate scope decision.
   - Required Fix: Either add a minimal UI affordance (e.g., a `nugget_id` selector/"Unlink nugget" control in `QuestionOverviewView`'s existing edit form, or from the `NuggetPanel`) that can send omit, explicit `null`, and a chosen value — satisfying all four R-CON-AL-05 aspects — or explicitly add "no UI to manually assign/unlink `nugget_id` on an existing card this sprint" to `00_draft.md §11`/`10_architecture.json`'s `non_goals`, so the omission is a stated decision rather than a silent gap.

## Open Uncertainties

1. **Whether the `/sprint-close` regeneration of `00_architecture/` will actually happen this time**
   - Location: `10_architecture.json §risks` (PROCESS DEVIATION entry)
   - Uncertainty: This is the second sprint in a row (after `Sprint03_Images`) to flag the same `00_architecture/` staleness and defer the fix to `/sprint-close`. Nothing in the current pipeline mechanically enforces that the regeneration actually happens.
   - Why it matters: If deferred again, `00_architecture/` and `atlas_dev_ref.md` (confirmed still describing pre-Sprint03 EssayCards) will drift even further from reality, compounding the same problem for the next sprint's designer.
   - Suggested owner: Architecture (via whoever runs `/sprint-close` for this sprint).

## Minimal Change Set

1. Fix the character-class mismatch between `SLUG_LIKE_RE` and `extract_nugget_keys`'s reference regex so every valid `nugget_key` is referenceable (Confirmed Problem 1).
2. Resolve the main-spine-only nugget title-resolution gap — either enforce section co-reference at ingest or add a `main_spine_nuggets` field to essay-detail/export responses — and add a covering test-spec scenario (Hard Rule Violation 1).
3. Either add a minimal UI path to set/clear `nugget_id` on an existing card, or explicitly non-goal it in `00_draft.md`/`10_architecture.json` (Hard Rule Violation 2).

## Approval Condition
- All three Minimal Change Set items are reflected in a revised `10_architecture.json`/`10_scaffolding.json` (and `00_draft.md` where the underlying decision changes), each with a corresponding `10_test_spec.md` scenario where the fix affects observable behavior.
