# Architecture Audit Report

> **Audit Run:** `Tasktracker_Audit_Sprint05`
> **Run Type:** app-specific
> **Agent:** audit_architecture
> **Date:** 2026-04-09

---

## 1. Executive Summary

TaskTracker is structurally sound at the layer and contract level: all data-serving endpoints return `Dataset`, imports respect the downward dependency direction, and the platform errorhandling and contracts packages are used correctly. The Sprint05 implementation — views, pending status, label proxy, set-labels endpoint — is functional and broadly compliant.

Two findings require attention before the next sprint. First, `database.py` contains an inline `init_schema()` that diverges from the canonical `schema.sql` in two ways: it lacks `effort_hours` and does not include `pending` as a valid status. This creates a dual-source-of-truth condition that will silently fail on fresh deployments (constraint violation or missing column). Second, the label proxy endpoints (`/tasks/{task_id}/labels`, `/tasks/labels/search`, etc.) return LabelEngine's raw bespoke shape rather than `Dataset`, and no formal exception record covers this deviation from R-CON-BP-04. A third medium finding concerns the `labels` field being embedded directly into `Dataset` rows by querying the LabelEngine's `labels` schema directly from the application backend — crossing a platform service boundary without going through the LabelEngine API, which is the pattern used for write operations.

Everything else audited is either conformant or covered by existing formal exceptions.

### Finding counts

| Category | critical | high | medium | low | Total |
|---|---|---|---|---|---|
| `rule_violation` | 0 | 1 | 0 | 0 | 1 |
| `contract_violation` | 0 | 0 | 0 | 0 | 0 |
| `exception_missing_record` | 0 | 1 | 0 | 0 | 1 |
| `boundary_drift` | 0 | 0 | 1 | 0 | 1 |
| `missing_rule_signal` | 0 | 0 | 1 | 1 | 2 |
| `likely_orphaned` | 0 | 0 | 0 | 1 | 1 |
| `verification_required` | 0 | 0 | 0 | 0 | 0 |
| **Total** | **0** | **2** | **2** | **2** | **6** |

### Top 5 recommended actions

1. Fix `database.py:init_schema()` to match `schema.sql` — or retire the inline DDL and rely solely on the migration chain. (Rule violation, `R-CON-BP-03`, `R-CON-BP-09`)
2. Record a formal exception for the label proxy endpoints returning non-Dataset shapes, or wrap the LabelEngine responses in `Dataset`. (`R-CON-BP-04`)
3. Document the direct `labels.*` schema query in `fetch_labels_for_tasks` as an accepted boundary pattern, or convert to LabelEngine API calls. (Boundary drift)
4. Clarify in the rule set whether non-UI-rendering proxy endpoints must conform to R-CON-BP-04 — current Atlas rules do not address this case. (Missing rule signal)
5. Remove or update the `CurrentArchitecture/` design artifacts, which reflect Sprint02 state — they will mislead future agents about the current schema and structure.

---

## 2. Audit Basis

### Rules consulted

| Rule ID | File |
|---|---|
| R-CON-BP-01 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-02 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-03 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-04 | `.claude/rules/R-CON-BP.md` + `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md` |
| R-CON-BP-06 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-07 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-09 | `.claude/rules/R-CON-BP.md` |
| R-CON-PL-01 | `.claude/rules/R-CON-PL.md` |
| R-CON-PL-02 | `.claude/rules/R-CON-PL.md` |
| R-CON-AL-01 | `.claude/rules/R-CON-AL.md` |
| R-CON-AL-04 | `.claude/rules/R-CON-AL.md` |
| R-OPS-BP-01 | `.claude/rules/R-OPS-BP.md` |
| R-OPS-BP-02 | `.claude/rules/R-OPS-BP.md` |

### Contracts consulted

- `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md` (v0.3)
- `02_Platform/packages/platform_contracts/contracts.py`

### Formal exceptions inspected

- `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` — R-EXC-PC-01, R-EXC-PC-02, R-EXC-PC-03 (none apply to TaskTracker directly; confirmed no TaskTracker-specific exception file exists)

### Components and files inspected

