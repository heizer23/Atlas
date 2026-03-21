# Design Review — food_tracker (Sprint 02 Re-Review)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: All three prior blocking issues have been correctly resolved. The `all_time + daily` zero-fill carve-out is now explicit in both the invariant and internal_flow step 8. The `preview_model` shape is declared with a field-definition reference. The ISO week SQL expression is specified with the correct `IYYY`/`IW` format. Two new Major problems were identified during this re-review: `_zero_fill` as specified cannot produce rows for the `all_time + daily` passthrough case (bucket_ids is empty, so no output rows are emitted even when DB rows exist), and `_compute_buckets` has no DB access in its signature but step 8 requires DB results to enumerate bucket ids for `all_time + aggregated`. Both gaps will cause an implementer to guess or produce incorrect behavior. These must be resolved before implementation proceeds.

---

## Confirmed Problems

1. **`_zero_fill` cannot execute the `all_time + daily` passthrough**
   - Severity: Major
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `files[5].private_objects._zero_fill.purpose`; `03_Application/FoodTracker/10_Design/component_architecture.json` → `internal_flow[9]` (step 10)
   - Why it is a problem: `_zero_fill` iterates `bucket_ids: list[str]` and produces one output row per entry. For `all_time + daily`, step 8 (`_compute_buckets`) returns an empty `bucket_ids` list by design. Step 10 calls `_zero_fill` with that empty list. The result is an empty output — regardless of whether `db_rows` is non-empty. The architecture invariant requires that for `all_time + daily`, "only DB result rows are returned." There is no specified mechanism to pass those DB rows through when `bucket_ids` is empty. Additionally, `bucket_label` (day-of-month integer string) must be attached to each row; for the passthrough case, no `label_map` entry exists for any DB row since the label_map is built from the bucket_ids list in step 8.
   - Impact: An implementer following the scaffold literally will produce an empty Dataset for `all_time + daily` when data exists. If the implementer adds an ad-hoc special case, bucket_label values will be undefined because the label derivation rule for this path is not specified in the scaffold.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the zero-fill carve-out for `all_time + daily` was correctly added to the invariant and step 8, but the `_zero_fill` function contract and step 10 were not updated to describe how to handle an empty bucket_ids list with a non-empty db_rows result.

2. **`_compute_buckets` has no DB access but `all_time + aggregated` requires DB results to enumerate bucket ids**
   - Severity: Major
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `files[5].private_objects._compute_buckets` (signature `(query: ReportQuery) → tuple[list[str], dict[str, str]]`); `03_Application/FoodTracker/10_Design/component_architecture.json` → `internal_flow[7]` (step 8)
   - Why it is a problem: Step 8 explicitly states `all_time + aggregated → years present in DB result` as the source of bucket ids. The `_compute_buckets` function signature accepts only `query: ReportQuery` — it has no DB connection parameter and no pre-fetched DB result input. For `all_time + aggregated`, the function cannot enumerate bucket ids without first knowing which years exist in the database. Step 9 (`_query_logs`) is where the DB query occurs and is specified to run after step 8. There is no defined mechanism for `_compute_buckets` to obtain DB results before step 9 executes.
   - Impact: An implementer must either reorder steps 8 and 9, add a DB parameter to `_compute_buckets`, or merge the two functions — none of which are declared in the design. Any choice made silently diverges from the specified flow and signature.
   - Likely Cause (Design Phase): Dependency Misinterpretation — step 8 was updated to describe `all_time + aggregated` behavior correctly in prose, but the corresponding function signature was not updated to reflect the additional input dependency this behavior introduces.

---

## Recommended Improvements

1. **Declare `_zero_fill` passthrough behavior for empty `bucket_ids`**
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `files[5].private_objects._zero_fill.purpose`; `component_architecture.json` → `internal_flow[9]` (step 10)
   - Improvement: Extend `_zero_fill`'s purpose statement to include: "When `bucket_ids` is empty (the `all_time + daily` case), emit one row per entry in `db_rows` in ascending `bucket_id` order, deriving `bucket_label` from the day-of-month integer of the `bucket_id` date string." Update step 10 to describe this conditional path.
   - Why: Without this, the `all_time + daily` passthrough path has no specified behavior and `bucket_label` is undefined for those rows.

