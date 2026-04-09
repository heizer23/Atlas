# Architecture Audit Report

> **Audit Run:** `LabelEngine_auditrun_04_09_2026`
> **Run Type:** component-specific (LabelEngine platform component + TaskTracker consumer integration)
> **Agent:** audit_architecture
> **Date:** 2026-04-09

---

## 1. Executive Summary

The LabelEngine platform component is structurally sound. It is correctly classified as a platform service, carries no domain meaning, exposes a documented HTTP API, and its design and implementation artifacts are coherent and approved. The LabelEngine itself has no rule violations.

The integration between LabelEngine and TaskTracker contains three confirmed structural problems — two high-severity and one medium — that span the platform-application boundary.

**Problem 1 (high, boundary_drift):** `fetch_labels_for_tasks` in TaskTracker's `tasks.py` (lines 72–95) issues SQL directly against `labels.object_labels` and `labels.labels` using TaskTracker's own Postgres connection pool, bypassing the LabelEngine API entirely for all read operations. Write operations (attach/detach) correctly use the LabelEngine HTTP API. This asymmetry couples TaskTracker to LabelEngine's internal DB schema layout with no formal exception record.

**Problem 2 (high, contract_violation + exception_missing_record):** All five label proxy endpoints in TaskTracker return LabelEngine's native bespoke shapes (`{ labels: [...] }`, `ObjectLabelRecord`) verbatim to the Atlas Shell UI. R-CON-BP-04 requires all UI-visible data endpoints to return `Dataset` or `ApiError`. The frontend `ShellEntry.tsx` destructures `res.labels` directly (lines 435–436, 732–733, 893–895), confirming the coupling. No `ARCHITECTURE_EXCEPTIONS.md` exists for TaskTracker. Notably, the LabelEngine's own `architecture.json` `ui_implementer` deferrals section explicitly anticipated Dataset-shaped responses from the proxy layer: "TaskTracker backend proxies all label operations and **serves Dataset-shaped responses to the UI**." The implementation did not follow through.

**Problem 3 (medium, missing_rule_signal):** `list_tasks` embeds a `labels` array into `Dataset` rows (not declared in `TASK_SCHEMA`) and the frontend `TaskGroupedList` reads this field for grouping logic (`task.labels?.[0]?.name`). The UI Data Contract says undeclared row fields are "silently ignored" by rendering primitives — they are — but no Atlas rule addresses the pattern of using undeclared Dataset row fields as application-logic side-channels.

### Finding Counts

| Category | Critical | High | Medium | Low |
|---|---|---|---|---|
| boundary_drift | — | 1 | — | — |
| contract_violation | — | 1 | — | — |
| exception_missing_record | — | 1 | — | — |
| missing_rule_signal | — | — | 1 | — |
| verification_required | — | — | 1 | — |
| likely_orphaned | — | — | — | 1 |

### Top 5 Recommended Actions

1. Create `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md` to formally cover the non-Dataset label proxy responses (F-002/F-003).
2. Resolve the direct DB read crossing: add `POST /api/objects/labels/batch` to LabelEngine, or register a formal exception for the read-only direct SQL access (F-001).
3. Declare `labels` in `TASK_SCHEMA`, or replace the embedded-labels grouping with a proper grouped endpoint (F-004).
4. Add one invariant sentence to `architecture.json → contracts.invariants` declaring the label uniqueness model (F-005). No code change needed.
5. Invoke the `test_writer` agent on LabelEngine — all 17 specified test cases are stubs (F-006).

---

## 2. Audit Basis

**Rules consulted:**
- R-CON-BP-01 (Architecture as AI Interface) — `.claude/rules/R-CON-BP.md`
- R-CON-BP-02 (Contracts and Boundaries) — `.claude/rules/R-CON-BP.md`
- R-CON-BP-03 (Durable State Must Be Explicit) — `.claude/rules/R-CON-BP.md`
- R-CON-BP-04 (UI Data Contract) — `.claude/rules/R-CON-BP.md`
- R-CON-PL-01 (Platform Boundary) — `.claude/rules/R-CON-PL.md`
- R-CON-PL-02 (Dependency Direction) — `.claude/rules/R-CON-PL.md`
- R-OPS-BP-01 (Surface Violations Explicitly) — `.claude/rules/R-OPS-BP.md`
- R-OPS-BP-02 (Security: Least Privilege) — `.claude/rules/R-OPS-BP.md`