- `03_Application/TaskTracker/backend/main.py`
- `03_Application/TaskTracker/backend/database.py`
- `03_Application/TaskTracker/backend/routers/tasks.py`
- `03_Application/TaskTracker/src/ShellEntry.tsx`
- `03_Application/TaskTracker/src/shellConfig.ts`
- `03_Application/TaskTracker/schema.sql`
- `03_Application/TaskTracker/migrations/001_init_schema.sql`
- `03_Application/TaskTracker/migrations/002_add_effort.sql`
- `03_Application/TaskTracker/migrations/003_add_pending_status.sql`
- `03_Application/TaskTracker/CurrentArchitecture/architecture.json`
- `03_Application/TaskTracker/CurrentArchitecture/scaffolding.json`
- `03_Application/TaskTracker/Sprint05/00_input/draft.md`
- `03_Application/TaskTracker/Sprint05/30_implementation/implementation_notes.md`
- `03_Application/TaskTracker/Sprint04/30_implementation/implementation_notes.md`
- `03_Application/TaskTracker/CLAUDE.md`

### Exclusions and uncertainty boundaries

- No `ARCHITECTURE_EXCEPTIONS.md` exists for TaskTracker — absence is itself a finding.
- `CurrentArchitecture/` artifacts are Sprint02 vintage; they do not reflect Sprint04 or Sprint05 state. They were reviewed to understand structural intent but not used as conformance targets.
- The LabelEngine API shape (what `GET /api/objects/{id}/labels` actually returns) was inferred from usage in `tasks.py` and `ShellEntry.tsx`; the LabelEngine's own router was not fully audited here.
- CORS configuration (`allow_origin_regex`) was noted; no violation identified (development-only, no production exposure evident in the inspected config).

---

## 3. Findings

---

### F-01 — `database.py` inline schema diverges from canonical `schema.sql`

- **category:** `rule_violation`
- **severity:** high
- **claim:** `database.py:init_schema()` contains a hardcoded DDL block that omits `effort_hours` and restricts `status` to the pre-Sprint02/Sprint05 set `('open', 'in_progress', 'done')`, creating a contradictory second source of schema truth.
- **evidence:**
  - `database.py` lines 41–63: `init_schema()` creates `tasktracker.tasks` with `check (status in ('open', 'in_progress', 'done'))` — `pending` is absent. `effort_hours` column is absent.
  - `schema.sql` lines 1–25: fully current — includes `effort_hours double precision`, `pending` in check constraint.
  - `migrations/003_add_pending_status.sql`: alters the constraint to add `pending`.
  - On a fresh deployment, `init_schema()` runs at startup (called from `main.py:on_startup`). If migrations have not been applied yet, `init_schema()` creates the table with the outdated constraint. If a migration tries to `DROP CONSTRAINT IF EXISTS tasks_status_check` and re-add it, the drop will succeed but `init_schema` may race or re-run on a second restart, reinstating the outdated constraint.