2. **Resolve `_compute_buckets` input dependency for `all_time + aggregated`**
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `files[5].private_objects._compute_buckets` (signature); `component_architecture.json` → `internal_flow[7]` (step 8) and `internal_flow[8]` (step 9)
   - Improvement: Either (a) add an optional `db_rows: dict[str, dict] | None = None` parameter to `_compute_buckets` and note that it is required for `all_time + aggregated`, or (b) reorder: run step 9 before step 8 for `all_time` scope only, passing results into step 8. Either choice must be declared explicitly in the scaffold signature and the internal_flow step ordering note.
   - Why: An undeclared input dependency on DB results for one scope variant breaks the function contract and forces the implementer to invent a resolution.

---

## Scaffold-Only Observations

1. **`_build_report_label` purpose does not cover `week + daily` label format**
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `files[5].private_objects._build_report_label.purpose`
   - Observation: The examples given are `'March 2025 — Daily'`, `'All Time — Aggregated'`, `'2025 — Daily'`. The `week + daily` case (e.g., `'2025-W12 — Daily'` or a human-readable equivalent such as `'Week 12, 2025 — Daily'`) is not illustrated. All other scope+mode combinations are covered by analogy; the week case is the only one without an implied format.
   - Impact on implementation: Low risk — implementer can infer the pattern, but an explicit example would remove ambiguity about whether the period label uses the raw `YYYY-WNN` key or a human-expanded form.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

1. **`all_time + aggregated` zero-fill scope is ambiguous in the invariant**
   - Location: `03_Application/FoodTracker/10_Design/component_architecture.json` → `contracts.invariants[11]`
   - Uncertainty: The invariant carves out only `all_time + daily` from zero-fill. Step 8 describes `all_time + aggregated` as enumerating "years present in DB result" — which also means no zero-fill (no synthetic rows for years with no data). The invariant text does not explicitly state whether `all_time + aggregated` also skips zero-fill. Both behaviors are technically consistent, but the invariant as written implies `all_time + aggregated` does get zero-fill (only `daily` is excluded), which contradicts step 8.
   - Why it matters: If the invariant is taken as authoritative, the implementer must produce zero-value rows for years between the first and last logged year with no data in `all_time + aggregated`. If step 8 is authoritative, no zero-fill occurs. Different implementers will reach different conclusions.
   - Suggested owner: Architecture

---

## Minimal Change Set

1. Extend `_zero_fill.purpose` in `component_scaffold.json` and step 10 in `component_architecture.json` to specify the empty-bucket_ids passthrough path: when `bucket_ids` is empty, emit DB rows in ascending order with `bucket_label` derived from the day-of-month of each `bucket_id` date string.
2. Resolve the `_compute_buckets` input dependency gap: choose either (a) add an optional `db_rows` parameter to the signature for the `all_time + aggregated` case or (b) declare that `_query_logs` runs before `_compute_buckets` when `scope == 'all_time'`, and update both the scaffold signature and internal_flow step ordering accordingly.
3. Clarify `contracts.invariants[11]` to explicitly state whether `all_time + aggregated` zero-fill also uses DB-derived bucket enumeration (matching step 8) or is expected to produce zero-fill rows for years between first and last logged year.

---

## Approval Condition

The design may proceed to implementation when `_zero_fill`'s behavior for an empty `bucket_ids` list is fully specified (including `bucket_label` derivation for passthrough rows) and `_compute_buckets`'s input dependency for `all_time + aggregated` is declared in the scaffold signature.

---

## Prior Blocking Issues — Resolution Status

| Prior Issue | Severity | Resolution Status |
|---|---|---|
| `all_time + daily` zero-fill undefined | Critical | Resolved — invariant and step 8 now explicitly exclude `all_time + daily` from zero-fill |
| `preview_model` response shape undeclared | Major | Resolved — `interfaces.exposed_surfaces[1].ui_contract` now declares `{preview: <normalised_dict>}` with field reference to Sprint 01 §6.4 |
| ISO week SQL expression unspecified | Major | Resolved — `_build_group_key_expr.purpose` now specifies `to_char(logged_at,'IYYY-"W"IW')` with explicit note against `WW` |
