# Deployment Report — Chronicle Sprint01_First Heatmap

## Deployed

Chronicle application with unified calendar heatmap. Includes `GET /api/chronicle/calendar/sources`, `GET /api/chronicle/calendar/events`, and `PATCH /api/chronicle/calendar/sources` backend endpoints; `CalendarPage`, `HeatmapRenderer`, `SourceChooser`, and `DayDetailView` frontend components; Blueprint SQL view `shared_views.calendar_event_view` and selection table `shared_views.calendar_source_selection`.

---

## Bugs Found During Deployment

### Bug 1 — Shell Docker build failed: Chronicle `src/` not copied into build context

**Symptom:** `make up` failed at `shell-build` with:
```
Could not resolve "../../../../03_Application/Chronicle/src/shellConfig"
from "src/shell/main.tsx"
```

**Root Cause Layer:** Dockerfile / shell build configuration

**What happened:** The shell `Dockerfile` explicitly copies each application's `src/` directory so Vite can resolve shell registration imports at build time. When Chronicle was wired into `main.tsx` (via `shellConfig.ts`), the corresponding `COPY` line for `03_Application/Chronicle/src/` was not added to the Dockerfile. The build succeeded locally (Vite dev server resolves from disk) but failed in Docker where only explicitly copied paths exist.

**Fix applied:** Added `COPY 03_Application/Chronicle/src/ 03_Application/Chronicle/src/` to `02_Platform/02_Atlas_Shell/Dockerfile`.

---

### Bug 2 — nginx had no proxy entry for `/api/chronicle`

**Symptom:** Not surfaced as a visible error during `make up`, but would have caused all Chronicle API calls to return nginx 404s in the production container.

**Root Cause Layer:** nginx configuration

**What happened:** When a new application backend is added, two proxy configurations must be updated: `vite.config.ts` (dev server) and `nginx.conf` (production). The implementer updated `vite.config.ts` correctly but the production nginx proxy entry for `/api/chronicle → atlas-chronicle:8000` was missing.

**Fix applied:** Added `/api/chronicle` location block to `02_Platform/02_Atlas_Shell/nginx.conf`.

---

### Bug 3 — `make up` did not include Chronicle

**Symptom:** `make up` would start the full stack but not apply the Blueprint SQL view or start the Chronicle container.

**Root Cause Layer:** Makefile / stack orchestration

**What happened:** The `up` target in `01_System/Makefile` must be explicitly extended when a new application is added. `schema-chronicle` (Blueprint SQL view) and `chronicle-build chronicle-up` were not present. Similarly, `chronicle-down` was absent from the `down` target.

**Fix applied:** Added `$(MAKE) schema-chronicle` after `migrate`, `$(MAKE) chronicle-build chronicle-up` after `food-build food-up`, and `$(MAKE) chronicle-down` to the `down` target.

---

## Process Analysis

| Bug | Should have been caught at | Why it wasn't |
|---|---|---|
| Missing Dockerfile COPY | Implementer | The Dockerfile has a clear comment: "Add a new COPY line here when a new application is integrated." The implementer did not follow it. |
| Missing nginx proxy entry | Implementer | Same pattern as Dockerfile — nginx.conf must be updated alongside vite.config.ts when a new backend is integrated. The implementer updated only the dev path. |
| Missing `make up` entries | Implementer | The Makefile `up` target must be extended manually per application. No automation or checklist enforced this. |

All three bugs are in the same class: **deployment wiring checklist items not completed by the implementer.** None are design or logic errors. All were caught at first `make up` run.

---

## Agent Improvement Recommendations

### implementer

When wiring a new application into the Atlas Shell, the implementer must complete all four deployment integration points, not just shell registration:

1. `vite.config.ts` — dev proxy entry
2. `02_Platform/02_Atlas_Shell/Dockerfile` — `COPY` line for application `src/`
3. `02_Platform/02_Atlas_Shell/nginx.conf` — production proxy location block
4. `01_System/Makefile` — `schema-*` (if Blueprint SQL), `*-build *-up` in `up`, `*-down` in `down`

The implementer agent definition should be updated to include this checklist explicitly.

### sprint-orchestrator / overall process

Consider adding a deployment wiring verification step before marking a sprint `AWAITING_HUMAN_REVIEW` — check that all four integration points are present for any new application.

---

## No Contract or Platform Gaps

All three issues are operational/procedural. No contract inconsistencies, no platform bugs, no design errors identified.