- **rule_refs:** R-CON-BP-03 (durable state must have a single clear owner), R-CON-BP-09 (cross-artifact truth consistency)
- **contract_refs:** none
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/database.py`
  - `03_Application/TaskTracker/schema.sql`
  - `03_Application/TaskTracker/migrations/003_add_pending_status.sql`
- **why_it_matters:** The schema is durable state. Two diverging definitions of it means fresh deployments may produce a table that rejects `pending` status inserts and silently drops the `effort_hours` column. The canonical `schema.sql` is the intended source of truth but it is not actually used at startup — only `init_schema()` is. This is a correctness risk, not merely a documentation inconsistency.
- **recommended_action:** Either (a) retire `init_schema()` and replace it with a proper migration runner that applies all files in `migrations/` in order (the idiomatic Atlas pattern), or (b) keep `init_schema()` but have it `execute open(schema.sql).read()` rather than embedding DDL inline. Under either option, `schema.sql` becomes the single canonical source. The `init_schema()` function should not contain a second copy of the DDL.
- **confidence:** high

---

### F-02 — Label proxy endpoints return bespoke LabelEngine shapes — no exception record

- **category:** `exception_missing_record`
- **severity:** high
- **claim:** Six endpoints under `/tasks` — `GET /labels/search`, `GET /{task_id}/labels`, `POST /{task_id}/labels`, `DELETE /{task_id}/labels/{label_id}`, `PUT /{task_id}/labels` — return the raw LabelEngine response payload rather than `Dataset | ApiError`, with no formal exception record.
- **evidence:**
  - `tasks.py` lines 352–425: all label proxy endpoints call LabelEngine and return `JSONResponse(status_code=resp.status_code, content=resp.json())` verbatim. The returned shapes are LabelEngine-specific (e.g., `{"labels": [...]}` from `GET /{task_id}/labels`, `{"labels": [LabelRecord]}` from search). None are `Dataset`.
  - `ShellEntry.tsx` lines 435–436, 893–896: frontend explicitly destructures `res.labels`, not `res.rows` — confirming the non-Dataset shape is consumed as-is.
  - No `ARCHITECTURE_EXCEPTIONS.md` exists in `03_Application/TaskTracker/` to record this deviation.
  - R-CON-BP-04: "All application endpoints that provide UI-visible data must return a `Dataset`." The frontend renders these labels in the detail view and label popover — they are UI-visible data.
- **rule_refs:** R-CON-BP-04
- **contract_refs:** `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md` §1, §5
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 352–425)
  - `03_Application/TaskTracker/src/ShellEntry.tsx` (label-consuming call sites)
- **why_it_matters:** Future agents auditing or extending TaskTracker will see contract-violating endpoints with no formal justification. Consumers of these endpoints cannot rely on the standard `Dataset` / `ApiError` contract for error handling or rendering. The frontend already compensates with bespoke `res.labels` access rather than `res.rows` access, embedding the LabelEngine schema into the app frontend.
- **recommended_action:** Either (a) wrap the LabelEngine responses in a thin `Dataset` adapter in the proxy handlers (label list as rows, with a minimal schema), or (b) create `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md` with a formal exception record documenting that label proxy endpoints pass through LabelEngine's native shape because they are operational/action endpoints rather than display data endpoints, and that this pattern is intentional. Option (b) is lower-cost and preserves the current functioning behavior; option (a) is architecturally cleaner but changes the frontend consumption pattern.
- **confidence:** high

---

### F-03 — `fetch_labels_for_tasks` queries `labels.*` schema directly, bypassing LabelEngine API

- **category:** `boundary_drift`
- **severity:** medium
- **claim:** The `fetch_labels_for_tasks` helper in `tasks.py` issues a direct SQL query against `labels.object_labels` and `labels.labels` — the LabelEngine's internal schema — rather than calling the LabelEngine API. This couples TaskTracker directly to LabelEngine's internal DB layout.
- **evidence:**
  - `tasks.py` lines 72–95: `fetch_labels_for_tasks` executes `select ol.object_id, l.id as label_id, l.name as label_name from labels.object_labels ol join labels.labels l on l.id = ol.label_id where ol.object_id = any(%s)` using the caller's connection (TaskTracker's own DB connection pool).
  - `tasks.py` line 231: called from `list_tasks` to batch-embed labels into Dataset rows.
  - All write operations (attach, detach, set) go through LabelEngine via HTTP. Only the batch read is direct SQL.
- **rule_refs:** R-CON-PL-01 (platform boundary — LabelEngine is a platform service; its internal schema is not a public contract), R-CON-BP-02 (contracts and boundaries)
- **contract_refs:** none
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py` (lines 72–95, 231)
- **why_it_matters:** LabelEngine's `labels.object_labels` and `labels.labels` table layouts are internal implementation details of a platform service. If LabelEngine's schema evolves (renamed columns, additional joins required, schema split), TaskTracker's direct SQL query breaks silently — there is no API-level contract or version boundary. The asymmetry (reads bypass the service; writes go through it) also means cache invalidation or transactional semantics in LabelEngine cannot apply to these reads. The behaviour was introduced as a performance optimisation (one batch query vs N HTTP calls) — a legitimate concern, but the boundary violation is real.
- **recommended_action:** Document this as a formal exception (or architecture decision record) in `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`, recording the rationale (N+1 avoidance), the constraint (TaskTracker and LabelEngine share the same Postgres instance by deployment contract), and the risk (schema coupling). If LabelEngine later exposes a batch-fetch API (e.g., `GET /api/objects/batch?ids=...`), migrate to it. The exception record ensures the coupling is visible to future agents.
- **confidence:** high

---

### F-04 — `view=pending_board` is an internal implementation name exposed in the URL

- **category:** `missing_rule_signal`
- **severity:** medium
- **claim:** The frontend maps its `'pending'` tab to `GET /tasks?view=pending_board`, where `pending_board` is an implementation-level name not aligned with any user-facing or domain concept. This is an inconsistency between the frontend tab vocabulary and the backend view parameter vocabulary, with no governing rule about view parameter naming.
- **evidence:**
  - `ShellEntry.tsx` line 1439: `if (view === 'pending') return '/tasks?view=pending_board';`
  - `tasks.py` lines 119, 162: `VALID_VIEW = {"active", "pending_board"}` and `elif view == "pending_board":`
  - Sprint05 draft (`Sprint05/00_input/draft.md`) defines the view as "Pending" in both UI and backend terms; the `_board` suffix appears only in implementation.
