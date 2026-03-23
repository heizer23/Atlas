# Redesign Summary — food_tracker (Sprint 02)

## Applied Changes

1. **`all_time + daily` bucket enumeration — scope-conditional zero-fill declaration**
   - Review Source: `design_review.md` Confirmed Problem 1 (Critical) and Minimal Change Set item 1
   - Files Updated: `10_Design/component_architecture.json`
   - Change: `internal_flow[7]` (step 8, `compute_bucket_boundaries`) now explicitly states that `scope=all_time` with `mode=daily` returns an empty bucket list and skips zero-fill, with DB result rows returned as-is. `contracts.invariants[11]` (zero-fill invariant) is now scope-conditional: it excludes `scope=all_time + mode=daily` and declares that in that case only DB result rows are returned and an empty dataset is returned when no rows exist.
   - Decision rationale: Option (b) from the review (exclude zero-fill for `all_time + daily`) was chosen. This is the smallest defensible change — it is consistent with the existing `risks[4]` framing already in the artifact ("Zero-fill only applies within a defined period; all_time with no data cannot define a period to fill") and requires no new undeclared pre-step DB query. The sprint definition states "daily views include zero-value buckets for dates with no entries" in a context that presupposes a bounded period; `all_time + daily` has no bounded period by definition.

2. **`preview_model` contract reference declared explicitly**
   - Review Source: `design_review.md` Confirmed Problem 2 (Major), Hard Rule Violation 1, and Minimal Change Set item 2
   - Files Updated: `10_Design/component_architecture.json`
   - Change: `interfaces.exposed_surfaces[1]` (`POST /api/food/validate`) `ui_contract` field now reads `"preview_model (shape: {preview: <normalised_dict>}; field definitions governed by 00_Requirements/FoodTracker01 — Manual JSON Intake.md §6.4) | ApiError"`. The `purpose` field was also extended to note that `food.py` is unchanged in Sprint 02 and that the governing contract artifact remains the Sprint 01 definition.

3. **PostgreSQL ISO week SQL expression specified in `_build_group_key_expr`**
   - Review Source: `design_review.md` Confirmed Problem 3 (Major) and Minimal Change Set item 3
   - Files Updated: `10_Design/component_scaffold.json`
   - Change: `files[5]` (`report.py`) `private_objects._build_group_key_expr.purpose` now includes the explicit expression `to_char(logged_at,'IYYY-"W"IW')` for the `month + aggregated` ISO week case, with a note that `IYYY` is the ISO year and `IW` is the ISO week number (01-53), and that `WW` must not be used as it is non-ISO and will silently mismatch the `YYYY-WNN` bucket ids enumerated in `_compute_buckets`.

## Unchanged by Design

All other sections of `component_architecture.json` and `component_scaffold.json` were preserved verbatim. This includes all other internal_flow steps, all other invariants, all other exposed surfaces, all dependency declarations, all scaffold file entries, and all deferred decisions. The Scaffold-Only Observations (ChartPanel drill affordance and browser vs. server time) were noted in the review as low-risk implementation decisions and are not in the Minimal Change Set; they were not touched. `20_Data/schema.sql` was not referenced by the review and was not modified.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: For Minimal Change Set item 1, the review required a "single chosen resolution" for `all_time + daily` enumeration. Option (b) — no zero-fill for `all_time + daily` — was chosen over option (a) (pre-step DB min/max query) because it requires no new undeclared mechanism and aligns with the existing risk framing already present in the artifact. If the product owner prefers option (a) (DB min/max query to bound the range), that is a separate decision requiring a further targeted correction to step 8 and the invariant.

---

# Redesign Summary — food_tracker (Sprint 02, Round 2)

## Applied Changes

1. **`_zero_fill` empty-bucket_ids passthrough path specified**
   - Review Source: `design_review.md` Confirmed Problem 1 (Major) and Minimal Change Set item 1
   - Files Updated: `10_Design/component_architecture.json` (`internal_flow[9]`, step 10), `10_Design/component_scaffold.json` (`files[5].private_objects._zero_fill.purpose`)
   - Change: Step 10 (`zero_fill_and_build_rows`) now declares two explicit conditional paths. Normal path (bucket_ids non-empty): unchanged behavior. Passthrough path (bucket_ids empty, the all_time+daily case): emit one row per db_rows entry in ascending bucket_id order; derive `bucket_label` from the day-of-month integer string of the YYYY-MM-DD `bucket_id` (e.g., `'2025-03-07'` → `'7'`); `label_map` is empty in this case and must not be consulted. `_zero_fill.purpose` in the scaffold was extended with the same passthrough path and `bucket_label` derivation rule.

2. **`_compute_buckets` input dependency resolved for `all_time + aggregated`**
   - Review Source: `design_review.md` Confirmed Problem 2 (Major) and Minimal Change Set item 2
   - Files Updated: `10_Design/component_architecture.json` (`internal_flow[7]` step 8, `internal_flow[8]` step 9), `10_Design/component_scaffold.json` (`files[5].public_objects.get_report.purpose`, `files[5].private_objects._compute_buckets` signature and purpose)
   - Resolution chosen: Option (a) — add an optional `db_rows: dict[str, dict] | None = None` parameter to `_compute_buckets`. For `scope=all_time+aggregated`, the `get_report` handler calls `_query_logs()` first, then passes `db_rows` into `_compute_buckets()`. For all other scope+mode combinations the existing call order is unchanged. This is the smallest change: no steps are renumbered, no new functions are added, and the dependency is explicit in the signature rather than implicit in call order.
   - Step 9 (`query_food_logs`) was updated with a NOTE stating that for `all_time+aggregated` it must run before step 8 so `db_rows` is available. Step 8 (`compute_bucket_boundaries`) inputs list was updated to reflect the optional `db_rows` parameter. `get_report` purpose in the scaffold was updated to declare the conditional call ordering.

3. **`contracts.invariants[11]` clarified to cover `all_time + aggregated`**
   - Review Source: `design_review.md` Minimal Change Set item 3 and Open Uncertainty 1
   - Files Updated: `10_Design/component_architecture.json` (`contracts.invariants[11]`)
   - Change: Invariant [11] (zero-fill rule) now explicitly carves out two exceptions: (a) `all_time + daily` (unchanged from round 1) and (b) `all_time + aggregated`, where bucket ids are the distinct years present in the DB result and no synthetic zero-fill rows are produced for years with no data. This resolves the ambiguity identified in the review: step 8 is authoritative; the invariant now matches it. This is also consistent with the sprint definition's test expectation ("returns one row per year with data, and zero rows for years with no data within the all_time span").

## Unchanged by Design

All other sections of `component_architecture.json` and `component_scaffold.json` were preserved verbatim. Internal flow steps 1-7 and 11, all other invariants, all exposed surfaces, all dependency declarations, all other scaffold file entries, all deferrals, and `20_Data/schema.sql` were not touched. The Scaffold-Only Observation regarding `_build_report_label` week label format was noted as low-risk (Minor, not in the Minimal Change Set) and was not applied.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: For Minimal Change Set item 2, option (a) (optional `db_rows` parameter) was chosen over option (b) (reorder steps 8 and 9 for `all_time` scope) because it requires fewer artifact changes: only the `_compute_buckets` signature changes, and the step numbering is preserved. The conditional call ordering is declared in the `get_report` handler purpose and noted in the step 9 description, giving the implementer an unambiguous single source for the orchestration decision.