**Contracts consulted:**
- `02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md` (v0.3)
- `02_Platform/packages/platform_contracts/contracts.py`
- `02_Platform/LabelEngine/Spint01- First labels/20_design/architecture.json` (component contract)

**Exception records inspected:**
- `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` — three exceptions (R-EXC-PC-01, R-EXC-PC-02, R-EXC-PC-03); none cover TaskTracker label integration
- No `ARCHITECTURE_EXCEPTIONS.md` exists for `03_Application/TaskTracker`
- No `ARCHITECTURE_EXCEPTIONS.md` exists for `02_Platform/LabelEngine`

**Files inspected:**

LabelEngine:
- `app/main.py`, `app/models.py`, `app/database.py`, `app/service.py`
- `app/routers/labels.py`, `app/routers/objects.py`, `app/routers/groups.py`
- `Dockerfile`, `compose.yml`, `pyproject.toml`
- `tests/test_labels.py`, `tests/test_objects.py`, `tests/test_groups.py`
- `Spint01- First labels/20_design/architecture.json`
- `20_Data/schema.sql`, `20_design/design_review.md`
- `30_implementation/implementation_notes.md`, `90_meta/sprint_state.json`

TaskTracker:
- `backend/routers/tasks.py`, `backend/database.py`
- `src/ShellEntry.tsx`
- `schema.sql`, `compose.yml`
- `Sprint05/30_implementation/implementation_notes.md`

Platform shared:
- `02_Platform/packages/platform_contracts/contracts.py`
- `02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md`

**Exclusions:** LabelEngine test coverage not evaluated as a rule violation (test stubs are a delivery gap, not a structural violation). Sprint process compliance is out of scope.

---

## 3. Findings

---

### F-001 — Direct Cross-Schema SQL: TaskTracker Queries LabelEngine's Internal DB Tables

