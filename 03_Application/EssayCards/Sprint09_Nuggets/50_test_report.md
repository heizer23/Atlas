# Test Report — EssayCards — Sprint09_Nuggets

**Verdict:** TESTS_PASSING
**Date:** 2026-09-21
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| List nuggets returns a Dataset ordered by title | test_list_nuggets_returns_dataset_ordered_by_title | backend | PASS | — |
| List nuggets is valid when empty | test_list_nuggets_empty_is_valid | backend | PASS | — |
| Nugget detail includes body_markdown | test_nugget_detail_includes_body_markdown | backend | PASS | — |
| Nugget detail with an unknown id returns 404 | test_nugget_detail_not_found | backend | PASS | — |
| Nugget upsert creates, then updates by key without changing the id or key | test_nugget_upsert_creates_then_updates_by_key | backend | PASS | — |
| Nugget upsert rejects a missing or blank required field | test_nugget_upsert_rejects_missing_key_or_title | backend | PASS | — |
| Nugget upsert rejects a key violating the slug pattern | test_nugget_upsert_rejects_key_violating_slug_pattern | backend | PASS | — |
| Nugget flashcards lists linked cards with no scheduling fields | test_nugget_flashcards_lists_linked_cards_no_scheduling_fields | backend | PASS | — |
| Nugget flashcards for an unknown nugget id returns 404 | test_nugget_flashcards_not_found | backend | PASS | — |
| Nugget sections lists every section referencing a shared nugget | test_nugget_sections_lists_multiple_referencing_sections | backend | PASS | — |
| Nugget sections for an unknown nugget id returns 404 | test_nugget_sections_not_found | backend | PASS | — |
| Authoring package for an existing nugget includes its connected nuggets | test_authoring_package_existing_nugget_includes_connected_nuggets | backend | PASS | — |
| Authoring package with nugget_id omitted describes a new nugget | test_authoring_package_new_nugget_has_null_nugget_and_empty_connected | backend | PASS | — |
| Authoring package with an unresolvable context returns 404 | test_authoring_package_unresolvable_context_returns_404 | backend | PASS | — |
| Generate-flashcards package includes the nugget's existing flashcards | test_generate_flashcards_package_includes_existing_flashcards | backend | PASS | — |
| Generate-flashcards package with an unresolvable nugget or context returns 404 | test_generate_flashcards_package_unresolvable_context_returns_404 | backend | PASS | — |
| Markdown ingest resolves an existing nugget reference and resyncs section_nuggets | test_ingest_markdown_resolves_existing_nugget_reference | backend | PASS | — |
| Markdown ingest with an unresolved nugget reference writes nothing | test_ingest_markdown_unresolved_nugget_reference_rejected_writes_nothing | backend | PASS | — |
| Markdown reference resolves a mixed-case nugget_key | test_ingest_markdown_resolves_mixed_case_nugget_reference | backend | PASS | — |
| JSON ingest with an unresolved nugget reference returns VALIDATION_ERROR | test_ingest_json_unresolved_nugget_reference_returns_validation_error | backend | PASS | — |
| Re-ingesting a section that drops a nugget reference removes only the association | test_reingest_dropping_nugget_reference_removes_only_the_association | backend | PASS | — |
| Ingest round-trips main_spine_markdown | test_ingest_json_round_trips_main_spine_markdown | backend | PASS | — |
| Essay detail sections carry their referenced nuggets | test_essay_detail_sections_carry_referenced_nuggets | backend | PASS | — |
| Question overview rows carry their section's referenced nuggets | test_questions_rows_carry_section_nuggets | backend | PASS | — |
| Question overview rows carry each card's current nugget_id | test_questions_rows_carry_nugget_id | backend | PASS | — |
| Section export includes the main spine and focus-section nugget context | test_export_section_includes_main_spine_and_focus_section_nuggets | backend | PASS | — |
| Essay detail's main_spine_nuggets resolves a main-spine-only reference | test_essay_detail_main_spine_nuggets_resolves_main_spine_only_reference | backend | PASS | — |
| Essay export and section export carry main_spine_nuggets | test_essay_export_and_section_export_carry_main_spine_nuggets | backend | PASS | — |
| Due rows carry nugget_id | test_due_rows_carry_nugget_id | backend | PASS | — |
| Flashcard upsert with nugget_id omitted leaves an existing assignment untouched | test_upsert_omitted_nugget_id_leaves_existing_assignment_untouched | backend | PASS | — |
| Flashcard upsert with nugget_id explicit null clears an existing assignment | test_upsert_explicit_null_nugget_id_clears_assignment | backend | PASS | — |
| Flashcard upsert with a valid nugget_id sets the assignment | test_upsert_valid_nugget_id_sets_assignment | backend | PASS | — |
| Flashcard upsert with an unresolvable nugget_id is rejected without side effects | test_upsert_unresolvable_nugget_id_rejected_assignment_unchanged | backend | PASS | — |
| Single-question export includes nugget_id | test_export_question_includes_nugget_id | backend | PASS | — |
| Exploration package for a nugget-linked card uses nugget context | test_exploration_package_nugget_linked_card_uses_nugget_context | backend | PASS | — |
| Exploration package for a legacy card is unchanged | test_exploration_package_legacy_card_unchanged | backend | PASS | — |
| Examination package includes nugget_versions per section | test_examination_package_includes_nugget_versions_per_section | backend | PASS | — |
| Examination import stores nugget_versions verbatim | test_examination_import_stores_nugget_versions_verbatim | backend | PASS | — |
| Examination import without nugget_versions stores null | test_examination_import_without_nugget_versions_stores_null | backend | PASS | — |
| nugget_freshness_flags with no recorded versions skips the check | test_nugget_freshness_flags_none_recorded_skips_check | backend | PASS | — |
| nugget_freshness_flags flags changed and missing keys, not matching ones | test_nugget_freshness_flags_detects_changed_and_missing_keys | backend | PASS | — |
| [UI] Clicking a nugget reference opens the nugget without leaving the reader | (none) | UI | UNTESTED | No `tests/ui/` directory or Playwright execution infrastructure exists for EssayCards (confirmed absent as of Sprint03_Images, and explicitly noted as such in this sprint's `10_architecture.json` §risks — "if no tests/ui/ Playwright suite exists yet for this component..., record the [UI] scenario as untested (not passing)"). Recorded as untested, not a failure; same convention as Sprint03_Images's `50_test_report.md`. |
| [UI — manual] Flashcard review source navigation opens the nugget without ending the session | (none) | manual | MANUAL | Requires human verification; test spec itself notes this was verified manually this sprint. |
| [UI — manual] Editing a question can assign or unlink its nugget | (none) | manual | MANUAL | Requires human verification; test spec itself notes this was verified manually this sprint. |

Backend/API totals: 41 scenarios — 41 PASS, 0 FAIL, 0 MISSING.
UI totals: 1 `[UI]` scenario UNTESTED (infra gap, not a failure), 2 `[UI — manual]` scenarios MANUAL (not a failure).

Full suite: 221 collected, 220 passed, 1 failed. The single failure is a pre-existing,
unrelated fixture issue in `test_examinations.py` (see Failure Analysis) — it does not
affect the Sprint09 verdict.

## Test output

```
tests/test_nuggets.py::test_list_nuggets_returns_dataset_ordered_by_title PASSED
tests/test_nuggets.py::test_list_nuggets_empty_is_valid PASSED
tests/test_nuggets.py::test_nugget_detail_includes_body_markdown PASSED
tests/test_nuggets.py::test_nugget_detail_not_found PASSED
tests/test_nuggets.py::test_nugget_upsert_creates_then_updates_by_key PASSED
tests/test_nuggets.py::test_nugget_upsert_rejects_missing_key_or_title PASSED
tests/test_nuggets.py::test_nugget_upsert_rejects_key_violating_slug_pattern PASSED
tests/test_nuggets.py::test_nugget_flashcards_lists_linked_cards_no_scheduling_fields PASSED
tests/test_nuggets.py::test_nugget_flashcards_not_found PASSED
tests/test_nuggets.py::test_nugget_sections_lists_multiple_referencing_sections PASSED
tests/test_nuggets.py::test_nugget_sections_not_found PASSED
tests/test_nuggets.py::test_authoring_package_existing_nugget_includes_connected_nuggets PASSED
tests/test_nuggets.py::test_authoring_package_new_nugget_has_null_nugget_and_empty_connected PASSED
tests/test_nuggets.py::test_authoring_package_unresolvable_context_returns_404 PASSED
tests/test_nuggets.py::test_generate_flashcards_package_includes_existing_flashcards PASSED
tests/test_nuggets.py::test_generate_flashcards_package_unresolvable_context_returns_404 PASSED
tests/test_ingest.py::test_extract_nugget_keys_strips_fences_and_inline_code PASSED
tests/test_ingest.py::test_extract_nugget_keys_captures_mixed_case_key PASSED
tests/test_ingest.py::test_ingest_markdown_resolves_existing_nugget_reference PASSED
tests/test_ingest.py::test_ingest_markdown_unresolved_nugget_reference_rejected_writes_nothing PASSED
tests/test_ingest.py::test_ingest_markdown_resolves_mixed_case_nugget_reference PASSED
tests/test_ingest.py::test_reingest_dropping_nugget_reference_removes_only_the_association PASSED
tests/test_ingest_endpoint.py::test_ingest_json_round_trips_main_spine_markdown PASSED
tests/test_ingest_endpoint.py::test_ingest_json_unresolved_nugget_reference_returns_validation_error PASSED
tests/test_ingest_endpoint.py::test_ingest_json_resolves_existing_nugget_reference PASSED
tests/test_essays.py::test_essay_detail_sections_carry_referenced_nuggets PASSED
tests/test_essays.py::test_questions_rows_carry_section_nuggets PASSED
tests/test_essays.py::test_questions_rows_carry_nugget_id PASSED
tests/test_essays.py::test_export_section_includes_main_spine_and_focus_section_nuggets PASSED
tests/test_essays.py::test_essay_detail_main_spine_nuggets_resolves_main_spine_only_reference PASSED
tests/test_essays.py::test_essay_export_and_section_export_carry_main_spine_nuggets PASSED
tests/test_flashcards.py::test_due_rows_carry_nugget_id PASSED
tests/test_flashcards.py::test_upsert_omitted_nugget_id_leaves_existing_assignment_untouched PASSED
tests/test_flashcards.py::test_upsert_explicit_null_nugget_id_clears_assignment PASSED
tests/test_flashcards.py::test_upsert_valid_nugget_id_sets_assignment PASSED
tests/test_flashcards.py::test_upsert_unresolvable_nugget_id_rejected_assignment_unchanged PASSED
tests/test_flashcards.py::test_export_question_includes_nugget_id PASSED
tests/test_exploration.py::test_exploration_package_nugget_linked_card_uses_nugget_context PASSED
tests/test_exploration.py::test_exploration_package_legacy_card_unchanged PASSED
tests/test_examinations.py::test_examination_package_includes_nugget_versions_per_section PASSED
tests/test_examinations.py::test_examination_import_stores_nugget_versions_verbatim PASSED
tests/test_examinations.py::test_examination_import_without_nugget_versions_stores_null PASSED
tests/test_examinations.py::test_nugget_freshness_flags_none_recorded_skips_check PASSED
tests/test_examinations.py::test_nugget_freshness_flags_detects_changed_and_missing_keys PASSED

=================================== FAILURES ===================================
__________ test_import_stores_new_result_without_overwriting_history ___________

    def test_import_stores_new_result_without_overwriting_history(client, db_conn):
        ...
        history = client.get(_history_url(SECTION_ORIGINS_ID))
        assert history.status_code == 200
        rows = history.json()["rows"]
        assert len(rows) == 3
>       assert rows[0]["score"] == 5  # most recent first
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       assert 4 == 5

tests/test_examinations.py:112: AssertionError

=========================== short test summary info ============================
FAILED tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history
================== 1 failed, 220 passed, 5 warnings in 26.72s ==================
```

(220 nugget-unrelated PASSED lines omitted above for brevity — full run: 221 collected,
220 passed, 1 failed, across test_essays.py, test_examinations.py, test_exploration.py,
test_flashcards.py, test_images.py, test_ingest.py, test_ingest_endpoint.py,
test_nuggets.py, test_questions.py, test_scheduling.py, test_shell_proxy.py.)

## Failure Analysis

All 41 backend/API scenarios in `10_test_spec.md` pass. The 1 `[UI]` scenario is
untested due to a documented, pre-existing infrastructure gap (no Playwright suite for
EssayCards), not a defect in this sprint's implementation — `10_architecture.json`
explicitly anticipated and accepted this for Sprint09 (§risks). The 2
`[UI — manual]` scenarios are marked MANUAL per the test spec itself, which states they
were "verified manually this sprint."

**1. Pre-existing unrelated failure — `test_import_stores_new_result_without_overwriting_history`**

Confirmed to be exactly the same failure as `EVD-2026-08-30-006`
(`00_Blueprint/Quality/agent_rule_evidence.md`), first observed 2026-08-30 during
Sprint04_ImageUpload — same test, same assertion (`assert 4 == 5  # most recent first`
at `tests/test_examinations.py:112`), same root cause: `tests/fixtures.sql`'s
`se-origins-2` row is inserted with `examined_at = now() - interval '2 days'`, while the
test payload hardcodes `examined_at: '2026-08-28T14:30:00Z'`. On today's date
(2026-09-21), the fixture's relative timestamp resolves to a value newer than the
hardcoded payload, so the fixture row sorts first instead of the newly-imported one. No
nugget-related code path (`backend/routers/nuggets.py`, `backend/ingest.py`'s nugget
resolution, `flashcards.nugget_id`, `nugget_versions`) touches this test or its fixture
rows — it exercises only `section_examinations` insert/history-ordering behavior that
predates and is untouched by this sprint. Not blocking Sprint09's verdict.

**2. `[UI]` scenario untested — infrastructure gap, not a Sprint09 defect**

`10_architecture.json` §risks (ui_implementer deferral note) states: "if no tests/ui/
Playwright suite exists yet for this component (confirmed absent as of Sprint03_Images),
record the [UI] scenario as untested (not passing) per R-PRO-BP-01 §10." This is
consistent with every prior EssayCards sprint's test reports (e.g. Sprint03_Images);
EssayCards has never had Playwright UI execution infrastructure. This is a known,
accepted, app-wide gap predating Sprint09, not something this sprint's design or
implementation introduced or was expected to fix.

## Required Action

Proceed to `/sprint-close`; no fixes required for Sprint09 — the one full-suite failure
is the pre-existing, previously-documented, unrelated `test_examinations.py` fixture
issue (`EVD-2026-08-30-006`), and the `[UI]` scenario's untested status reflects a
long-standing, explicitly-accepted app-wide infrastructure gap, not a Sprint09 defect.
