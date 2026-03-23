# Design Review — Chronicle Sprint01_First Heatmap

**Reviewer:** design-reviewer
**Artifacts reviewed:**
- `20_design/architecture.json`
- `20_design/scaffolding.json`
**Source spec:** `01_input/draft.md` + `10_specs/design_specs.md`
**Date:** 2026-03-23

---

## Verdict

APPROVED

---

## Review Summary

The design is correct, complete, and consistent with the draft spec, Atlas layer rules, and existing Atlas conventions. No mandatory changes required.

---

## Checklist

### Atlas Layer Compliance

- [x] Application layer owns only domain behavior. No Platform logic introduced.
- [x] Platform components consumed via existing interfaces only (@platform-ui, platform_contracts, platform_errorhandling).
- [x] Blueprint ownership of CalendarEventView is correctly declared. No attempt by Chronicle to own the view.
- [x] Heatmap renderer is explicitly inline with no Platform dependency declared — consistent with the draft resolution of Must-Fix 1.
- [x] No new Platform components introduced.

### Contracts

- [x] CalendarEventViewRow named contract is declared in architecture.json with explicit field types, identity, and rules. Satisfies the post-READY requirement from design_specs.md.
- [x] SourceListRow, SelectionToggleRequest, SelectionToggleResponse are declared as explicit stable contracts.
- [x] Non-Dataset justification is present and correct. Heatmap endpoint deviates from Dataset deliberately and the justification is sound (sparse date access, no pagination semantics).
- [x] PATCH /calendar/sources uses (application, source_label, selected) — identity is consistent with the view's (application, source_label) primary key.

### Spec Completeness

- [x] All acceptance criteria from draft are addressable from the design:
  - Calendar page exists in Application layer — CalendarPage.tsx + ShellEntry.tsx + shellConfig.ts.
  - Reads only from shared_views.calendar_event_view — calendar.py queries only this view.
  - No transformation logic in application — all transformation is in the Blueprint SQL.
  - Sources derived dynamically — GET /calendar/sources returns distinct rows from the view.
  - Selection persisted in calendar_source_selection — PATCH /calendar/sources upserts.
  - Selected sources show checkmark — SourceChooser uses selected field.
  - One selected source auto-opens — CalendarPage auto-selects first selected source on mount.
  - Only one source rendered at a time — architecture explicitly states this.
  - Values 1..100 / missing -> 0 — HeatmapRenderer design decisions section.
  - Workout and food data render correctly — both present in the Blueprint SQL view.
  - No Platform component for heatmap — explicitly enforced in architecture.json invariants.

### Am-3 Resolution

- [x] Am-3 (application field format) resolved correctly. Designer observed chronicle.sql directly and confirmed 'workout', 'food' as the canonical values. Frontend matching must use these strings. This is consistent with how the view is implemented.

### Am-2 Resolution

- [x] Am-2 (no source selected on first use) resolved: empty heatmap area with SourceChooser visible and a prompt. No auto-open. Acceptable MVP decision.

### Scaffolding

- [x] Port 8013 assigned to Chronicle — consistent with Atlas pattern (FoodTracker=8012).
- [x] Database pattern is consistent with FoodTracker — psycopg2 pool, ATLAS_PG_* env vars.
- [x] Shell registration pattern is correct — shellConfig.ts + side-effect import in main.tsx.
- [x] Makefile modifications are correctly scoped (schema-chronicle + chronicle-* service targets).
- [x] Blueprint SQL file is marked as already-present and not to be modified.
- [x] Implementation order is reasonable and dependency-ordered.

### Risks Carried Forward (not blocking approval)

- **R-2 (label stability):** source_label immutability is still not enforced. Architecture declares this as a known assumption. Acceptable for MVP — logged in architecture.json invariants.
- **R-3 (application field):** Am-3 is now resolved. Field format confirmed from chronicle.sql. Risk is closed.

---

## Issues Found

None blocking.

### Minor Observations (informational)

1. **No __init__.py listed for `03_Application/Chronicle/`** — scaffolding.json lists `03_Application/Chronicle/__init__.py` which is correct. Confirm this is needed given FoodTracker also has one. Yes — required for platform_errorhandling/contracts imports that traverse the package hierarchy.

2. **calendar.py does not import Dataset** — architecture correctly notes that named contracts are used instead. Implementer should import only what is needed from platform_contracts; do not import Dataset if it is not used. This avoids misleading code.

3. **HeatmapRenderer year range** — "current calendar year" is determined at page load from client Date. This is correct for MVP. No server-side year inference is needed since the view has no year filter itself — the implementer will need to filter by year range in the GET /calendar/events query or apply the filter client-side after fetching all rows. The architecture does not specify this detail. Implementer decision: filtering in the backend query is cleaner. Recommend filtering WHERE date >= YYYY-01-01 AND date < (YYYY+1)-01-01 in the backend, where year comes from a query param.

   **Action for implementer:** Add an optional `year` query parameter (integer, default=current year) to GET /calendar/events. Filter in SQL.

4. **CORS pattern** — Chronicle backend should mirror FoodTracker's CORS middleware: `allow_origin_regex=r"http://localhost:\d+"`. Scaffolding does not call this out explicitly. Implementer should not omit it.

---

## Post-Approval Notes for Implementer

1. GET /calendar/events should accept an optional `year` query parameter (default = current server year). Filter: `WHERE date >= '%year%-01-01'::date AND date < '%year+1%-01-01'::date` in the SQL query. The frontend passes the current client year.
2. Add CORS middleware matching FoodTracker's pattern.
3. Do not import Dataset in calendar.py — the endpoints use named row contracts, not Dataset. Import only what is used.
4. DayDetailView should render cleanly for 0-value / missing-day clicks — but architecture specifies that clicking a 0-value cell does nothing. Implementer: guard the onDayClick call so it is only invoked when value > 0.
5. The Makefile schema-chronicle target must apply `00_Blueprint/SharedViews/chronicle.sql`. The SQL uses `CREATE OR REPLACE VIEW` and `CREATE TABLE IF NOT EXISTS` — it is safe to re-apply.
