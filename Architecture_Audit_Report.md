# Architecture Audit Report

**Date:** 2026-03-24
**Auditor:** Architecture Auditor (atlas-architecture-auditor)
**Scope:** Full structural audit of all implemented components against Atlas governance rules, contracts, and architectural boundaries.

---

## 1. Executive Summary

The Atlas implementation is largely coherent. The four-layer model is respected, the UI Data Contract (`R-CON-BP-04`) is consistently applied across the majority of endpoints, and the platform boundary is properly maintained with the known exception pattern recorded in `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md`. The formal exception register (`R-EXC-PC-01`, `R-EXC-PC-02`, `R-EXC-PC-03`) correctly covers all detected Atlas Shell deviations.

The most structurally significant finding is that seven FoodTracker endpoints return **ad hoc response shapes that are not `Dataset` or `ApiError` and have no formal exception record**: `GET /food/validate`, `GET /food/entries/{id}`, `GET /food/standards`, `GET /food/day`, `POST /food/standards/{id}/log`, `PATCH /food/entries/{id}/standard`, and `DELETE /food/standards/{id}/today-instance`. These collectively constitute contract violations. The Chronicle calendar endpoints also return bespoke shapes; these are partially justified in a code comment but without a formal exception record.

A second structural issue is that the `platform_contracts` Python package defines `ColumnType` as a closed `Literal` type, which is narrower than the contract specification in `R-CON-BP-04` (which explicitly permits `string` extensibility). This creates a silent divergence between the Python and TypeScript contract expressions.

The `sprint_conventions.md` for FoodTracker exists but is underspecified — it acknowledges historic deviations without stating which canonical stages are overridden or providing the rationale required by `R-PRO-BP-01 §7`.

Outside of these findings, the system is structurally sound. Dependency direction is correct (applications import platform, platform does not import applications — excepting the formally excepted Shell pattern). No domain logic was found in platform components. No orphaned routes or unreachable handlers were identified.

### Finding Counts

| Category | Critical | High | Medium | Low | Total |
|---|---|---|---|---|---|
| `contract_violation` | 0 | 4 | 0 | 0 | 4 |
| `exception_missing_record` | 0 | 2 | 1 | 0 | 3 |
| `rule_violation` | 0 | 1 | 0 | 0 | 1 |
| `missing_rule_signal` | 0 | 0 | 2 | 0 | 2 |
| `verification_required` | 0 | 0 | 1 | 0 | 1 |
| `likely_orphaned` | 0 | 0 | 0 | 1 | 1 |
| **Total** | **0** | **7** | **4** | **1** | **12** |

### Top 5 Recommended Actions

1. Register formal exception records for FoodTracker Sprint 04 non-Dataset endpoints (`GET /food/standards`, `GET /food/day`, `PATCH /food/entries/{id}/standard`, `POST /food/standards/{id}/log`, `DELETE /food/standards/{id}/today-instance`) in `ARCHITECTURE_EXCEPTIONS.md` within the FoodTracker application, citing the named-contract rationale from `architecture.json`.
2. Register a formal exception record for Chronicle calendar endpoints (`GET /calendar/sources`, `GET /calendar/events`, `PATCH /calendar/sources`) covering their non-Dataset shapes, citing the heatmap/event semantics rationale.
3. Correct `platform_contracts/contracts.py` `ColumnType` from a closed `Literal` to `str` (or an open union) to match the extensible definition in `R-CON-BP-04`.
4. Rewrite `FoodTracker/sprint_conventions.md` to explicitly state which canonical stages are overridden and why, satisfying the `R-PRO-BP-01 §7` requirements (currently it only says "some older sprints don't follow the new rule").
5. Register a formal exception record for `GET /food/validate` and `GET /food/entries/{id}` (non-Dataset endpoints), or convert `GET /food/entries/{id}` to return a single-row `Dataset` to eliminate the deviation.

---

## 2. Audit Basis

### Rules Consulted

