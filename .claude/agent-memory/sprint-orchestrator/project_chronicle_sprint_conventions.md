---
name: Chronicle Sprint Conventions
description: Chronicle Sprint01 completed 2026-03-23; Sprint02 DRAFT_READY 2026-03-23; inline heatmap established; Blueprint SQL view at 00_Blueprint/SharedViews/chronicle.sql; port 8013; appId='chronicle'
type: project
---

Chronicle is a live application in `03_Application/Chronicle/`.

## Sprint01 — First Heatmap (completed 2026-03-23)

Sprint01 delivered: Blueprint SQL view, single-source heatmap, flat SourceChooser, DayDetailView, selection persistence.

**Known layout deviation:** Sprint01 input draft was at `01_input/draft.md` (not canonical `00_input/`). Sprint02 uses canonical `00_input/draft.md`.

**No skip-specs convention:** Canonical rules apply. Do not skip reviewer-specs-readiness for Chronicle. However, the FoodTracker sprint convention (designer reads draft.md directly) has been applied to Chronicle in practice — confirm per sprint.

**Heatmap renderer decision (Sprint01):** Inline implementation within Chronicle application. Platform extraction explicitly deferred. Do NOT route to a Platform designer for the heatmap unless a new sprint explicitly reopens this.

**Blueprint SQL view:** `00_Blueprint/SharedViews/chronicle.sql` — present and applied. Defines `shared_views.calendar_event_view` and `shared_views.calendar_source_selection`. Applied via `make schema-chronicle`.

**Application field format in the view:** Short lowercase strings — 'workout', 'food'. NOT full AppRegistry appIds.

**Port:** 8013. **AppRegistry:** appId='chronicle', basePath='/chronicle'.

**Shell registration:** Side-effect import added to `02_Platform/02_Atlas_Shell/src/shell/main.tsx` in Sprint01.

**Makefile targets:** schema-chronicle, chronicle-build, chronicle-up, chronicle-down, chronicle-logs, chronicle-reboot — all present from Sprint01.

**All four shell integration points completed in Sprint01:** Dockerfile COPY, nginx.conf proxy, vite.config.ts dev proxy, Makefile targets. No new deployment wiring is needed unless a new backend port or service is introduced.

## Sprint02 — Swimlanes and Selector (DRAFT_READY as of 2026-03-23)

Sprint02 extends Chronicle with:
- Grouped, collapsible SourceChooser (groups from SQL)
- Multi-source selection (max 4 at once)
- SwimlaneRenderer: transposed grid, swimlane-per-source
- Blueprint SQL view extension: adds `application_group` and `sort_order` columns

**Contract changes in Sprint02:**
- `SourceListRow` gains `application_group: string` and `sort_order: integer`
- `shared_views.calendar_event_view` gains `application_group` and `sort_order` columns (additive, per-branch constants in SQL)
- `GET /calendar/sources` response gains the two new fields, ordered by (application_group, sort_order, source_label)
- New component: `SwimlaneRenderer.tsx` (replaces direct HeatmapRenderer usage for multi-source)

**Open for designer:** Whether HeatmapRenderer is retired or retained as a single-source fallback.

**Why:** Sprint01 artifacts were detailed enough to derive Sprint02 contract requirements without ambiguity.

**How to apply:** When orchestrating future Chronicle sprints, start from the Sprint02 baseline contracts. The blueprint SQL view now includes grouping metadata. Swimlane cap of 4 is a product constraint, not a technical limit.
