# Design Review — Notifications (Sprint1_MVP for Workouttracker)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is structurally sound, correctly classified as Platform, and well-specified across its primary contract surfaces. The FCM payload contract is a strong boundary artifact. Two gaps require correction before implementation: the behavior of `cancel()` on an already-cancelled record is unspecified (leaving an implementer branch open in the `replace` path), and the timing tolerance claim in `contracts.provides` is internally inconsistent with the documented risk. These are targeted corrections that do not require redesign.

---

## Confirmed Problems

1. **`cancel()` behavior on already-cancelled records is unspecified**
   - Severity: Major
   - Location: `20_design/architecture.json` → `interfaces.provides` (NotificationService.cancel) and `internal_flow.step 4` (replace_notification)
   - Why it is a problem: `NotificationService.cancel` is documented with three branches: set-to-cancelled (if pending), no-op (if dispatched), raise NotificationNotFoundError (if not found). No branch is defined for calling `cancel()` on a record that already has `status=cancelled`. The `replace` path calls `cancel(old_id)` — if the caller passes an already-cancelled notification ID, `cancel()` has no specified behavior. The implementer must choose: treat as no-op, raise an error, or return success. Each choice produces different `replace` semantics.
   - Impact: Replace on a previously-cancelled notification will produce undocumented behavior. If `cancel()` raises on a cancelled record, the replace is blocked unexpectedly. If it silently succeeds, the caller gets no indication that the "old" notification was already inactive. Either outcome is correct or incorrect depending on the intended semantics — the design does not declare which is intended.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the lifecycle state matrix was specified for the happy path (pending → cancelled, dispatched → no-op) but the already-cancelled case, reachable through the replace operation, was not enumerated.

2. **Timing tolerance contract states conflicting claims**
   - Severity: Minor
   - Location: `20_design/architecture.json` → `contracts.provides` (fourth item) and `risks` (first item)
   - Why it is a problem: `contracts.provides` states "Maximum expected dispatch latency of ~5 seconds from fire_at under normal load (polling interval is 5 seconds; average latency is ~2.5 seconds)." The `risks` section then correctly identifies that the draft's 2-second acceptance criterion may be interpreted as worst-case, and states "average latency ~2.5 seconds." The `provides` claim says "maximum expected" is ~5 seconds while also saying "average is ~2.5 seconds" — these two statements together imply the worst-case is ~5 seconds, which is what the risk section says. The `provides` text is not wrong, but it underspecifies: it does not explicitly state the worst-case is ~5 seconds (one full polling interval). An implementer reading only `contracts.provides` and not `risks` would not know the worst-case figure.
   - Impact: The reviewer checklist item in `deferrals.reviewer` does not include verifying the timing claim against the acceptance criterion. If the implementation reviewer measures worst-case timing against the 2-second figure, the service may be marked non-conformant despite the design being correct.

---

## Recommended Improvements

1. **Add the already-cancelled branch to `cancel()` specification**
   - Location: `20_design/architecture.json` → `interfaces.provides` (NotificationService.cancel purpose field)
   - Improvement: Declare the explicit behavior when `cancel()` is called on a record with `status=cancelled`. The most defensible choice — consistent with the dispatched no-op — is: treat as no-op, return success. This should also be reflected in the `failure_modes` list or noted in `internal_flow.step 4`.
   - Why: Eliminates the implementer's branch decision. Keeps the cancel semantics consistent: "cancel is idempotent for terminal states."

2. **State worst-case timing explicitly in `contracts.provides`**
   - Location: `20_design/architecture.json` → `contracts.provides` (fourth item)
   - Improvement: Amend the provides text to read "Maximum expected dispatch latency of ~5 seconds from fire_at (one full polling interval); average ~2.5 seconds. The draft acceptance criterion of 2 seconds is expected-case, not worst-case." This makes the claim self-contained without requiring the reader to cross-reference the `risks` section.
   - Why: The reviewer checklist references this claim. The claim must be unambiguous to the implementation reviewer who may not read `risks`.

3. **Add `cancel-on-cancelled` to the `test_writer` deferrals**
   - Location: `20_design/architecture.json` → `deferrals.test_writer`
   - Improvement: Add a test case: "Cancel notification: DELETE on already-cancelled record returns 200 with no state change (idempotent)."
   - Why: Once the behavior is declared, the test case must exist to enforce it. Without it, the implementer has no coverage requirement for the new branch.