| Rule ID | Title | Canonical Source |
|---|---|---|
| R-CON-BP-01 | Architecture as AI Interface | `.claude/rules/R-CON-BP-01_architecture_as_ai_interface.md` |
| R-CON-BP-02 | Contracts and Boundaries | `.claude/rules/R-CON-BP-02_contracts_and_boundaries.md` |
| R-CON-BP-03 | Durable State Must Be Explicit | `.claude/rules/R-CON-BP-03_no_hidden_state.md` |
| R-CON-BP-04 | UI Data Contract | `.claude/rules/R-CON-BP-04_ui_data_contract.md` |
| R-CON-BP-05 | Atlas Rule System | `.claude/rules/R-CON-BP-05_rule_system.md` |
| R-OPS-BP-01 | Surface Violations Explicitly | `.claude/rules/R-OPS-BP-01_surface_violations.md` |
| R-OPS-BP-02 | Security: Least Privilege | `.claude/rules/R-OPS-BP-02_security.md` |
| R-PRO-BP-01 | Sprint Process Contract | `.claude/rules/R-PRO-BP-01_sprint_process.md` |
| R-CON-PL-01 | Platform Boundary | `.claude/rules/R-CON-PL-01_platform_boundary.md` |
| R-CON-PL-02 | Dependency Direction | `.claude/rules/R-CON-PL-02_dependency_direction.md` |

### Exception Records Inspected (not re-reported as violations)

| Exception ID | Covers | Location |
|---|---|---|
| R-EXC-PC-01 | Application nav content in Shell | `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` |
| R-EXC-PC-02 | Shell lazy imports Application layer | `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` |
| R-EXC-PC-03 | ShellErrorBoundary `request_id` unspecified for client errors | `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` |

### Contracts Consulted

