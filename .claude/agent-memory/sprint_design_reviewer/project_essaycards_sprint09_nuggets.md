# EssayCards Sprint09_Nuggets — design review notes

## Scoped re-review pattern (12_design_corrections.md → 13_design_review.md)
When asked to do a scoped re-review of a corrections round (not a from-scratch pass):
- Read `12_design_corrections.md` fully first — it names exactly which artifact sections it touched per finding.
- Only re-read those specific sections of `10_architecture.json`/`10_scaffolding.json`/`10_test_spec.md` (grep/offset-read, not full re-read), cross-checked against the corrector's claims.
- Explicitly verify any "either/or" judgment call the corrector made against the *exact* Required Fix wording in the prior `11_design_review.md` — confirm the chosen option is one of the ones actually offered, not a third invented approach, and check it doesn't conflict with `forbidden`/`non_goals` elsewhere in the architecture.
- This sprint's corrector (`design_corrector` for EssayCards Sprint09) did this well: all three findings (regex character-class parity, `main_spine_nuggets` additive field, nugget `<select>` UI closing R-CON-AL-05) were faithfully and completely closed, with matching test-spec scenarios including the required `[UI — manual]` one. Verdict: APPROVED on first re-review, no evidence entries needed (no new Major/Critical findings).

## Recurring EssayCards pattern: parallel-regex character-class drift
EssayCards has now had one instance of two regexes governing the same identifier (`SLUG_LIKE_RE` for authoring vs. an extraction/reference regex) drifting in character class (Sprint09, nugget_key vs. `[[nugget:key]]`). Worth checking for this same shape (validation regex vs. a separately-maintained reference/extraction regex) in future EssayCards sprints touching author-assigned identifiers (slug, anchor_slug, card_key, nugget_key).

## Recurring EssayCards pattern: backend tri-state without UI half
EssayCards backend consistently implements R-CON-AL-04 (omit/null/value) correctly on `POST /flashcards/upsert`-style endpoints, but new fields added to that tri-state don't automatically get a UI control in the same sprint — this has now been the actual root cause of one Hard Rule Violation (Sprint09, `nugget_id`). When a sprint adds a new tri-state field to an existing upsert endpoint, check specifically whether any UI form is wired to send the field's cleared/null state, not just whether the backend handles it.

## Artifact hygiene note (non-blocking, recurring)
When a design-corrector fixes a bug in `10_architecture.json`/`10_scaffolding.json` that was originally illustrated with example code/regex text in `00_draft.md`, the draft's illustrative text is frequently left stale (correctly, per R-PRO-BP-01's "draft.md only when the review explicitly requires it" mandate) but this creates a real R-CON-BP-09 cross-artifact inconsistency between the source draft and the now-authoritative design artifacts. Treat this as a Minor/Recommended-Improvement, not a blocker, as long as: (a) the correction record transparently discloses it, and (b) no deferral/test-spec relies on the stale draft text. Don't let it block approval, but do flag it every time it recurs.