- **category:** `boundary_drift`
- **severity:** high
- **claim:** TaskTracker's `fetch_labels_for_tasks` queries `labels.object_labels` and `labels.labels` directly via TaskTracker's own Postgres connection pool, bypassing the LabelEngine API for all read operations and coupling the application to the platform service's internal persistence layout.
- **evidence:**
  - `03_Application/TaskTracker/backend/routers/tasks.py:72–95`: `SELECT ... FROM labels.object_labels ol JOIN labels.labels l ... WHERE ol.object_id = any(%s) AND ol.object_type = 'task'` executed using `conn` from `backend.database.get_db()` (TaskTracker's own pool).
  - `03_Application/TaskTracker/backend/database.py`: TaskTracker's pool uses the same `ATLAS_PG_*` env vars and connects to the same Postgres instance as LabelEngine. Both services share DB connectivity; the `labels` schema is physically accessible.
  - `tasks.py:368–386`: write operations (attach, detach) correctly use `_label_client()` (httpx). The asymmetry is confirmed: reads bypass the API; writes use it.
  - `tasks.py:229–233`: `labels_by_task = fetch_labels_for_tasks(conn, task_ids)` is called inside the `list_tasks` endpoint handler.
  - `02_Platform/LabelEngine/Spint01- First labels/20_design/architecture.json` `dependencies.forbidden`: LabelEngine explicitly lists "Any import from 03_Application" as forbidden. The inverse boundary — applications must consume LabelEngine via its HTTP API, not by direct DB access — is implied by R-CON-PL-01 but not stated in LabelEngine's own contract (a secondary gap).
- **rule_refs:** R-CON-PL-01, R-CON-BP-02, R-CON-BP-03
- **contract_refs:** `02_Platform/LabelEngine/Spint01- First labels/20_design/architecture.json` (the component's declared integration surface is HTTP; direct DB access is not a declared integration point)
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 72–95, 229–233)
  - `03_Application/TaskTracker/backend/database.py`
- **why_it_matters:** LabelEngine's DB schema (`labels.object_labels`, `labels.labels`, column names `object_id`, `label_id`, `label_name`, `attached_at`) is the private implementation of a platform service. Any schema change — renaming columns, adding partitioning, moving to a separate DB host, altering the `object_type` constraint — silently breaks TaskTracker's read path with no contract signal. LabelEngine cannot enforce its own invariants (e.g., `object_type` casing via its CHECK constraint logic, `attached_at` ordering rules via its service layer) for reads that bypass it. The asymmetry between read (direct SQL) and write (API) also creates a dual-source truth: label writes go through the LabelEngine service; reads go around it.
- **recommended_action:** Replace `fetch_labels_for_tasks` with calls through the LabelEngine API. Since per-task HTTP calls would cause an N+1 problem for list views, add a batch endpoint to LabelEngine — e.g., `POST /api/objects/labels/batch` with body `{"object_ids": [...]}` returning a map of `object_id -> [ObjectLabelRecord]`. Update `fetch_labels_for_tasks` to call this batch endpoint via `_label_client()`. If direct DB access is retained as an intentional performance optimization, create a formal exception record in `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md` declaring: the performance rationale, the read-only constraint, and that the access must be updated if LabelEngine's schema changes.
- **confidence:** high

---

### F-002 — Label Proxy Endpoints Return Non-Dataset Shapes to the UI

- **category:** `contract_violation`
- **severity:** high
- **claim:** Five label-facing endpoints in TaskTracker return LabelEngine's native bespoke response shapes verbatim to the Atlas Shell UI, violating R-CON-BP-04's requirement that all UI-visible data endpoints return `Dataset` or `ApiError`.
- **evidence:**
  - `tasks.py:352–357` — `search_labels`: `return JSONResponse(status_code=resp.status_code, content=resp.json())` — passes through `{ labels: [{ id, name }] }` verbatim.
  - `tasks.py:360–365` — `get_task_labels`: same pattern, passes through `{ labels: [{ object_id, label_id, label_name, attached_at }] }`.
  - `tasks.py:368–376` — `attach_task_label`: same pattern, passes through `ObjectLabelRecord` shape.
  - `tasks.py:393–425` — `set_task_labels`: passes through `resp.json()` from `get_task_labels` at line 425.
  - `ShellEntry.tsx:435–436`: `const res = await apiFetch<{ labels: LabelRecord[] }>(...); setSuggestions((res as { labels: LabelRecord[] }).labels ?? [])` — frontend explicitly casts and reads `res.labels`.
  - `ShellEntry.tsx:732–733`: same `res.labels` destructure pattern in a second component.
  - `ShellEntry.tsx:893–895`: `apiFetch<{ labels: AttachedLabel[] }>(...).then(res => { setAttachedLabels((res as { labels: AttachedLabel[] }).labels ?? []) })` — consuming `{ labels: AttachedLabel[] }` shape from `GET /tasks/{task_id}/labels`.
  - `UI_Data_Contract.md §9`: "Producers must not: invent app-local response shapes when Dataset fits."
  - `architecture.json` (LabelEngine) `ui_implementer` deferrals: "TaskTracker backend proxies all label operations and **serves Dataset-shaped responses to the UI where the UI contract applies**" — the design anticipated Dataset transformation; the implementation did not perform it.
- **rule_refs:** R-CON-BP-04
- **contract_refs:** `02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md` (v0.3), `02_Platform/packages/platform_contracts/contracts.py`
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 352–425)
  - `03_Application/TaskTracker/src/ShellEntry.tsx` (lines 435–436, 732–733, 893–895)