- `R-CON-BP-04` (UI Data Contract — `Dataset`, `ApiError`, Chart Mapping types) — `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- Python expression: `02_Platform/packages/platform_contracts/contracts.py`
- TypeScript expression: `02_Platform/UI/react/src/api/types.ts`
- `00_Blueprint/SharedViews/chronicle.sql` — shared cross-application calendar view

### Components and Files Inspected

**Blueprint:**
- `00_Blueprint/RULE_REGISTRY.md`
- `00_Blueprint/Atlas_Manifest.md`
- `00_Blueprint/SharedViews/chronicle.sql`

**Platform:**
- `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md`
- `02_Platform/Atlas_Shell/src/types.ts`
- `02_Platform/Atlas_Shell/src/registry/AppRegistry.ts`
- `02_Platform/Atlas_Shell/src/shell/Router.tsx`
- `02_Platform/Atlas_Shell/src/shell/ShellLayout.tsx` (not read, no findings expected)
- `02_Platform/Atlas_Shell/src/shell/main.tsx`
- `02_Platform/Atlas_Shell/src/index.ts`
- `02_Platform/packages/platform_contracts/contracts.py`
- `02_Platform/packages/platform_contracts/__init__.py`
- `02_Platform/packages/platform_errorhandling/api_response.py`
- `02_Platform/packages/platform_errorhandling/__init__.py`
- `02_Platform/UI/react/src/api/types.ts`

**Applications:**
- `03_Application/WorkoutTracker/backend/main.py`
- `03_Application/WorkoutTracker/backend/routers/workout.py`
- `03_Application/TaskTracker/backend/routers/tasks.py`
- `03_Application/FoodTracker/backend/main.py`
- `03_Application/FoodTracker/backend/routers/food.py`
- `03_Application/FoodTracker/backend/routers/report.py`
- `03_Application/FoodTracker/backend/routers/entries.py`
- `03_Application/FoodTracker/backend/routers/standards.py`
- `03_Application/FoodTracker/src/ShellEntry.tsx`
- `03_Application/FoodTracker/src/StandardsPage.tsx`
- `03_Application/FoodTracker/sprint_conventions.md`
- `03_Application/Chronicle/backend/routers/calendar.py`
- `03_Application/Chronicle/Sprint02_Swimlanes and Selector.md/90_meta/sprint_state.json`
- `03_Application/FoodTracker/Sprint04_Standard Dishes/90_meta/sprint_state.json`
- Various `shellConfig.ts` files for all four applications

### Exclusions and Uncertainty Boundaries

- `WorkoutTracker/00_requirements/ui-reference/` — treated as reference material, not live implementation
- Node modules (`node_modules/`) — excluded from all analysis
- Application-level SQL migration files — inspected for presence only; schema correctness not audited
- Application frontend pages not directly named in a route discrepancy — not individually read (partial coverage)
- The `02_Platform/MCPGateway` component was identified but not audited; it has no UI-facing endpoints and no registered rules that apply to it specifically

---

## 3. Findings

### F-01 — FoodTracker Sprint 04 endpoints return non-Dataset shapes without exception records

- **category:** `contract_violation`
- **severity:** high
- **claim:** Seven FoodTracker endpoints introduced in Sprint 04 return bespoke response shapes (`DayPagePayload`, `StandardsPagePayload`, `EntryDetail`, `StandardToggleResult`, HTTP 204, or HTTP 201 with a bare object) rather than `Dataset` or `ApiError`, with no formal exception record.
- **evidence:**
  - `GET /api/food/day` returns `{"today_entries": [...], "standards": [...]}` — a custom nested structure, not `Dataset`.
  - `GET /api/food/standards` returns `{"standards": [...], "today_instances": [...]}` — a custom nested structure.
  - `POST /api/food/standards/{id}/log` (HTTP 201) returns a bare `EntryDetail` dict — not `Dataset`.
  - `PATCH /api/food/entries/{id}/standard` returns `{"id": ..., "standard": ...}` — not `Dataset` and not `ApiError`.
  - `DELETE /api/food/standards/{id}/today-instance` returns HTTP 204 with no body — not `Dataset`.
  - None of these are registered in `ARCHITECTURE_EXCEPTIONS.md` or any formal exception artifact.
  - Sprint 04 `sprint_state.json` notes these as "scaffold-only observations, acknowledged risks, not blockers" — but that is a design-review note, not a formal exception record.
  - `R-CON-BP-04` states: "Any Atlas endpoint or interface intended to supply data for UI rendering must return a payload defined by an explicit stable UI contract." The rule permits non-Dataset shapes only when "the alternate shape is defined as an explicit stable contract."
- **rule_refs:** R-CON-BP-04 §Core Rule, §Default-First Rule, §5 Canonical Producer Rule
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `03_Application/FoodTracker/backend/routers/standards.py` (lines 139–205, 208–247, 250–305, 308–391, 394–440)
- **why_it_matters:** These are UI-facing endpoints consumed directly by `StandardsPage.tsx`. Without a formal exception record, future agents cannot distinguish intentional design decisions from silent contract violations. The shapes themselves may be valid (they fit the "detail object with nested structure" permitted deviation class), but they require explicit stable contracts to be machine-legible.
- **recommended_action:** Create `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md` and register one or more exception records (type `EXCEPTION`, scope `APPLICATION`) covering these endpoints. Each entry should cite the named-contract rationale (e.g., "DayPagePayload is a composed dashboard payload whose primary content is a nested structure that does not fit Dataset semantics") and reference the `architecture.json` named contracts section.
- **confidence:** high

---

### F-02 — `GET /api/food/entries/{id}` returns a bare `EntryDetail` object without exception record

- **category:** `contract_violation`
- **severity:** high
- **claim:** The `get_entry` endpoint returns a bare `EntryDetail` dict (not `Dataset`, not `ApiError`) with no formal exception record.
- **evidence:**
  - `03_Application/FoodTracker/backend/routers/entries.py` line 390: `return JSONResponse(content=_serialise_entry_detail(dict(row)))` — returns a bare object with no `meta`, `schema`, or `rows` wrapper.
  - The shape is not `Dataset`. It is not registered as a named contract in any exception file.
  - `R-CON-BP-04` §Define another explicit UI contract when the payload is "a detail object with nested structure" — this is a permitted category but requires an explicit stable contract definition, which does not exist here.
  - In contrast, `GET /api/food/entries` and `PUT /api/food/entries/{id}` both return `Dataset`. The GET-by-id endpoint breaks consistency within the same router.
- **rule_refs:** R-CON-BP-04 §Core Rule, §Define another explicit UI contract
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `03_Application/FoodTracker/backend/routers/entries.py` (lines 363–390)
  - `03_Application/FoodTracker/src/EntryDetailPage.tsx` (consumer — not read, but implied)
- **why_it_matters:** This is a silent bespoke shape for a UI-facing endpoint. No contract document governs what `EntryDetail` contains, which fields are stable, or what consumers can rely on. This creates invisible coupling between the producer and the consumer.
- **recommended_action:** Either (a) convert to return a single-row `Dataset` (consistent with how `TaskTracker` handles single-row results), or (b) formally register `EntryDetail` as an explicit named contract with stable fields and add an exception record.
- **confidence:** high

---

### F-03 — `POST /api/food/validate` returns `{"preview": ...}` — a bespoke shape without exception record

- **category:** `contract_violation`
- **severity:** high
- **claim:** The `POST /api/food/validate` endpoint returns `{"preview": <normalised_dict>}` — a bespoke shape not conforming to `Dataset` or `ApiError` — with no formal exception record.
- **evidence:**
  - `03_Application/FoodTracker/backend/routers/food.py` line 368: `return JSONResponse(content={"preview": normalised})`.
  - No exception record exists for this shape.
  - `R-CON-BP-04` permits non-Dataset shapes for "a form definition or submission result" — but requires the alternate shape to be "defined as an explicit stable contract."
  - The `ShellEntry.tsx` consumer (line 112) calls this endpoint and accesses `res.preview` directly — coupling to an undocumented shape.
- **rule_refs:** R-CON-BP-04 §Core Rule, §Default-First Rule
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `03_Application/FoodTracker/backend/routers/food.py` (line 361–368)
  - `03_Application/FoodTracker/src/ShellEntry.tsx` (line 112–119, consumer)
- **why_it_matters:** This is a validation-preview endpoint — its shape is plausibly a "form submission result" that does not fit Dataset. But without a formal contract definition, the `preview` field is unstable and invisible to future agents.
- **recommended_action:** Define `PreviewPayload` as an explicit named contract (documented in `ARCHITECTURE_EXCEPTIONS.md` or a named-contract file) and register an exception record. The shape is small and stable enough to document formally.
- **confidence:** high

---

### F-04 — Chronicle calendar endpoints return bespoke shapes; exception comment exists in code but no formal record

- **category:** `exception_missing_record`
- **severity:** high
- **claim:** The Chronicle calendar endpoints (`GET /calendar/sources`, `GET /calendar/events`, `PATCH /calendar/sources`) return custom list/object shapes without `Dataset` wrapping, acknowledged in a docstring comment but without a formal exception record.
- **evidence:**
  - `03_Application/Chronicle/backend/routers/calendar.py` lines 1–24: module docstring states "No Dataset used — CalendarEventView endpoints use the CalendarEventViewRow named contract declared in 20_design/architecture.json. This is a controlled exception to the Atlas UI Data Contract."
  - `GET /calendar/sources` returns a plain JSON list, not `Dataset`.
  - `GET /calendar/events` returns a plain JSON list, not `Dataset`.
  - `PATCH /calendar/sources` returns `{"application": ..., "source_label": ..., "selected": ...}`.
  - There is no corresponding entry in `ARCHITECTURE_EXCEPTIONS.md` (the shell's exception file) or any Chronicle-level exception file.
  - A code comment is not a formal exception record as defined by R-CON-BP-05 §8.
- **rule_refs:** R-CON-BP-04 §Core Rule; R-CON-BP-05 §8 (EXCEPTION records require formal registration)
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `03_Application/Chronicle/backend/routers/calendar.py` (entire file)
- **why_it_matters:** The deviation is almost certainly justified (heatmap/calendar semantics do not fit paginated Dataset), but relying on a docstring comment for exception governance means future agents will see apparent contract violations with no registered exception to consult.
- **recommended_action:** Create `03_Application/Chronicle/ARCHITECTURE_EXCEPTIONS.md` and register an exception record (type `EXCEPTION`, scope `APPLICATION`, exception_to `R-CON-BP-04`) covering the three calendar endpoints. The rationale is already well-expressed in the docstring — it just needs to be in the correct artifact.
- **confidence:** high

---

### F-05 — `WorkoutTracker` `GET /exercises/history` returns a bespoke shape without exception record

- **category:** `contract_violation`
- **severity:** high
- **claim:** The `exercise_history` endpoint returns `{"rows": [...]}` — a bespoke shape that is neither `Dataset` nor `ApiError` — with no formal exception record.
- **evidence:**
  - `03_Application/WorkoutTracker/backend/routers/workout.py` line 360: `return JSONResponse(content={"rows": rows})`.
  - No exception record exists for this shape anywhere in the WorkoutTracker application.
  - No ARCHITECTURE_EXCEPTIONS.md file exists at `03_Application/WorkoutTracker/`.
  - All other WorkoutTracker endpoints correctly return `Dataset` via `dataset_response()`.
  - The `{"rows": [...]}` shape does not include `meta`, `schema`, or `id` per row — it is a partial Dataset-like shape without the contract structure.
- **rule_refs:** R-CON-BP-04 §Core Rule, §5 Canonical Producer Rule
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `03_Application/WorkoutTracker/backend/routers/workout.py` (lines 337–360)
- **why_it_matters:** This is a raw data endpoint returning exercise history rows without schema declaration. Any frontend consumer coupling to this shape has no contract to rely on. The shape cannot be rendered by platform UI primitives (TableView, BarChart) because they require `Dataset` structure.
- **recommended_action:** Either (a) wrap the response in a proper `Dataset` with a declared schema (e.g., with keys `workout_date`, `set1_reps`–`set5_reps`, `weight_kg`), or (b) if the raw shape is intentional for a chart consumer that needs the pre-aggregation rows, register a formal exception record.
- **confidence:** high

---

### F-06 — Python `platform_contracts.ColumnType` is a closed `Literal`, narrower than the `R-CON-BP-04` contract specification

- **category:** `rule_violation`
- **severity:** high
- **claim:** The Python expression of the UI Data Contract defines `ColumnType` as a closed `Literal["string", "number", "date", "boolean", "enum"]`, diverging from `R-CON-BP-04` which explicitly defines `ColumnType` as `str` (extensible) with the comment "extensible."
- **evidence:**
  - `02_Platform/packages/platform_contracts/contracts.py` line 9: `ColumnType = Literal["string", "number", "date", "boolean", "enum"]`
  - `R-CON-BP-04` §1.2 Python specification states: `ColumnType = str` with comment "open — backend declares any column type string; frontend renders what is declared."
  - The TypeScript expression (`02_Platform/UI/react/src/api/types.ts` line 5) is also a closed union without the extensible `string` escape, but `R-CON-BP-04` §1.1 shows it as `| string // extensible`.
  - The `platform_contracts` CLAUDE.md states "this is a contract, not a utility library" and "import from here in every router," making this the authoritative backend source. The canonical contract (`R-CON-BP-04`) explicitly requires extensibility.
