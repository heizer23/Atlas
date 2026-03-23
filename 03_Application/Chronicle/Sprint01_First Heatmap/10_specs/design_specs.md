# Specs-Readiness Review — Chronicle Sprint01_First Heatmap

**Reviewer:** reviewer-specs-readiness
**Source artifact:** `01_input/draft.md`
**Date:** 2026-03-23

---

## Verdict
NOT READY

---

## Must-Fix Issues (Blocking)

### 1. Platform Heatmap Renderer — dependency status unresolved

**Issue:** The draft calls for a Platform-layer Calendar/Heatmap Renderer ("no knowledge of sources or applications") as a named component in section 9. No existing Platform sprint or Platform component for this renderer exists in the repository.

**Why it blocks:** Without a decision on the dependency status, the designer faces two fundamentally different architectures:
- Option A: Build the heatmap renderer inline in the Chronicle application and defer Platform extraction to a future sprint. The designer scopes only the application layer.
- Option B: A Platform sprint for the heatmap renderer must run in parallel or must already exist. The designer scopes only the application layer's consumption of a Platform primitive.

These produce different architecture.json files, different scaffolding.json dependency declarations, and different contracts. Two designers would build materially different products.

**Minimal fix:** Human owner must decide — inline vs Platform sprint — before design handoff. Add one line to the draft: "Heatmap renderer: inline in Chronicle application for this sprint (defer Platform extraction)" OR "Heatmap renderer: Platform sprint X running in parallel — consume from @platform-ui."

---

## Safe-to-Defer Decisions (Designer can handle)

### Application registration and routing
The Atlas Shell registration pattern (AppRegistry.register, ShellEntry, basePath) is established and visible in FoodTracker. The designer can apply the same pattern for Chronicle with basePath `/chronicle` or equivalent. Safe designer decision.

### Selection persistence endpoint shape
The draft establishes that `selected` is a DB-side flag (single-user, global, database-prepared rows). The mutation endpoint shape (PATCH vs PUT, request body) is a design-level decision. Safe designer decision.

### Day detail view layout
The draft specifies fields to show (date, application, sourceLabel, label, value) but not the visual layout. Safe designer decision.

### Source chooser presentation
The draft specifies behavior (list all sources, checkmark for selected, toggle) but not the visual component type (modal, sidebar, dropdown, inline list). Safe designer decision.

### Year range for the heatmap
The draft does not specify how many years of data to display or whether the calendar spans one year or all available data. Safe designer decision for MVP — default to current calendar year.

---

## Atlas Violations / Redundancies

### Non-Dataset endpoint contract

**What the spec says:** The CalendarEventView row contract defines a flat row schema with 6 required fields. This is a custom payload shape, not a `Dataset`.

**Atlas rule:** UI Data Contract v1.0 states: "Use Dataset by default for tables, list views, filterable collections, chart source data, pageable result sets." The heatmap is a chart source — the question is whether Dataset applies.

**Assessment:** Dataset does not naturally fit a heatmap endpoint. The heatmap requires date-sparse row access (missing days render as 0), not paginated collection rendering. The Dataset contract's `meta.total`, `page`, `page_size` semantics do not apply. This is a valid controlled exception.

**Required correction:** The designer must declare the CalendarEventView endpoint as an explicit stable contract (per Atlas Manifest Rule 4: "Only the views derived from application tables are contracts"). The architecture.json must include a `contracts.named_contracts` section that formalizes the CalendarEventView row shape with field types, identity rules, and version. This is not redundant — it is required by Atlas.

---

## Ambiguities with Suggested Resolution

### Am-1: Backend mutation endpoint for `selected` toggle

**Ambiguity:** The draft specifies selection persistence as a requirement but does not define the API endpoint shape for toggling `selected`.

**Recommended decision:** `PATCH /chronicle/calendar/sources` with body `{ application: string, sourceLabel: string, selected: boolean }`. Returns updated row or ApiError.

**Confidence:** High — consistent with Atlas PATCH conventions and the identity model `(application, sourceLabel)`.

---

### Am-2: Auto-open behavior when no source is selected

**Ambiguity:** "Auto-opens one selected source" — what happens on first use when no source is selected?

**Recommended decision:** Show empty heatmap with chooser visible, no auto-open. User selects their first source manually.

**Confidence:** Medium — the draft is silent on this case. "Auto-open selected" reads as conditional on at least one selected source existing.

---

### Am-3: `application` field value format

**Ambiguity:** The example rows use `"workout-tracker"` and `"food-tracker"` as the `application` field. Is this the Atlas application ID (e.g., as registered in AppRegistry) or a human display string?

**Recommended decision:** Use the Atlas AppRegistry `appId` value (e.g., `"food"`, `"workout"`) as the canonical application identifier. The example values appear to be illustrative and should not be taken as the exact format.

**Confidence:** Low — the draft does not specify this. The designer must resolve this before implementing the database view. This may require clarification from the human owner if the application display name differs from the appId.

---

## Risks

### R-1 — CalendarEventView as a cross-application database contract

**Risk type:** Contract scope
**Description:** The CalendarEventView is populated by multiple applications (workout-tracker, food-tracker, etc.). This makes it a cross-application shared view — which per Atlas Manifest Rule 4 must live in `00_Blueprint/` as a shared database view contract, not inside the Chronicle application. If Chronicle owns the view definition, other applications cannot contribute to it without a Chronicle dependency.
**Severity:** High
**Resolution:** The CalendarEventView database view must be declared as a Blueprint contract (shared schema), not as a private application table. The draft does not address this. Designer must surface this during architecture design.

---

### R-2 — Label stability guarantee unresolved

**Risk type:** Data integrity
**Description:** Open question in draft: "Do you enforce that sourceLabel cannot change once created?" The draft marks this as non-blocking but notes that selection persistence can break if labels change. A selection stored against a stale label will silently orphan.
**Severity:** Medium
**Resolution:** For MVP, acceptable to defer. Designer should declare this as a known assumption in architecture.json invariants.

---

### R-3 — `application` field ambiguity (see Am-3 above)

**Risk type:** Integration breakage
**Description:** If the database view uses a different string format for `application` than what the frontend expects, source matching will fail silently.
**Severity:** Medium
**Resolution:** Resolve Am-3 before database view implementation.

---

## Minimal Edits to Reach READY

1. **Resolve Platform dependency status** — Add one explicit line to section 9 (Required components): "Heatmap renderer for Sprint01: inline implementation within Chronicle application. Platform extraction deferred to a future Platform sprint." OR identify an existing Platform component. This unblocks the designer's architecture scope.

2. **Acknowledge CalendarEventView as Blueprint contract** — Add a note to section 8 (Required contracts): "CalendarEventView is a cross-application shared database view. It must be declared as a Blueprint schema contract, not a Chronicle-private table." This ensures the designer routes the contract correctly.

---

## Post-READY notes for designer

The following must be addressed during design (not spec changes):

- Declare CalendarEventView contract under `architecture.json contracts.named_contracts` with explicit field types and version.
- Establish Am-3 resolution (application field format) before designing the database view.
- Declare the `selected` mutation endpoint as an explicit exposed surface with request/response contract.
- Register Chronicle in Atlas Shell AppRegistry following FoodTracker's ShellEntry + shellConfig.ts pattern.