- **why_it_matters:** R-CON-BP-04 is the invariant that allows the Atlas Shell to render any application's data through platform primitives. Bespoke shapes couple the frontend directly to LabelEngine's internal model. The `isApiError` check in the frontend cannot correctly classify non-Dataset, non-ApiError shapes, making error-path behavior ambiguous. If LabelEngine changes `ObjectLabelRecord`'s field names, both the proxy and the frontend break with no type-system signal.
- **recommended_action:** Option A: Transform the read proxy endpoints to return `Dataset`. For `GET /tasks/labels/search`, a Dataset with `schema: [{key: "id", type: "string"}, {key: "name", type: "string"}]` and a row per label. For `GET /tasks/{task_id}/labels`, a Dataset with `ObjectLabelRecord` fields as columns. Update `ShellEntry.tsx` to consume `res.rows`. Option B: For mutation endpoints (`POST`, `PUT`, `DELETE`) where a Dataset response is architecturally awkward, register a formal exception with a stated rationale and constraint. Either option requires creating `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`.
- **confidence:** high

---

### F-003 — No Formal Exception Record for Non-Dataset Label Proxy Responses

- **category:** `exception_missing_record`
- **severity:** high
- **claim:** The implemented deviation from R-CON-BP-04 in TaskTracker's label proxy endpoints has no formal exception record in any registered location.
- **evidence:**
  - Glob search for `03_Application/TaskTracker/**/ARCHITECTURE_EXCEPTIONS.md` returned no results.
  - `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` contains only three Atlas Shell exceptions; none covers TaskTracker proxy responses.
  - `Sprint05/30_implementation/implementation_notes.md`: does not mention or justify the non-Dataset proxy shape. Section §7 documents `PUT /tasks/{task_id}/labels` mechanics but says nothing about the response contract.
  - `00_Blueprint/Rule_System.md §8`: "A single approved deviation from a registered rule warrants an EXCEPTION record regardless of reuse, because the absence of that record makes the violation invisible to future agents."
- **rule_refs:** R-CON-BP-04, R-OPS-BP-01
- **contract_refs:** `02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md`
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 352–425)
- **why_it_matters:** Without a formal exception record, the deviation is institutionally invisible. Future agents will see bespoke shapes and cannot determine whether they are intentional accepted trade-offs or undetected violations. The LabelEngine design artifact explicitly expected transformation; the sprint notes do not address the gap. This is precisely the failure mode R-PRO-BP-02 and the exception record requirement are designed to prevent.
- **recommended_action:** Create `/home/linse/Prod/Atlas/03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`. Register at minimum one exception for "label picker interaction endpoints return LabelEngine-native shapes," including: which rule is deviated from, the rationale (e.g., label picker is an interactive widget that needs typed records, not table rows), any constraint (e.g., frontend must not assume undeclared fields beyond what LabelEngine documents), and a resolution criterion.
- **confidence:** high

---

### F-004 — `labels` Field Embedded in `Dataset` Rows Without Schema Declaration

- **category:** `missing_rule_signal`
- **severity:** medium
- **claim:** `list_tasks` embeds a `labels` array into `Dataset` rows via `fetch_labels_for_tasks` but `labels` is not declared in `TASK_SCHEMA`; the frontend `TaskGroupedList` consumes this field for grouping logic, creating an undeclared payload side-channel.
- **evidence:**
  - `tasks.py:229–233`: `labels_by_task = fetch_labels_for_tasks(conn, task_ids); for r in rows: r["labels"] = labels_by_task.get(r["id"], [])` — appended to rows before `Dataset` construction.
  - `tasks.py:25–33`: `TASK_SCHEMA` has 7 declared columns: `title`, `status`, `priority`, `due_date`, `effort_hours`, `created_at`, `description`. `labels` is absent.
  - `ShellEntry.tsx:1380`: `const primary = task.labels?.[0]?.name;` — frontend reads `labels` from the row for group-header logic in `TaskGroupedList`.
  - `Sprint05/implementation_notes.md:21`: "Labels are still embedded in `TaskRow.labels` (backend unchanged) and are still used by `TaskGroupedList` for grouping logic" — confirms intentional design.
  - `UI_Data_Contract.md §2`: "row fields not declared in schema are ignored" — by rendering primitives only. The contract is silent on whether application frontend logic may consume undeclared row fields.