- **rule_refs:** R-CON-BP-04 §1.2 (Python backend canonical types)
- **contract_refs:** `.claude/rules/R-CON-BP-04_ui_data_contract.md`
- **affected_artifacts:**
  - `02_Platform/packages/platform_contracts/contracts.py` (line 9)
- **why_it_matters:** If an application needs to declare a custom column type (e.g., `"currency"` or `"percentage"`), the current `Literal` definition will cause a Pydantic validation error at runtime. This silently restricts a capability that the contract explicitly intends to leave open. The Python canonical spec in `R-CON-BP-04` uses `ColumnType = str`.
- **recommended_action:** Change `ColumnType = Literal["string", "number", "date", "boolean", "enum"]` to `ColumnType = str` in `contracts.py` to match the canonical Python specification in `R-CON-BP-04 §1.2`.
- **confidence:** high

---

### F-07 — `FoodTracker/sprint_conventions.md` does not satisfy `R-PRO-BP-01 §7` requirements

- **category:** `rule_violation`
- **severity:** medium
- **claim:** The FoodTracker `sprint_conventions.md` file exists but does not meet the structural requirements of `R-PRO-BP-01 §7`: it does not explicitly state which canonical stages are overridden, does not state the rationale, and its content is a single informal sentence.
- **evidence:**
  - `03_Application/FoodTracker/sprint_conventions.md` full content: "Some of the older Sprints in this app do not follow the new rule. This deviation is harmless and can be ignored."
  - `R-PRO-BP-01 §7` requires a sprint conventions file to: state explicitly which canonical stages or rules it overrides; state the rationale; be checked by the orchestrator before applying canonical stage requirements.
  - The file names no specific stages, provides no rationale, and does not declare an override — it only makes a retrospective observation about old sprints.
  - Sprint 04 `sprint_state.json` notes the convention correctly ("FoodTracker sprint family convention: 10_specs layer is skipped; reviewer-specs-readiness is not invoked") but this is in a sprint artifact, not in the conventions file.
