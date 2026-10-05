# Test Report — EssayCards — Sprint13_ReviewStatsSentenceFeedback

**Verdict:** TESTS_PASSING
**Date:** 2026-10-05
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Today endpoint — no scope returns global counts | test_review_stats.py::test_today_endpoint_no_scope_returns_global_counts | backend | PASS | — |
| Today endpoint — section_id without essay_id is rejected | test_today_endpoint_section_id_without_essay_id_is_rejected | backend | PASS | — |
| Today endpoint — topic combined with essay_id is rejected | test_today_endpoint_topic_combined_with_essay_id_is_rejected | backend | PASS | — |
| Today endpoint — repeat reviews count once in Unique | test_today_endpoint_repeat_reviews_count_once_in_unique | backend | PASS | — |
| Today endpoint — first-ever review from yesterday not First today | test_today_endpoint_first_review_from_yesterday_does_not_count_as_first_today | backend | PASS | — |
| Activity endpoint — reshaped row matches worked example | test_activity_endpoint_reshaped_row_matches_the_worked_example | backend | PASS | — |
| Activity endpoint — recall rate null on empty day | test_activity_endpoint_recall_rate_is_null_not_zero_on_a_day_with_no_reviews | backend | PASS | — |
| Summary endpoint — New Cards Seen per window | test_summary_endpoint_new_cards_seen_reflects_first_ever_reviews_inside_each_window | backend | PASS | — |
| Sentence splitting — plain prose | test_sentence_feedback.py::test_sentence_splitting_plain_prose_splits_at_sentence_boundaries | backend | PASS | — |
| Sentence splitting — markdown link | test_sentence_splitting_markdown_link_is_not_split_at_its_internal_period | backend | PASS | — |
| Sentence splitting — nugget reference | test_sentence_splitting_nugget_reference_is_not_split | backend | PASS | — |
| Sentence splitting — fenced code excluded | test_sentence_splitting_fenced_code_content_is_excluded | backend | PASS | — |
| Sentence feedback list — empty | test_sentence_feedback_list_empty_when_nothing_is_marked | backend | PASS | — |
| Sentence feedback list — only marked appear | test_sentence_feedback_list_only_marked_sentences_appear | backend | PASS | — |
| Marking difficult then thumbs up yields one row, both flags | test_marking_difficult_then_thumbs_up_on_same_sentence_yields_one_row_with_both_flags | backend | PASS | — |
| Clearing only true flag deletes row | test_clearing_the_only_true_flag_deletes_the_row | backend | PASS | — |
| Clearing one flag leaves other flag and row | test_clearing_one_flag_leaves_the_other_flag_and_the_row_intact | backend | PASS | — |
| Out-of-range sentence_index rejected | test_sentence_feedback_out_of_range_sentence_index_is_rejected | backend | PASS | — |
| sentence_text mismatch rejected | test_sentence_feedback_sentence_text_mismatch_is_rejected | backend | PASS | — |
| Unknown section rejected | test_sentence_feedback_unknown_section_is_not_found | backend | PASS | — |
| Invalid flag value rejected | test_sentence_feedback_invalid_flag_value_is_rejected | backend | PASS | — |
| [UI] Review page no redundant page label | review_page.spec.ts: plain review page shows no standalone Review caption | UI | PASS | — |
| [UI] Review page keeps Focus caption on scoped session | review_page.spec.ts: scoped review page keeps its Focus caption | UI | PASS | — |
| [UI] Review page five daily metrics | review_page.spec.ts: five daily metrics in order | UI | PASS | — |
| [UI] Review page interval row one unlabeled row of six | review_page.spec.ts: interval row is one unlabeled row of six numbers | UI | PASS | — |
| [UI] Reader — tapping a sentence opens two-button popover | sentence_feedback.spec.ts: tapping a sentence opens a popover; both flags toggle independently; difficult persists after reload | UI | PASS | — |
| [UI] Reader — both flags set independently | same test as above | UI | PASS | — |
| [UI] Reader — marked sentences persist after reload | same test as above | UI | PASS | — |
| [UI] Stats — stacked bar with recall-rate label and legend | review_stats.spec.ts: Study activity chart shows stacked columns... | UI | PASS | — |
| [UI] Stats — Observed Recall selector switches period | review_stats.spec.ts: Observed recall selector switches the displayed period... | UI | PASS | — |

No `[UI — manual]` scenarios in this spec.

## Test output

```
Test container rebuilt (service essaycards-test) and started; atlas_test exists.
docker exec atlas-essaycards-test pytest tests/ -v
================== 291 passed, 4 warnings in 64.70s (0:01:04) ==================
(re-run after rebuild: 291 passed, 4 warnings in 65.21s)

docker exec atlas-playwright npx playwright test .../review_page.spec.ts .../sentence_feedback.spec.ts .../review_stats.spec.ts
Running 9 tests using 3 workers
  9 passed (3.9s)
```

## Failure Analysis

All scenarios passed. Note: sentence_feedback.spec.ts runs against live data (atlas-shell) and toggles flags back off.

## Required Action

Run /sprint-close to close the sprint.
