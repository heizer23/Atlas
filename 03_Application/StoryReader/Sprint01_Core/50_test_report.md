# Test Report — StoryReader — Sprint01_Core

**Verdict:** TESTS_PASSING
**Date:** 2026-09-24
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Story list — empty state | test_story_list_empty_state | backend | PASS | — |
| Story list — marked-passage count reflects the latest version only | test_story_list_marked_passage_count_reflects_latest_version_only | backend | PASS | — |
| Story detail — version list for the switcher | test_story_detail_version_list_for_switcher | backend | PASS | — |
| Story detail — unknown story | test_story_detail_unknown_story | backend | PASS | — |
| Ingestion — first publish creates version 1 | test_ingest_first_publish_creates_version_1 | backend | PASS | — |
| Ingestion — unchanged content is a no-op | test_ingest_unchanged_content_is_noop | backend | PASS | — |
| Ingestion — changed content appends a new version | test_ingest_changed_content_appends_new_version | backend | PASS | — |
| Ingestion — slug/filename mismatch is rejected | test_ingest_slug_filename_mismatch_rejected | backend | PASS | — |
| Ingestion — re-ingestion can change title without a new version | test_ingest_title_change_without_new_version | backend | PASS | — |
| Paragraph split — blank-line-separated paragraphs | test_blank_line_separated_paragraphs | backend | PASS | — |
| Paragraph split — a multi-line list is one paragraph | test_multiline_unordered_list_is_one_paragraph | backend | PASS | — |
| Paragraph split — a fenced code block is one paragraph with fences dropped | test_fenced_code_block_is_one_paragraph_with_fences_dropped | backend | PASS | — |
| Version content — default resolves to latest | test_version_content_default_resolves_to_latest | backend | PASS | — |
| Version content — explicit old version remains readable | test_version_content_explicit_old_version_remains_readable | backend | PASS | — |
| Version content — unknown version number | test_version_content_unknown_version_number | backend | PASS | — |
| Version content — malformed version segment | test_version_content_malformed_version_segment | backend | PASS | — |
| Annotations list — reading order | test_annotations_list_reading_order | backend | PASS | — |
| Annotations list — no implicit latest | test_annotations_list_no_implicit_latest | backend | PASS | — |
| Create annotation — new span | test_create_annotation_new_span | backend | PASS | — |
| Create annotation — reaction changed at the same exact span | test_create_annotation_reaction_changed_at_same_exact_span | backend | PASS | — |
| Create annotation — selected_text must match the true substring | test_create_annotation_selected_text_must_match_true_substring | backend | PASS | — |
| Create annotation — invalid reaction rejected | test_create_annotation_invalid_reaction_rejected | backend | PASS | — |
| Create annotation — char_end not after char_start | test_create_annotation_char_end_not_after_char_start | backend | PASS | — |
| Create annotation — unknown story or version | test_create_annotation_unknown_story_or_version | backend | PASS | — |
| Delete annotation — toggle-off removes the row | test_delete_annotation_toggle_off_removes_the_row | backend | PASS | — |
| Delete annotation — unknown id | test_delete_annotation_unknown_id | backend | PASS | — |
| Publishing a new version never touches existing annotations | test_publishing_new_version_never_touches_existing_annotations | backend | PASS | — |
| Export — self-contained JSON for Codex | test_export_self_contained_json_for_codex | backend | PASS | — |
| Export — empty version is valid, not an error | test_export_empty_version_is_valid_not_an_error | backend | PASS | — |
| Export — unknown version | test_export_unknown_version | backend | PASS | — |
| [UI — manual] Tap-to-react saves without confirmation | — | manual | MANUAL | requires human verification; no execution infra per designer |
| [UI — manual] Tapping the active reaction again removes it | — | manual | MANUAL | requires human verification; no execution infra per designer |
| [UI — manual] Feedback list row jumps back to its passage | — | manual | MANUAL | requires human verification; no execution infra per designer |

Additional passing tests beyond the 1:1 scenario mapping (extra edge-case coverage, not required by spec but present): `test_multiline_blockquote_is_one_paragraph`, `test_nested_blockquote_strips_repeated_markers`, `test_no_blank_line_document_is_exactly_one_paragraph`, `test_ordered_list_is_one_paragraph`, `test_heading_marker_stripped`, `test_inline_emphasis_and_link_markup_stripped`, `test_empty_document_returns_no_paragraphs`, `test_export_empty_version_zero_annotations`, `test_storyreader_proxy_returns_json`, `test_shell_serves_app_at_basepath` — all PASS.

`tests/ui/` exists but is empty (no `.spec.ts` files), consistent with all `[UI]` scenarios in `10_test_spec.md` being labeled `[UI — manual]` by the designer. Playwright execution was correctly skipped.

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.12
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 40 items