- **rule_refs:** R-PRO-BP-01 §7 (Per-Application Sprint Conventions)
- **affected_artifacts:**
  - `03_Application/FoodTracker/sprint_conventions.md`
- **why_it_matters:** The sprint orchestrator is required to check this file before applying canonical stage requirements. As written, it provides no actionable governance — an orchestrator reading it cannot determine what deviations are permitted. The actual convention (skip `10_specs/` and `reviewer-specs-readiness`) is only expressed in sprint_state.json notes.
- **recommended_action:** Rewrite `sprint_conventions.md` to declare: (1) the 10_specs stage is skipped for all FoodTracker sprints; (2) `reviewer-specs-readiness` is not invoked; (3) the designer reads `00_input/draft.md` directly; (4) the rationale. This satisfies R-PRO-BP-01 §7 and makes the convention machine-legible to the orchestrator.
- **confidence:** high

---

### F-08 — `platform_contracts` package name does not match `platform_errorhandling` naming pattern; package CLAUDE.md file header misnames it

- **category:** `missing_rule_signal`
- **severity:** medium
- **claim:** The `platform_contracts` package `contracts.py` file has a header comment that says `# platform_errorhandling/contracts.py`, misidentifying its own package. This is evidence that there is no rule governing internal file header naming conventions for platform packages.
- **evidence:**
  - `02_Platform/packages/platform_contracts/contracts.py` line 1: `# platform_errorhandling/contracts.py` — the file path comment names the wrong package.
  - The actual package directory is `platform_contracts`, not `platform_errorhandling`.
  - No Atlas rule governs internal file header comment format for platform packages.
