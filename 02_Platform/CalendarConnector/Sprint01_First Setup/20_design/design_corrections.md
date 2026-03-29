# Design Corrections — calendar_connector

## Applied Changes

1. **Migration runner gap — closed design decision**
   - Review Source: `design_review.md` § Confirmed Problems #1, Minimal Change Set item 1
   - Files Updated: `20_design/architecture.json`
   - Change: Removed the open question "Should migrate.py be extended..." (owner: architecture) and replaced it with a closed `design_decisions` entry. Decision: `database.py init_schema()` is the authoritative schema deployment path for this component. `migrations/001_init.sql` runs idempotently on service startup. Extending `migrate.py` to scan Platform paths is explicitly deferred to a future infrastructure sprint. The corresponding risk entry "Migration runner gap" was removed from `risks`. The deferral item "Determine migration runner path" was removed from `deferrals.platform_implementer`. The reviewer checklist item was updated to reference the closed decision rather than an open question.

2. **Nginx proxy block reclassified to internal_required**
   - Review Source: `design_review.md` § Confirmed Problems #2, Minimal Change Set item 2
   - Files Updated: `20_design/architecture.json`
   - Change: Moved the nginx entry from `dependencies.internal_optional` to `dependencies.internal_required`. The entry now declares the required block shape explicitly: upstream name `atlas-calendar-connector:8000`, `proxy_pass http://$upstream_calendar`, and all four `proxy_set_header` / `proxy_read_timeout` directives matching the existing Atlas service pattern in `nginx.conf`. The deferral item "Add location /api/calendar block to nginx.conf" was removed from `deferrals.platform_implementer`. The reviewer checklist item was updated accordingly. Note: `scaffolding.json` contained no nginx classification field — the dependency classification lives exclusively in `architecture.json`.

3. **Port registry entry added**
   - Review Source: `design_review.md` § Confirmed Problems #3, Minimal Change Set item 3
   - Files Updated: `20_design/architecture.json`, `01_System/config.env`
   - Change: Added `CALENDAR_CONNECTOR_PORT=8021` to `01_System/config.env` under a new `# ── Platform: CalendarConnector ──` section, and added a matching comment line in the service port roster (`# CalendarConnector 8021`). Moved the `01_System/config.env` registration from `deferrals.platform_implementer` into `dependencies.internal_required` with an explicit note that compose.yml must reference the env var, not a raw port number. The deferral item "Add CALENDAR_CONNECTOR_PORT=8021 to 01_System/config.env" was removed from `deferrals.platform_implementer`. The compose.yml deferral item was updated to note the env var requirement. The existing `contracts.consumes` reference `"CALENDAR_CONNECTOR_PORT from 01_System/config.env"` was already correctly stated and was not changed.

---

## Unchanged by Design

All unaffected sections of `architecture.json` and `scaffolding.json` were preserved verbatim: `component_name`, `layer`, `source_definition`, `summary`, `classification`, `contracts`, `shared_views`, `interfaces`, `internal_flow`, `persistence`, `deferred_decisions`, `external_required`, `external_optional`, `forbidden`, `ui_implementer` deferrals, `test_writer` deferrals, and the remaining two `risks` entries. `scaffolding.json` was not modified.

---

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: The review's Minimal Change Set item 2 references both `architecture.json` and `scaffolding.json` for the nginx reclassification. Inspection of `scaffolding.json` confirmed it contains no nginx classification field — the `internal_optional`/`internal_required` classification vocabulary exists only in `architecture.json → dependencies`. No scaffolding change was required or made for this item; the change is complete in `architecture.json` alone. The `design_decisions` array is a new top-level key in `architecture.json`; it did not exist before and is placed after `risks` to avoid disturbing any existing key ordering that implementers or agents may reference.