tests/test_ingest.py::test_ingest_first_publish_creates_version_1 PASSED [  2%]
tests/test_ingest.py::test_ingest_unchanged_content_is_noop PASSED       [  5%]
tests/test_ingest.py::test_ingest_changed_content_appends_new_version PASSED [  7%]
tests/test_ingest.py::test_ingest_slug_filename_mismatch_rejected PASSED [ 10%]
tests/test_ingest.py::test_ingest_title_change_without_new_version PASSED [ 12%]
tests/test_ingest.py::test_publishing_new_version_never_touches_existing_annotations PASSED [ 15%]
tests/test_paragraphs.py::test_blank_line_separated_paragraphs PASSED    [ 17%]
tests/test_paragraphs.py::test_multiline_unordered_list_is_one_paragraph PASSED [ 20%]
tests/test_paragraphs.py::test_multiline_blockquote_is_one_paragraph PASSED [ 22%]
tests/test_paragraphs.py::test_nested_blockquote_strips_repeated_markers PASSED [ 25%]
tests/test_paragraphs.py::test_fenced_code_block_is_one_paragraph_with_fences_dropped PASSED [ 27%]
tests/test_paragraphs.py::test_no_blank_line_document_is_exactly_one_paragraph PASSED [ 30%]
tests/test_paragraphs.py::test_ordered_list_is_one_paragraph PASSED      [ 32%]
tests/test_paragraphs.py::test_heading_marker_stripped PASSED            [ 35%]
tests/test_paragraphs.py::test_inline_emphasis_and_link_markup_stripped PASSED [ 37%]
tests/test_paragraphs.py::test_empty_document_returns_no_paragraphs PASSED [ 40%]
tests/test_shell_proxy.py::test_storyreader_proxy_returns_json PASSED    [ 42%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [ 45%]
tests/test_stories.py::test_story_list_empty_state PASSED                [ 47%]
tests/test_stories.py::test_story_list_marked_passage_count_reflects_latest_version_only PASSED [ 50%]
tests/test_stories.py::test_story_detail_version_list_for_switcher PASSED [ 52%]
tests/test_stories.py::test_story_detail_unknown_story PASSED            [ 55%]
tests/test_stories.py::test_version_content_default_resolves_to_latest PASSED [ 57%]
tests/test_stories.py::test_version_content_explicit_old_version_remains_readable PASSED [ 60%]
tests/test_stories.py::test_version_content_unknown_version_number PASSED [ 62%]
tests/test_stories.py::test_version_content_malformed_version_segment PASSED [ 65%]
tests/test_stories.py::test_annotations_list_reading_order PASSED        [ 67%]
tests/test_stories.py::test_annotations_list_no_implicit_latest PASSED   [ 70%]
tests/test_stories.py::test_create_annotation_new_span PASSED            [ 72%]
tests/test_stories.py::test_create_annotation_reaction_changed_at_same_exact_span PASSED [ 75%]
tests/test_stories.py::test_create_annotation_selected_text_must_match_true_substring PASSED [ 77%]
tests/test_stories.py::test_create_annotation_invalid_reaction_rejected PASSED [ 80%]
tests/test_stories.py::test_create_annotation_char_end_not_after_char_start PASSED [ 82%]
tests/test_stories.py::test_create_annotation_unknown_story_or_version PASSED [ 85%]
tests/test_stories.py::test_delete_annotation_toggle_off_removes_the_row PASSED [ 87%]
tests/test_stories.py::test_delete_annotation_unknown_id PASSED          [ 90%]
tests/test_stories.py::test_export_self_contained_json_for_codex PASSED  [ 92%]
tests/test_stories.py::test_export_empty_version_is_valid_not_an_error PASSED [ 95%]
tests/test_stories.py::test_export_empty_version_zero_annotations PASSED [ 97%]
tests/test_stories.py::test_export_unknown_version PASSED                [100%]

=============================== warnings summary ===============================
tests/test_stories.py::test_story_list_empty_state
  /app/backend/main.py:32: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.
    @app.on_event("startup")

tests/test_stories.py::test_story_list_empty_state
  /usr/local/lib/python3.12/site-packages/fastapi/applications.py:4681: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.
    return self.router.on_event(event_type)  # ty: ignore[deprecated]

tests/test_stories.py::test_story_list_empty_state
  /app/tests/conftest.py:100: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 40 passed, 3 warnings in 2.65s ========================
```

No Playwright run — `tests/ui/` is empty (no `.spec.ts` files); this is expected since all `[UI]` scenarios are `[UI — manual]`.

## Failure Analysis

All scenarios passed. The three `[UI — manual]` scenarios (Tap-to-react saves without confirmation; Tapping the active reaction again removes it; Feedback list row jumps back to its passage) require human verification in the running app and were not, and could not be, executed automatically — they are not counted as failures.

Independent verification note: the implementer reported 40 pytest tests passing pre-handoff across `test_paragraphs.py`, `test_ingest.py`, `test_stories.py`, `test_shell_proxy.py`. Re-running the suite from a freshly rebuilt container confirms exactly 40 passed, 0 failed — the report is accurate.

Process gap (non-blocking for this verdict, but worth fixing): `atlas-storyreader-test` was already running, but the central `01_System/test/compose.test.yml` has no `storyreader-test` / `essaycards-test`-style entry for this component — every other component (`storagetracker-test`, `essaycards-test`, `claudeconsole-test`, etc.) is registered there. I rebuilt the test container via the component-local `03_Application/StoryReader/compose.yml` (`docker compose -f compose.yml --env-file config.env --env-file secrets.env up -d storyreader-test --build`) instead, which succeeded cleanly and reflects the current implementation. The central compose.test.yml registration should still be added so future test runs and `make -C 01_System test-run COMPONENT=storyreader` work through the standard path.

## Required Action

Proceed to `/sprint-close`; separately, add a `storyreader-test` entry to `01_System/test/compose.test.yml` (missing from an otherwise consistent per-component registration) so the standard test-runner path works without falling back to the component-local compose file.