- **rule_refs:** R-CON-BP-01 (machine legibility), R-CON-BP-02 (explicit contracts)
- **affected_artifacts:**
  - `02_Platform/packages/platform_contracts/contracts.py` (line 1)
- **why_it_matters:** The incorrect file path comment is a low-risk naming error, but its presence — and the absence of a rule that would prevent it — is a signal that Atlas lacks a governing rule for implementation-level file header conventions. A future agent reading this file would have a misleading path reference.
- **recommended_action:** Correct the file header comment to `# platform_contracts/contracts.py`. Separately, consider whether a rule governing platform package internal file headers is warranted (see Section 5).
- **confidence:** high

---

### F-09 — Duplicate `_err`/`_api_err`/`_api_error` error helper functions across FoodTracker routers

- **category:** `missing_rule_signal`
- **severity:** medium
- **claim:** Three separate FoodTracker routers (`food.py`, `entries.py`, `standards.py`, `report.py`, `calendar.py`) each define a local `_err`/`_api_err`/`_api_error` helper that builds an `ApiError`-shaped dict, rather than using the platform-provided `api_error()` from `platform_errorhandling`.
- **evidence:**
  - `03_Application/FoodTracker/backend/routers/food.py` line 65–74: local `_err()` function
  - `03_Application/FoodTracker/backend/routers/entries.py` line 43–52: local `_err()` function
  - `03_Application/FoodTracker/backend/routers/standards.py` line 33–44: local `_api_err()` function
  - `03_Application/FoodTracker/backend/routers/report.py` line 86–94: local `_err()` function (inside `_parse_report_params`)
  - `03_Application/Chronicle/backend/routers/calendar.py` line 49–57: local `_api_error()` function
  - All of these produce `ApiError`-shaped dicts directly rather than calling `platform_errorhandling.api_error()`.
  - In contrast, `WorkoutTracker` and `TaskTracker` correctly import and use `from platform_errorhandling import api_error`.
  - There is no Atlas rule stating that application routers must use the platform `api_error()` function.
- **rule_refs:** R-CON-PL-01 (platform provides capability), R-CON-BP-02 (prefer explicit contracts over inferred behavior)
- **affected_artifacts:**
  - `03_Application/FoodTracker/backend/routers/food.py`
  - `03_Application/FoodTracker/backend/routers/entries.py`
  - `03_Application/FoodTracker/backend/routers/standards.py`
  - `03_Application/FoodTracker/backend/routers/report.py`
  - `03_Application/Chronicle/backend/routers/calendar.py`
- **why_it_matters:** The platform already provides `api_error()` as a reusable capability. The local variants are mostly equivalent but differ in signature and defaults. This inconsistency suggests Atlas lacks a formal rule requiring applications to use platform error utilities when they exist. The inconsistency is not a contract violation (the output shapes are the same), but it is a boundary drift pattern.
- **recommended_action:** In the short term, replace local `_err`/`_api_err` helpers in the affected routers with calls to `platform_errorhandling.api_error()` (noting that `standards.py` uses a slightly different call signature). In the long term, consider adding a platform-component rule for `platform_errorhandling` stating that applications must use its `api_error()` function rather than reimplementing the error envelope locally.
- **confidence:** high

---

### F-10 — `Chronicle Sprint02` sprint folder has a `.md` extension in the folder name

- **category:** `exception_missing_record`
- **severity:** medium
- **claim:** The Chronicle Sprint02 folder is named `Sprint02_Swimlanes and Selector.md` — with a `.md` extension appended to the folder name — violating the canonical sprint folder naming convention in `R-PRO-BP-01 §1`.
- **evidence:**
  - Observed path: `03_Application/Chronicle/Sprint02_Swimlanes and Selector.md/90_meta/sprint_state.json`
  - `R-PRO-BP-01 §1` states: "Sprint folder: `Sprint<N>_<Title>/` — no file extension, no trailing slash in references."
  - `R-CON-BP-05 §6` states: "PROCESS rules apply prospectively." The prospective application date for `R-PRO-BP-01` is 2026-03-24.
  - This sprint folder was created before 2026-03-24 (based on the git log showing `feat: add Chronicle Sprint02` at commit `10c4492`, before the current date). Therefore, this may be covered by the prospective-only application clause.