- **rule_refs:** R-CON-BP-01, R-CON-BP-03 (spirit; no rule directly addresses this pattern)
- **contract_refs:** `02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md` (§2)
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 229–246)
  - `03_Application/TaskTracker/src/ShellEntry.tsx` (lines 1376–1393)
- **why_it_matters:** Atlas currently has no rule stating whether undeclared `Dataset` row fields may be used as application-logic side-channels. The pattern works today but: a schema refactor that drops `labels` from the row will silently break frontend grouping with no contract or type-system signal; the intent is not legible from the `TASK_SCHEMA` declaration alone; and implementations across applications will diverge without a governance position. This is a governance gap, not a clear violation.
- **recommended_action:** Option 1: Declare `labels` in `TASK_SCHEMA` with a new column type (e.g., `"json"`), making the field an explicit contract element. Option 2: Replace the embedded-labels grouping approach with a dedicated `GET /tasks?view=grouped` endpoint that returns properly structured per-group `Dataset`s. Raise the underlying governance gap (MS-001 below) for an Atlas rule decision.
- **confidence:** high

---

### F-005 — `_resolve_or_create_label` Double-Commit Leaves Label Uniqueness Model Undeclared in Contract

- **category:** `verification_required`
- **severity:** medium
- **claim:** `service.py`'s `_resolve_or_create_label` commits a new label insert before `attach_label` commits the `object_labels` row, creating a race window that can produce duplicate label rows; the component contract does not declare whether uniqueness is guaranteed or best-effort.
- **evidence:**
  - `service.py:354–383`: `_resolve_or_create_label` calls `conn.commit()` at line 382 (new label insert path). `attach_label` at lines 110–141 calls `conn.commit()` a second time at line 134.
  - `implementation_notes.md §_resolve_or_create_label and transaction boundaries`: "A race between two concurrent requests for the same label name could result in two label rows being created." Notes classify this as low probability and consistent with non-goals.
  - `architecture.json contracts.invariants`: no invariant about label name uniqueness. Duplicates on direct `POST /api/labels` are described as allowed ("Duplicates by name are allowed unless the application enforces uniqueness via the case-insensitive lookup" — `schema.sql` comment line 10).
  - No unique index on `lower(name)` in `schema.sql`.
- **rule_refs:** R-CON-BP-03
- **affected_artifacts:**
  - `02_Platform/LabelEngine/app/service.py` (lines 354–383, 110–141)
  - `02_Platform/LabelEngine/Spint01- First labels/20_design/architecture.json`
- **why_it_matters:** The label uniqueness model (best-effort on attach, not guaranteed) is stated only in implementation notes, not in the component contract. Consumers (TaskTracker) cannot determine from the architecture artifact alone what uniqueness guarantees they may rely on. This is a contract completeness gap (R-CON-BP-02) rather than a correctness bug, since the notes document the design intent.
- **recommended_action:** Add one sentence to `architecture.json → contracts.invariants`: "Label name uniqueness on the attach path is best-effort (case-insensitive match before insert); duplicate names can arise under concurrent attach requests or via direct POST /api/labels. No hard uniqueness constraint is enforced in v1." This converts an implementation note into a declared contract invariant.
- **confidence:** medium

---

### F-006 — LabelEngine Tests Are All Empty Stubs

- **category:** `likely_orphaned`
- **severity:** low
- **claim:** All three LabelEngine test files contain only TODO comments; no executable tests exist despite the sprint design artifact specifying 17 test cases.
- **evidence:**
  - `tests/test_labels.py`: 6 TODO lines, no test functions.
  - `tests/test_objects.py`: 8 TODO lines, no test functions.
  - `tests/test_groups.py`: 8 TODO lines, no test functions.
  - `sprint_state.json: current_state = "AWAITING_HUMAN_REVIEW"` — implementation is considered complete.
  - `architecture.json deferrals.test_writer`: 17 test cases specified.