---

## Scaffold-Only Observations

1. **`service.py` stub describes itself as "business-free" but performs lifecycle state decisions**
   - Location: `20_design/scaffolding.json` → `02_Platform/Notifications/backend/service.py` (role field)
   - Observation: The role text says "Business-free notification lifecycle operations." Lifecycle state transitions (pending → cancelled, no-op on dispatched, raise on not-found) are state machine decisions, not purely technical operations. The label "business-free" may cause the implementer to underestimate the branching complexity in `cancel()` and `replace()`.
   - Impact on implementation: Low risk in isolation. Combined with the unspecified already-cancelled branch (Confirmed Problem 1), it increases the probability the implementer treats `cancel()` as simpler than it is.

2. **`fcm_client.py` is not referenced in `architecture.json interfaces`**
   - Location: `20_design/scaffolding.json` → `02_Platform/Notifications/backend/fcm_client.py`
   - Observation: `fcm_client.py` with `send_fcm_message()` is declared in the scaffolding but not listed in `architecture.json interfaces.provides` or `interfaces.exposed_surfaces`. The `dispatch_job.py` description in `architecture.json internal_flow.step 5` references `firebase_admin.messaging.send()` directly rather than via `fcm_client.send_fcm_message()`. This is a mild inconsistency between the flow description and the scaffold structure.
   - Impact on implementation: The implementer may implement the dispatch job calling Firebase directly rather than through `fcm_client.py`, defeating the isolation intent of that module.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

1. **WorkoutTracker integration call mechanism**
   - Location: `20_design/architecture.json` → `open_questions` (second item)
   - Uncertainty: The question "Does the WorkoutTracker call the Notifications platform via HTTP or in-process Python import?" is listed as open with owner "implementer." The design simultaneously lists "Notification platform endpoints embedded in WorkoutTracker router" as `forbidden` and mandates a standalone FastAPI service. HTTP is the only architecturally consistent option given these constraints, but the open_question creates apparent ambiguity.
   - Why it matters: If the implementer reads the open_question without reading the forbidden list, they may attempt an in-process import across service boundaries. This would not embed endpoints in the WorkoutTracker router (so technically not forbidden) but would create tight coupling between an Application and a Platform component.
   - Suggested owner: Architecture — the open_question should be closed with a definitive answer (HTTP) referencing the forbidden constraint and R-CON-PL-02.

2. **`schema.sql` is deferred to the implementer but is listed as a required input for persistence review**
   - Location: `20_design/architecture.json` → `persistence.schema_artifact` and `20_design/scaffolding.json` → `02_Platform/Notifications/20_Data/schema.sql`
   - Uncertainty: `architecture.json` declares `persistence.owns_persistent_state == true` and references `20_Data/schema.sql` as the schema artifact, but the file does not exist. The design review rules require schema.sql when persistence is declared. The schema is fully specified in `persistence.schema_notes` text — the absence of the file is a deferred implementation artifact, not a design gap. However, the implementation reviewer will need to verify schema conformance against `schema_notes`.
   - Why it matters: If the implementation reviewer applies the schema.sql rule strictly, the absence of the file pre-implementation could be flagged incorrectly as a gap. The schema specification in `persistence.schema_notes` is sufficient and complete for this review.
   - Suggested owner: Implementer — the implementer must produce `schema.sql` as the first deliverable before any other implementation begins, as downstream tests depend on it.

---

## Minimal Change Set

1. In `architecture.json` → `interfaces.provides` NotificationService.cancel: add explicit behavior for `status=cancelled` input — declare as no-op returning success (idempotent cancel for terminal states).
2. In `architecture.json` → `internal_flow.step 3` cancel_notification: add the already-cancelled case to the output list alongside the existing dispatched no-op case.
3. In `architecture.json` → `contracts.provides` (timing entry): amend to state worst-case explicitly as "~5 seconds (one full polling interval)" and note the 2-second acceptance criterion is expected-case, not worst-case.

---

## Approval Condition

The design may proceed to implementation when `architecture.json` declares explicit behavior for `cancel()` on an already-cancelled record (idempotent no-op or error — either is acceptable, but one must be declared).