- **rule_refs:** R-PRO-BP-01 §1, R-CON-BP-05 §6
- **affected_artifacts:**
  - `03_Application/Chronicle/Sprint02_Swimlanes and Selector.md/` (folder)
- **why_it_matters:** If the sprint was created before 2026-03-24, this is not a violation under R-CON-BP-05 §6. However, the current `sprint_state.json` shows `DRAFT_READY` — meaning this sprint has not been started and will be worked on after the prospective date. A future agent opening this sprint should not rename the folder mid-sprint, but the naming should be corrected before design work begins.
- **recommended_action:** Rename the folder to `Sprint02_Swimlanes and Selector` before initiating design work. Record the correction in `orchestrator_log.md` if one exists. Given the retrospective-only protection of R-CON-BP-05 §6 applies only to completed artifacts, this is a low-priority correction before the sprint advances.
- **confidence:** medium

---

### F-11 — `FoodTracker/tools.py` reachability unknown

- **category:** `verification_required`
- **severity:** medium
- **claim:** `03_Application/FoodTracker/tools.py` exists at the application root and its purpose and reachability are not clear from the inspected artifacts.
- **evidence:**
  - File `03_Application/FoodTracker/tools.py` was identified in the glob scan but was not read.
  - The FoodTracker `backend/main.py` does not reference it. No import from this file was found in any inspected router.
  - The filename `tools.py` at the application root is unusual and does not correspond to any sprint artifact or platform registration.
- **affected_artifacts:**
  - `03_Application/FoodTracker/tools.py`