- **rule_refs:** R-CON-AL-01 (query behavior explicitness — query parameter vocabulary should be declared and unambiguous), R-CON-BP-01 (machine legibility)
- **contract_refs:** none
- **affected_artifacts:**
  - `03_Application/TaskTracker/backend/routers/tasks.py`
  - `03_Application/TaskTracker/src/ShellEntry.tsx`
- **why_it_matters:** This is not a correctness bug (the mapping works), but it violates machine legibility: a future agent reading the API independently will not understand why `view=pending` is not the parameter for the "Pending" tab. Atlas lacks a formal rule requiring query parameter vocabulary to match domain/UI vocabulary. This is a signal that such a rule or convention is missing.
- **recommended_action:** Rename `pending_board` to `pending` in both `VALID_VIEW` and the frontend fetch URL. If the name was intentionally kept distinct (e.g., to leave room for a separate "pending" status filter), document the distinction explicitly in code or a design note. Also surface the naming vocabulary gap to Atlas governance.
- **confidence:** high

---

### F-05 — `CurrentArchitecture/` artifacts are Sprint02-vintage and stale relative to current implementation

- **category:** `likely_orphaned`
- **severity:** low
- **claim:** `CurrentArchitecture/architecture.json` and `CurrentArchitecture/scaffolding.json` reflect Sprint02 (`Sprint02-Optimization_and_Effort`) state and do not include Sprint04 label integration, Sprint05 view system, pending status, or the label proxy endpoints.
- **evidence:**
  - `CurrentArchitecture/architecture.json` line 2: `"sprint": "Sprint02-Optimization_and_Effort"`. It describes `TASK_SCHEMA` without Sprint05's view/tab architecture, mentions `TableView` and `DetailView` as removed (that is Sprint02 context), and describes the frontend as a simple card-list — not the grouped-by-label view introduced in Sprint04.
  - `CurrentArchitecture/scaffolding.json` line 2: same Sprint02 sprint identifier.
  - Sprint04 implementation notes confirm `TaskGroupedList` was introduced in Sprint04 — absent from `CurrentArchitecture/`.
- **rule_refs:** R-CON-BP-03 (durable state must be current and owned), R-CON-BP-01 (machine legibility — stale artifacts mislead future agents)
- **contract_refs:** none
- **affected_artifacts:**
  - `03_Application/TaskTracker/CurrentArchitecture/architecture.json`
  - `03_Application/TaskTracker/CurrentArchitecture/scaffolding.json`
- **why_it_matters:** A future agent reading `CurrentArchitecture/` as the authoritative system description will receive a significantly incorrect view of the application — missing grouping, views, pending status, label proxy, and the `set_task_labels` endpoint. This degrades machine legibility (R-CON-BP-01) and creates a hidden-state risk (R-CON-BP-03). Atlas lacks a formal rule requiring `CurrentArchitecture/` to be kept current after each sprint.
- **recommended_action:** Update `CurrentArchitecture/architecture.json` and `CurrentArchitecture/scaffolding.json` to reflect the post-Sprint05 state, or clearly mark them as Sprint02-point-in-time artifacts and create an up-to-date equivalent. Also surface a missing-rule signal to governance: Atlas should require `CurrentArchitecture/` to be updated as a sprint completion gate.
- **confidence:** high

---

### F-06 — No rule governs whether proxy/action endpoints must conform to R-CON-BP-04

- **category:** `missing_rule_signal`
- **severity:** low
- **claim:** R-CON-BP-04 states "all application endpoints that provide UI-visible data must return a Dataset," but Atlas has no rule clarifying whether this applies to proxy/action endpoints (attach, detach, search) whose responses are operationally consumed but not rendered via Dataset primitives.
- **evidence:**
  - TaskTracker's label endpoints (F-02) are a concrete instance of this gap: they are UI-visible (labels appear in detail view) but are action/proxy endpoints, not reporting endpoints.
  - FoodTracker and Chronicle have `ARCHITECTURE_EXCEPTIONS.md` files — suggesting the need for exceptions has been encountered before — but the Atlas rule set does not distinguish reporting endpoints from action/proxy endpoints.
- **rule_refs:** R-CON-BP-04
- **contract_refs:** `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md` §9
- **affected_artifacts:** Governance gap — not a single file.
- **why_it_matters:** Without a rule, teams must either apply R-CON-BP-04 literally to all endpoints (impractical for 204 deletes and thin proxies) or rely on judgment. Inconsistent application across applications makes auditing non-deterministic. FoodTracker may have resolved this differently from TaskTracker.
- **recommended_action:** Atlas governance should clarify R-CON-BP-04 scope: does it apply to (a) all endpoints, (b) only GET/read endpoints, or (c) only endpoints consumed by platform UI rendering primitives (TableView, DetailView, charts)? A clarification or sub-rule would eliminate the ambiguity and prevent future exception proliferation.
- **confidence:** high