- **affected_artifacts:**
  - `02_Platform/LabelEngine/tests/test_labels.py`
  - `02_Platform/LabelEngine/tests/test_objects.py`
  - `02_Platform/LabelEngine/tests/test_groups.py`
- **recommended_action:** Invoke the `test_writer` agent on LabelEngine before marking the sprint `SPRINT_COMPLETE`. The 17 specified test cases in `architecture.json deferrals.test_writer` are the authoritative scope.
- **confidence:** high

---

## 4. Likely Orphaned / Residue Inventory

| Artifact | Reason Suspected | Confidence |
|---|---|---|
| `02_Platform/LabelEngine/Spint01- First labels/` (sprint folder with typo) | `database.py:48–53` constructs the schema.sql path via this folder name. On deployments where the sprint folder is not co-deployed, the inline DDL fallback activates silently. The folder is present in the repo and the inline DDL is kept in sync per the notes, so this is a path fragility rather than an orphan. No removal recommended; the typo folder name should be treated as the canonical path. | medium |

No other orphaned artifacts found.

---

## 5. Missing Rule Signals

### MS-001 — No Rule on Undeclared `Dataset` Row Fields Used as Frontend Logic Side-Channels

Atlas has no rule addressing whether application frontends may consume non-schema fields in `Dataset` rows for application-layer logic (as distinct from rendering). `UI_Data_Contract.md §2` says undeclared fields are "silently ignored" — by platform rendering primitives. The TaskTracker pattern of embedding `labels` into rows for client-side grouping is a distinct use case that the contract does not address. Without a rule, applications will make inconsistent choices.

**Locations:** `tasks.py:229–246`, `ShellEntry.tsx:1380`

**Suggested governance gap:** Add a clause to R-CON-BP-04 or create a new rule stating one of: (a) all fields consumed by application frontend logic must be declared in `schema[]`; or (b) non-schema fields are permitted as application side-channels provided they are documented in the endpoint contract.

---

### MS-002 — No Platform Batch Read API Pattern for Multi-Object Label Fetching

LabelEngine's `GET /api/objects/{object_id}/labels` is per-object. Fetching labels for a list view of 25 tasks would require 25 sequential HTTP calls. TaskTracker bypassed the API entirely (F-001) as a consequence. This pattern will recur for any application consuming labels in list views.

**Locations:** `tasks.py:72–95`, `LabelEngine/app/routers/objects.py:91–96`

**Suggested governance gap:** Atlas needs a standard for batch read APIs in platform services. Either: (a) platform services that will be consumed by list-view applications must expose a batch read endpoint; (b) a formal exception pattern must exist for direct DB read access for batch performance use cases. Without this, each application will independently implement workarounds.

---

## 6. Remediation Plan

### Immediate (High — Rule and Contract Violations)

1. Create `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`. Register a formal exception for label proxy endpoints returning non-Dataset shapes (covers F-002 and F-003). If the intent is to eventually transform them to Dataset, state that as the resolution criterion.

2. Resolve F-001: either add `POST /api/objects/labels/batch` to LabelEngine and call it from `fetch_labels_for_tasks` via HTTP, or register a formal exception for direct DB read access citing N+1 latency as the rationale with a read-only, schema-track constraint.

### Simplifications (Medium)

3. Add `labels` to `TASK_SCHEMA` with a declared type, or replace the embedded-labels grouping approach with a proper grouped endpoint. Eliminates the hidden side-channel (F-004).

4. Add one invariant sentence to `architecture.json → contracts.invariants` declaring the label uniqueness model (F-005). No code change required.

### Removals

5. No removals needed. The sprint-folder typo is a path fragility to accept and document, not a removable artifact.

### Formal Exception Records to Create

6. `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md` — does not exist. Must be created to cover F-002/F-003 and optionally F-001 if direct DB access is retained.

### Rule and Governance Clarifications

7. MS-001: Add a clause to R-CON-BP-04 addressing non-schema `Dataset` row fields consumed by application frontend logic.
8. MS-002: Define a batch read API pattern for platform services, or define a formal exception pattern for direct DB access in batch-read contexts.
