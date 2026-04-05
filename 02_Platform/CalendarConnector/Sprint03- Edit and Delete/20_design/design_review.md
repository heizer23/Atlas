# Design Review — CalendarConnector Sprint03: Edit and Delete

> Iteration 2 — Re-review after design corrections applied by design-corrector.
> Previous verdict: APPROVED_WITH_CHANGES. See `20_design/design_corrections.md` for applied changes.

## Verdict
- Status: APPROVED
- Summary: Both required corrections from the prior review have been applied correctly. The POST HTTP status code is now explicit and consistent across `interfaces.provides`, `open_questions[0]` (resolved), and the approval condition. The `write_decision_log` interface carries `atlas_event_id: Optional[str] = None` in both `architecture.json` and `scaffolding.json`, and migration `004_decision_log_atlas_event_id.sql` provides the backing schema change with correct nullability and idempotency. The `_get_valid_access_token` call-site obligation is documented. No new issues were introduced by the corrections. The design is ready for implementation.

---

## Confirmed Problems

None identified.

---

## Recommended Improvements

None identified.

---

## Scaffold-Only Observations

1. **`deferred_decisions[1]` remains in tension with `upsert_event_index` scaffold**
   - Location: `20_design/scaffolding.json` → `token_store.py` `upsert_event_index` purpose field; `20_design/architecture.json` → `deferred_decisions[1]`
   - Observation: The scaffold describes `ON CONFLICT (atlas_event_id) DO UPDATE` reactivation as the implementation pattern, while `deferred_decisions[1]` states "either is valid." As noted in the previous review's Open Uncertainties, the UNIQUE constraint on `atlas_event_id` in `003_event_index.sql` makes the ON CONFLICT reactivation path the only schema-compatible option. The deferral text is therefore misleading but not blocking — the implementer will land on the correct path by following the scaffold.
   - Impact on implementation: Negligible. The implementer should follow the scaffold (`ON CONFLICT` reactivation) and ignore the deferral text on this point.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

None identified.

---

## Minimal Change Set

None required. All items from the prior Minimal Change Set have been applied.

---

## Approval Condition

All prior approval conditions are satisfied. The design is approved for implementation.