---

## 4. Likely Orphaned / Residue Inventory

| Artifact | Reason suspected | Confidence |
|---|---|---|
| `03_Application/TaskTracker/CurrentArchitecture/architecture.json` | Sprint02 vintage; does not reflect Sprint04 or Sprint05 state. Grouping, views, pending status, label proxy, and `set_task_labels` are absent. | high |
| `03_Application/TaskTracker/CurrentArchitecture/scaffolding.json` | Same sprint identifier as above; Sprint02-only scope. | high |

---

## 5. Missing Rule Signals

### MS-01 — R-CON-BP-04 scope ambiguity: reporting vs action/proxy endpoints

Observed in: `03_Application/TaskTracker/backend/routers/tasks.py` (label proxy endpoints).

Multiple applications in Atlas use action endpoints (POST, DELETE, PATCH, proxy) that return non-Dataset responses to the UI. R-CON-BP-04 as written ("all application endpoints that provide UI-visible data") covers these cases literally, but the practical interpretation must differ between a reporting GET endpoint and an action endpoint that returns a status confirmation. No Atlas rule distinguishes these categories.

Suggested governance gap: A sub-rule or clarification to R-CON-BP-04 defining which endpoint categories must return Dataset vs which may return non-Dataset responses (e.g., 204 No Content for deletes, bespoke action confirmations for mutating proxy calls).

### MS-02 — No rule requires `CurrentArchitecture/` to be updated at sprint completion

Observed in: `03_Application/TaskTracker/CurrentArchitecture/` (two sprints stale).

Atlas sprint process (R-PRO-BP-01) defines sprint completion artifacts but does not require updating a `CurrentArchitecture/` folder. If applications maintain such a folder as a living architecture reference, its staleness degrades machine legibility (R-CON-BP-01) over time — the exact problem Atlas is designed to prevent.

Suggested governance gap: A sprint completion requirement (either via R-PRO-BP-01 extension or a new rule) mandating that a designated current-architecture artifact is updated or verified before `SPRINT_COMPLETE` is recorded.

---

## 6. Remediation Plan

### 1. Immediate fixes (high rule/exception violations)

1. **F-01 — Fix `database.py:init_schema()`.** Replace the inline DDL block with either a migration runner (preferred) or a reference to `schema.sql`. The inline DDL is two sprints behind and will corrupt fresh deployments.
   - Affected: `03_Application/TaskTracker/backend/database.py`

2. **F-02 — Create `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`.** Record a formal exception for the label proxy endpoints returning LabelEngine native shapes rather than Dataset. Include rationale, constraints, and resolution criteria (e.g., "if a batch label-fetch Dataset API is introduced, this exception is retired").
   - Affected: new file `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`

### 2. Simplifications (unnecessary complexity)

No unnecessary complexity findings in this audit. The implementation is lean for the feature scope.

### 3. Removals (orphaned artifacts)

3. **F-05 — Update `CurrentArchitecture/`.** Either update both JSON files to reflect post-Sprint05 state, or formally mark them as Sprint02 snapshots and create new current-state artifacts.
   - Affected: `03_Application/TaskTracker/CurrentArchitecture/architecture.json`, `scaffolding.json`

### 4. Formal exception records needed

4. **F-02 (label proxy shapes)** — formal exception in `03_Application/TaskTracker/ARCHITECTURE_EXCEPTIONS.md`.
5. **F-03 (direct `labels.*` schema query)** — document as an architecture decision record or formal exception in the same file, recording the N+1 avoidance rationale and the deployment constraint (shared Postgres instance).

### 5. Rule clarifications or new rules to feed back into Atlas governance

6. **MS-01** — Clarify R-CON-BP-04 scope: distinguish reporting/display endpoints from action/proxy endpoints. Consider a sub-rule exempting 204 deletes, PATCH confirmations, and thin proxies when the returned data is not consumed by Dataset-rendering platform primitives.
7. **MS-02** — Add a sprint completion gate requiring `CurrentArchitecture/` (or equivalent living architecture artifact) to be updated before `SPRINT_COMPLETE`. Consider adding this to R-PRO-BP-01 §4 required artifacts for `IMPLEMENTATION_REVIEWED`.
8. **F-04 (view param naming)** — Consider a convention (informal or formal) requiring backend query parameter vocabulary to match domain/UI vocabulary used in the frontend, to preserve machine legibility of API contracts.