- **recommended_action:** Read the file and determine whether it is: (a) a utility used by some deployment or CI script (acceptable); (b) an orphaned artifact with no consumers (should be removed); or (c) a tool providing MCP tool definitions (should be documented in the application's CLAUDE.md).
- **confidence:** low (file not read)

---

### F-12 — `WorkoutTracker/00_requirements/ui-reference/` — large reference UI bundle in application source tree

- **category:** `likely_orphaned`
- **severity:** low
- **claim:** `03_Application/WorkoutTracker/00_requirements/ui-reference/` contains a full React component library (shadcn/ui) as application source files that are not part of the implemented application.
- **evidence:**
  - Glob scan shows ~50+ `.tsx` files in `03_Application/WorkoutTracker/00_requirements/ui-reference/src/app/components/ui/` including `sidebar.tsx`, `carousel.tsx`, `chart.tsx`, `dialog.tsx`, etc.
  - These are shadcn/ui components, not WorkoutTracker application components.
  - `WorkoutTracker/src/ShellEntry.tsx` and `shellConfig.ts` are the actual application entry points; they do not import from `00_requirements/`.
  - The `00_requirements/` folder appears to contain a Figma-to-code design reference export that was used during initial design but is not part of the running application.
- **affected_artifacts:**
  - `03_Application/WorkoutTracker/00_requirements/ui-reference/` (entire directory)
- **why_it_matters:** This directory adds significant noise to the repository and could confuse future agents that glob for TSX files in the application. It is not dangerous, but it contributes to R-CON-BP-01 legibility concerns.
- **recommended_action:** If this reference material is no longer needed, remove it. If it must be retained for design documentation purposes, move it outside the `src/` tree and add a README noting it is reference-only, not live application code.
- **confidence:** medium

---

## 4. Likely Orphaned / Residue Inventory

| Path | Reason Suspected | Confidence |
|---|---|---|
| `03_Application/FoodTracker/tools.py` | Exists at application root with no evident consumer in `main.py` or any router | low |
| `03_Application/WorkoutTracker/00_requirements/ui-reference/` | Design-reference shadcn/ui component library not imported by live application code | medium |

---

## 5. Missing Rule Signals

### MS-01 — No rule requires applications to use platform error utilities

**Pattern observed:** Multiple application routers (`food.py`, `entries.py`, `standards.py`, `report.py` in FoodTracker; `calendar.py` in Chronicle) define local `_err`/`_api_err` helpers that duplicate the `platform_errorhandling.api_error()` function. Two applications (`WorkoutTracker`, `TaskTracker`) use the platform function correctly.

**Locations:** `03_Application/FoodTracker/backend/routers/food.py`, `entries.py`, `standards.py`, `report.py`; `03_Application/Chronicle/backend/routers/calendar.py`.

**Suggested governance gap:** Atlas has `R-CON-PL-01` stating "Platform provides capability; Applications provide meaning," but no platform-component rule for `platform_errorhandling` states that applications are required to consume `api_error()` rather than reimplementing it. A component-level rule (scope: `PLATFORM_COMPONENT`) for `platform_errorhandling` would close this gap.

---

### MS-02 — No rule governs whether non-Dataset UI endpoints require formal exception records at the application level

**Pattern observed:** Multiple applications have UI-facing endpoints that return non-Dataset shapes. Some acknowledge this in code comments or design documents (Chronicle `calendar.py`, FoodTracker Sprint 04 `architecture.json`). None have formal application-level exception records.

**Locations:** `03_Application/FoodTracker/backend/routers/standards.py`, `entries.py`, `food.py`; `03_Application/WorkoutTracker/backend/routers/workout.py`; `03_Application/Chronicle/backend/routers/calendar.py`.

**Suggested governance gap:** `R-CON-BP-04` requires an "explicit stable contract" for non-Dataset shapes but does not specify the artifact form that contract must take. The formal exception mechanism (`ARCHITECTURE_EXCEPTIONS.md`) exists for platform-level deviations but is not explicitly required or described for application-level deviations. A governance note in `R-CON-BP-04` or `R-CON-BP-05` clarifying that application-level deviations from R-CON-BP-04 require an application-local ARCHITECTURE_EXCEPTIONS.md would make this expectation explicit.

---

## 6. Remediation Plan

### Immediate Fixes (contract violations, high-severity rule violations)

1. **F-06 (high):** Correct `platform_contracts/contracts.py` line 9 — change `ColumnType = Literal[...]` to `ColumnType = str` to match `R-CON-BP-04 §1.2`.

2. **F-05 (high):** Wrap `GET /api/exercises/history` response in a `Dataset` with a declared schema, or register a formal exception record for `WorkoutTracker`.

3. **F-02 (high):** Convert `GET /api/food/entries/{id}` to return a single-row `Dataset`, or formally define and register the `EntryDetail` named contract.

4. **F-03 (high):** Formally register `PreviewPayload` as an explicit named contract for `POST /api/food/validate`, or restructure to return a single-row `Dataset` (less natural for a validation-preview flow).

### Formal Exception Records Needed

5. **F-01 (high):** Create `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md` covering `GET /food/day`, `GET /food/standards`, `POST /food/standards/{id}/log`, `PATCH /food/entries/{id}/standard`, `DELETE /food/standards/{id}/today-instance`.

6. **F-04 (high):** Create `03_Application/Chronicle/ARCHITECTURE_EXCEPTIONS.md` covering `GET /calendar/sources`, `GET /calendar/events`, `PATCH /calendar/sources`.

### Sprint Conventions Correction

7. **F-07 (medium):** Rewrite `03_Application/FoodTracker/sprint_conventions.md` to satisfy `R-PRO-BP-01 §7`: explicitly name the stages skipped, state the rationale, and make it machine-readable for the orchestrator.

### Simplifications and Cleanup

8. **F-09 (medium):** Replace local `_err`/`_api_err` helpers in FoodTracker and Chronicle routers with `platform_errorhandling.api_error()` calls.

9. **F-10 (medium):** Rename `Chronicle/Sprint02_Swimlanes and Selector.md/` folder to remove the `.md` extension before sprint work resumes.

10. **F-08 (medium):** Correct the file header comment in `platform_contracts/contracts.py` line 1.

### Removals (Orphaned Artifacts)

11. **F-12 (low):** Evaluate `WorkoutTracker/00_requirements/ui-reference/` for removal or relocation outside the live source tree.

12. **F-11 (verification needed):** Read and evaluate `FoodTracker/tools.py` to determine whether it is live, orphaned, or undocumented infrastructure.

### Rule Clarifications / New Rules for Atlas Governance

13. **MS-02:** Add a note to `R-CON-BP-04` or `R-CON-BP-05` explicitly requiring that application-level deviations from the UI Data Contract be registered in an application-local `ARCHITECTURE_EXCEPTIONS.md` file. This closes the gap between "explicit stable contract" (as required by R-CON-BP-04) and the absence of a specified artifact form for that contract at the application layer.

14. **MS-01:** Consider adding a `platform_errorhandling` component rule (`SCOPE: PLATFORM_COMPONENT`) stating that applications consuming this package must use `api_error()` for error envelopes rather than reimplementing the ApiError shape locally.
