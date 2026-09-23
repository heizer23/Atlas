# Design Review — EssayCards (Sprint09_Nuggets)

## Verdict
- Status: APPROVED
- Summary: This is a scoped re-review of `12_design_corrections.md` against `11_design_review.md`'s three findings. All three are faithfully closed: the `extract_nugget_keys` character class now matches `SLUG_LIKE_RE` exactly and the corresponding risk entry was removed; `main_spine_nuggets` is correctly wired into all three named endpoints with the frontend `titleMap` union described accurately; and `QuestionOverviewView`'s new nugget `<select>` genuinely closes the R-CON-AL-05 round trip (Save always sends `card.nugget_id` explicitly). Both either/or judgment calls the corrector flagged are faithful implementations of one of the two options `11_design_review.md` actually offered, not a third unreviewed approach, and neither conflicts with the rest of the design. `10_test_spec.md` exercises all three fixes, including the required `[UI — manual]` scenario for finding 3.

## Confirmed Problems
None identified.

## Recommended Improvements

1. **`00_draft.md §2` still quotes the pre-correction, now-incorrect extraction regex**
   - Location: `00_draft.md` line ~107 (`\[\[nugget:([a-z0-9_-]+)\]\]`) vs. `10_architecture.json §contracts.invariants` item 4 and `internal_flow` step 1 (`[a-zA-Z0-9_-]+`)
   - Improvement: Update `00_draft.md §2`'s illustrative regex to `[a-zA-Z0-9_-]+` so the source definition no longer contradicts the corrected, authoritative artifacts (R-CON-BP-09 — cross-artifact truth consistency).
   - Why: `11_design_review.md`'s Required Fix for Confirmed Problem 1 named only the code-level character-class correction and did not list `00_draft.md` among the files to update, so the corrector's decision to leave it untouched was a defensible reading of its mandate, and it disclosed the gap transparently in its Notes. This is non-blocking because `10_architecture.json` is unambiguously the authoritative statement (R-CON-BP-01) and no deferral or test scenario relies on the stale draft text — but a future reader of `00_draft.md` alone would see a regex that no longer matches what was built.

## Scaffold-Only Observations
None identified.

## Hard Rule Violations
None identified.

## Open Uncertainties
None identified.

## Minimal Change Set
None identified.

## Approval Condition
- None — approved as-is.

---

## Verification Detail (supporting the verdict above)

1. **Character-class fix (Confirmed Problem 1).** `10_architecture.json §contracts.invariants` item 4 and `internal_flow` step 1 both state the extraction regex is now `\[\[nugget:([a-zA-Z0-9_-]+)\]\]`, matching `SLUG_LIKE_RE = ^[a-zA-Z0-9_-]+$` exactly. `10_scaffolding.json`'s `backend/ingest.py` entry for `extract_nugget_keys` states the same. The now-resolved risk entry describing the mismatch was confirmed removed from `10_architecture.json §risks` (6 entries remain, none referencing character-class parity).

2. **`main_spine_nuggets` wiring (Hard Rule Violation 1).** `10_architecture.json §contracts.provides` and `interfaces.exposed_surfaces` both list `main_spine_nuggets: [{nugget_key, title}]` on `GET /essays/{essay_id}`, `GET /essays/{essay_id}/export`, and `GET /essays/{essay_id}/sections/{section_id}/export`. `internal_flow` step 20 (`_main_spine_nuggets`) and the `application_implementer` deferral both name all three call sites (`get_essay`, `export_essay`, `export_section`). `10_scaffolding.json`'s `essays.py` entry lists the same helper reused by the same three functions. The `titleMap` invariant (`§contracts.invariants`, "titleMap for a section's rendering...") explicitly states the main-spine titleMap is "the client-side union of every section's `nuggets` field AND the essay's own `main_spine_nuggets` field" — matching the `ui_implementer` deferral's identical wording.

3. **Nugget `<select>` UI (Hard Rule Violation 2).** `10_architecture.json §contracts.invariants` (the `QuestionOverviewView` edit-form invariant) states Save "ALWAYS sends `card.nugget_id` explicitly — the selected nugget's id, or JSON null for 'No nugget' — never omitted," reusing the same "always explicit, never defaulted" precedent already established for the form's `level` field. This is a genuine closure, not a partial fix: all four R-CON-AL-05 aspects are addressed (UI representation of cleared state = the "No nugget" option; payload = explicit id or null; backend interpretation and persisted state were already correct). `10_test_spec.md`'s `[UI — manual] Editing a question can assign or unlink its nugget` scenario exercises both directions (assign, then clear).

4. **Either/or fidelity.** `11_design_review.md` Hard Rule Violation 1's Required Fix offered (a) ingest-time enforcement of section co-reference or (b) an additive `main_spine_nuggets` field; the corrector chose (b), matching its own claim. Hard Rule Violation 2's Required Fix offered (a) a minimal UI affordance or (b) an explicit non-goal; the corrector chose (a), matching its own claim. Neither choice conflicts with `non_goals`, `forbidden`, or any other invariant — the additive field adds no new ingest-time validation (confirmed against `forbidden`'s existing list, which was not extended), and the UI affordance reuses the existing edit form and `POST /flashcards/upsert` endpoint with no new endpoint introduced.

5. **Test coverage.** `10_test_spec.md` adds: "Markdown reference resolves a mixed-case nugget_key" (finding 1); "Essay detail's main_spine_nuggets resolves a main-spine-only reference" and "Essay export and section export carry main_spine_nuggets" (finding 2, all three endpoints); "Question overview rows carry each card's current nugget_id" (HTTP half of finding 3) and "`[UI — manual]` Editing a question can assign or unlink its nugget" (UI half of finding 3). `10_scaffolding.json` lists `ShellEntry.tsx` under `files` with `change: changed`; the `[UI]` and `[UI — manual]` scenario requirement was already satisfied pre-correction and remains satisfied.
