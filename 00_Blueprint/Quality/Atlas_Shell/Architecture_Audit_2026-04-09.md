# Architecture Audit Report

> **Audit Run:** `Atlas_Shell_auditrun_04_09_2026`
> **Run Type:** component-specific
> **Agent:** audit_architecture
> **Date:** 2026-04-09

---

## 1. Executive Summary

The Atlas Shell is structurally sound and substantially well-implemented. The core integration contract (`AppConfig` / `NavItem`), the registry (`AppRegistry`), the routing model, and the platform UI primitives all conform to their design artifacts. Test coverage is meaningful and matched to the design's failure modes. The formal exception records in `ARCHITECTURE_EXCEPTIONS.md` correctly cover the two deliberate boundary deviations.

Three findings require action. The highest-severity is a confirmed boundary violation: application domain CSS (TaskTracker-specific class names) has leaked into `platform-ui/index.css`, which is the platform-wide design token and component stylesheet. This violates R-CON-PL-01 and contradicts the design invariant that the shell carries no application meaning. The remaining findings are: two exception records that describe a superseded file path (`src/apps/index.ts`) instead of the actual implementation mechanism; a triplicated `agg()` utility function across chart components; a direct internal mutation of the request log ring buffer by `WarningPlaceholder`; a version mismatch between `UI_Data_Contract.md` (v0.4) and R-CON-BP-04 (which describes v0.5); and stale path references in `component_architecture.json`.

No critical violations were found. No orphaned artifacts were detected within the shell itself. The dependency direction exceptions (R-EXC-PC-01, R-EXC-PC-02) are formally recorded, rationale is sound, and the implemented mechanism is better than what the exception text describes.

**Finding counts:**

| Category | Critical | High | Medium | Low |
|---|---|---|---|---|
| `boundary_drift` | — | 1 | — | — |
| `exception_missing_record` | — | — | 1 | — |
| `unnecessary_complexity` | — | — | 1 | — |
| `missing_rule_signal` | — | — | 1 | — |
| `verification_required` | — | — | 1 | — |
| `likely_orphaned` / stale reference | — | — | — | 2 |
| **Total** | 0 | 1 | 4 | 2 |

**Top 5 recommended actions:**

1. Remove `.tasks-toolbar`, `.tasks-filters`, and `.filter-chip` CSS blocks from `platform-ui/index.css` and move them into the TaskTracker application's own stylesheet.
2. Update `ARCHITECTURE_EXCEPTIONS.md` R-EXC-PC-01 and R-EXC-PC-02 to reference `src/shell/main.tsx` (the actual mechanism) instead of the non-existent `src/apps/index.ts`.
3. Extract the `agg()` function into a single shared utility module (e.g., `platform-ui/utils/chartAgg.ts`) and import it in all three chart components.
4. Align `UI_Data_Contract.md` version header (currently v0.4) with R-CON-BP-04 (which declares v0.5).
5. Update stale path references in `component_architecture.json` (dependencies referencing `02_Platform/UI` and `00_Blueprint/UI/*`).

---

## 2. Audit Basis

**Rules consulted:**

| ID | Canonical path |
|---|---|
| R-CON-BP-01 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-02 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-03 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-04 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-06 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-07 | `.claude/rules/R-CON-BP.md` |
| R-CON-BP-09 | `.claude/rules/R-CON-BP.md` |
| R-CON-PL-01 | `.claude/rules/R-CON-PL.md` |
| R-CON-PL-02 | `.claude/rules/R-CON-PL.md` |
| R-OPS-BP-01 | `.claude/rules/R-OPS-BP.md` |
| R-OPS-BP-02 | `.claude/rules/R-OPS-BP.md` |

**Contracts consulted:**

- `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md` (v0.4)
- `02_Platform/Atlas_Shell/platform-ui/api/types.ts` (R-CON-BP-04 TypeScript authority)
- `02_Platform/Atlas_Shell/src/types.ts` (AppConfig / NavItem shell contract, v1.0.0)
- `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` (R-EXC-PC-01, R-EXC-PC-02, R-EXC-PC-03)

**Exception records inspected:**

- R-EXC-PC-01 — Application nav content in platform shell: ACTIVE, covers `src/apps/index.ts` (file does not exist — exception text is stale; actual mechanism is `main.tsx` side-effect imports)
- R-EXC-PC-02 — Shell lazy application import pattern: ACTIVE, covers `src/apps/index.ts` (same staleness; actual mechanism confirmed in `main.tsx`)
- R-EXC-PC-03 — ShellErrorBoundary `request_id` unspecified: ACTIVE, no `ShellErrorBoundary` component found in implementation; the exception describes a component not yet implemented

**Components and files inspected:**

- `00_Definition/definition.md`
- `ARCHITECTURE_EXCEPTIONS.md`
- `10_Design/component_architecture.json`
- `UI_DesignLanguage.md`
- `UI_Implementation.md`
- `platform-ui/api/types.ts`
- `platform-ui/api/client.ts`
- `platform-ui/api/UI_Data_Contract.md`
- `platform-ui/hooks/useDataset.ts`
- `platform-ui/components/TableView.tsx`
- `platform-ui/components/DetailView.tsx`
- `platform-ui/components/BarChart.tsx`
- `platform-ui/components/LineChart.tsx`
- `platform-ui/components/ComboChart.tsx`
- `platform-ui/components/ErrorCard.tsx`
- `platform-ui/components/WarningPlaceholder.tsx`
- `platform-ui/components/DebugPanel.tsx`
- `platform-ui/components/Skeleton.tsx`
- `platform-ui/components/CreateForm.tsx`
- `platform-ui/index.css`
- `src/types.ts`
- `src/index.ts`
- `src/registry/AppRegistry.ts`
- `src/shell/main.tsx`
- `src/shell/Router.tsx`
- `src/shell/ShellLayout.tsx`
- `src/shell/ShellContext.ts`
- `src/shell/shell.css`
- `src/navigation/BottomNav.tsx`
- `src/navigation/Sidebar.tsx`
- `src/navigation/MoreMenu.tsx`
- `src/launcher/AppLauncher.tsx`
- `src/hooks/useShell.ts`
- `tests/AppRegistry.test.ts`
- `tests/Router.test.tsx`
- `tests/BottomNav.test.tsx`
- `tests/ShellLayout.test.tsx`
- `vite.config.ts`
- `package.json`
- `compose.yml`
- `Dockerfile`
- `nginx.conf`
- Application `shellConfig.ts` files: TaskTracker, FoodTracker, WorkoutTracker, Chronicle, NumericSeries (for contract compliance verification)

**Exclusions and uncertainty boundaries:**

- `00_Blueprint/SharedViews/chronicle.sql` was not inspected (out of scope for Shell component audit).
- `ShellErrorBoundary` referenced in R-EXC-PC-03 was not found in implementation — the component may not yet be built, or it may be planned. Exception is recorded for a component that does not exist.
- No `LabelEngine` or `NumericSeries` backend code was inspected in this audit.
- Sprint artifacts for Atlas Shell were not audited (not requested; process compliance is out of scope).

---

## 3. Findings

---

### F-001 — TaskTracker application domain CSS embedded in platform-ui stylesheet

- **category:** `boundary_drift`
- **severity:** high
- **claim:** `platform-ui/index.css` contains application-specific CSS classes (`.tasks-toolbar`, `.tasks-filters`, `.filter-chip`) that encode TaskTracker application domain structure into the platform-level design token and component stylesheet.
- **evidence:** `platform-ui/index.css` lines 610–645 define three blocks:
  ```css
  /* ─── Tasks page ─── */
  .tasks-toolbar { … }
  .tasks-filters { … }
  .filter-chip { … }
  .filter-chip.active { … }
  ```
  These class names are TaskTracker-specific and absent from any platform UI primitive component. No other application has corresponding blocks in this file. The file header states it is the source of truth for M3 and Atlas design tokens; the presence of application-domain class names contradicts this.
- **rule_refs:** R-CON-PL-01 (platform must not encode application-specific workflow decisions or domain meaning); R-CON-BP-01 (clarity: a file named as the platform token source must not silently carry application concerns)
- **contract_refs:** `UI_Implementation.md §9` — "Canonical location: `platform-ui/index.css` — do not redefine tokens in component files." The file is described as a token file, not an application stylesheet.
- **affected_artifacts:**
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/index.css` (lines 610–645)
- **why_it_matters:** Any future agent generating platform UI code from `index.css` as its style reference will absorb `.tasks-toolbar` and `.filter-chip` as if they were generic platform patterns. This pollutes the design token source of truth, degrades machine legibility of the platform boundary, and will silently grow as other applications add their own blocks. It contradicts the design invariant explicitly stated in `component_architecture.json`: "The shell renders navigation exclusively from registered AppConfig objects — no hard-coded application names or routes exist anywhere in shell source."
- **recommended_action:** Move `.tasks-toolbar`, `.tasks-filters`, `.filter-chip`, and `.filter-chip.active` to a TaskTracker-owned stylesheet (e.g., `03_Application/TaskTracker/src/tasks.css` or inline within the relevant component). Verify no other application-specific blocks exist in `platform-ui/index.css`.
- **confidence:** high

---

### F-002 — Exception records R-EXC-PC-01 and R-EXC-PC-02 reference non-existent file

- **category:** `exception_missing_record`
- **severity:** medium
- **claim:** Both active exception records in `ARCHITECTURE_EXCEPTIONS.md` describe the deviation as occurring in `src/apps/index.ts`, a file that does not exist in the implementation; the actual mechanism (side-effect imports in `main.tsx`) is a better-constrained pattern but is not what the exceptions formally cover.
- **evidence:**
  - R-EXC-PC-01 states: "application-specific navigation content (app labels, paths, `appId` values) is defined in `src/apps/index.ts` inside a platform component."
  - R-EXC-PC-02 states: "The Shell imports Application layer modules via `React.lazy(() => import('@workout/ShellEntry'))` in `src/apps/index.ts`."
  - `Glob("**/apps/**", "02_Platform/Atlas_Shell")` returns no results — `src/apps/index.ts` does not exist.
  - Actual implementation: `src/shell/main.tsx` contains side-effect imports of application `shellConfig.ts` files (lines 40–44). Applications own their `AppRegistry.register()` call; the shell only imports the side-effect.
  - The implemented pattern is actually more constrained than what the exception describes: no lazy imports in `main.tsx`, no `@workout/ShellEntry` alias — each app exposes a `ShellEntry` via its own `shellConfig.ts`.
- **rule_refs:** R-CON-BP-03 (durable state must be explicit and owned); R-CON-BP-09 (cross-artifact truth consistency — exception records must reflect actual implementation)
- **affected_artifacts:**
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` (R-EXC-PC-01 and R-EXC-PC-02 sections)
- **why_it_matters:** A future agent relying on the exception record to understand the boundary deviation will be misled: it will look for `src/apps/index.ts`, not find it, and be unable to assess whether the exception is still active or has been retired. The formal exception text does not match the implemented mechanism. This is a correctness gap in the exception artifact itself.
- **recommended_action:** Update R-EXC-PC-01 to correctly describe the implemented mechanism: application domain metadata lives in each application's own `shellConfig.ts`; the shell's `main.tsx` imports these as side-effects and that is the formal composition root. Update R-EXC-PC-02 to describe the side-effect import pattern in `main.tsx`, not lazy imports in `src/apps/index.ts`. Confirm whether the exceptions still apply to the current implementation or whether the pattern is now clean enough to retire them (particularly R-EXC-PC-01, since application metadata no longer lives inside a shell file).
- **confidence:** high

---

### F-003 — `agg()` aggregation function triplicated across chart components

- **category:** `unnecessary_complexity`
- **severity:** medium
- **claim:** An identical 12-line `agg()` function implementing the five aggregation methods (`sum`, `avg`, `count`, `max`, `min`) exists verbatim in three separate files with no shared utility module.
- **evidence:**
  - `platform-ui/components/BarChart.tsx` lines 102–112: `function agg(vals: number[], method: string): number`
  - `platform-ui/components/LineChart.tsx` lines 72–82: identical implementation
  - `platform-ui/components/ComboChart.tsx` lines 102–112: identical implementation
  - All three implementations are byte-for-byte identical in logic. The `Aggregation` type is defined in `platform-ui/api/types.ts` but the `agg()` parameter uses `string` rather than `Aggregation`, losing the type relationship.
- **rule_refs:** R-CON-BP-01 (prefer explicit structure and standard patterns; duplication creates ambiguity about which is authoritative); R-CON-PL-01 (platform components should standardize technical patterns)
- **affected_artifacts:**
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/components/BarChart.tsx`
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/components/LineChart.tsx`
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/components/ComboChart.tsx`
- **why_it_matters:** If an aggregation method is added or modified (e.g., `median`), all three files must be updated in sync. A future agent editing one chart component has no signal that the same function exists in the other two. The parameter type (`string` instead of `Aggregation`) also means a typo in an aggregation method name will silently return `0` rather than producing a type error.
- **recommended_action:** Extract into `platform-ui/utils/chartAgg.ts` (or equivalent). Update the parameter type from `string` to `Aggregation`. Import from all three chart components.
- **confidence:** high

---

### F-004 — `WarningPlaceholder` directly mutates the internal request log ring buffer

- **category:** `missing_rule_signal`
- **severity:** medium
- **claim:** `WarningPlaceholder.tsx` reaches directly into the `requestLog` array exported from `client.ts` via `getRequestLog()` and mutates it with `log.unshift(...)`, creating hidden shared mutable state between two platform-ui components with no governing rule or explicit contract for this pattern.
- **evidence:**
  - `platform-ui/components/WarningPlaceholder.tsx` lines 13–21:
    ```typescript
    const log = getRequestLog();
    const alreadyLogged = log.some(e => e.url === `[PLATFORM GAP] ${reason}`);
    if (!alreadyLogged && config !== undefined) {
      log.unshift({
        request_id: crypto.randomUUID().slice(0, 8),
        url: `[PLATFORM GAP] ${reason}`,
        method: "WARN",
        status: 0,
        duration: 0,
        response: config,
      });
    }
    ```
  - `platform-ui/api/client.ts` line 50: `export function getRequestLog(): RequestLogEntry[] { return requestLog; }` — this returns the live array reference, not a copy.
  - `UI_Data_Contract.md §4` states: "Invalid configs are also pushed to DebugPanel as [PLATFORM GAP] entries." The contract acknowledges this behavior but does not specify the mechanism.
  - `UI_Implementation.md §7` states: "Unsupported view type → `WarningPlaceholder` tagged `[PLATFORM GAP]`." No specification of how the tagging works.
- **rule_refs:** R-CON-BP-03 (durable or shared state must be explicit and owned); R-CON-BP-02 (explicit contracts over inferred behavior — the mutation side-channel is not declared in the contract)
- **affected_artifacts:**
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/components/WarningPlaceholder.tsx`
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/api/client.ts`
- **why_it_matters:** `getRequestLog()` returns the live array, not a copy. Any consumer of `getRequestLog()` that mutates the returned array also mutates the internal ring buffer. The `pushLog` function in `client.ts` (called by `apiFetch`) and the `unshift` call in `WarningPlaceholder` operate on the same array with no coordination. The `if (!alreadyLogged)` deduplication check is also a read-then-write race in a shared mutable structure. Atlas has no rule governing this inter-component shared mutable state pattern in platform-ui.
- **recommended_action:** Either (a) expose a dedicated `pushGapEvent(reason, config)` function from `client.ts` that performs the log insertion under its own control, and call that from `WarningPlaceholder`, or (b) make `getRequestLog()` return a copy and add a `pushLog` export for external callers. Either approach makes the mutation contract explicit. Additionally, consider updating `UI_Data_Contract.md` to formally specify the gap-event injection mechanism.
- **confidence:** high

---

### F-005 — `UI_Data_Contract.md` version header (v0.4) diverges from R-CON-BP-04 description (v0.5)

- **category:** `verification_required`
- **severity:** medium
- **claim:** `UI_Data_Contract.md` declares version `v0.4` in its header, but `R-CON-BP-04` in `.claude/rules/R-CON-BP.md` states `VERSION: v0.5` and describes a v0.5 change that added §9 (Endpoint Categories and Dataset Obligation). The document on disk appears to contain the v0.5 content (§9 is present) but the version header was not bumped.
- **evidence:**
  - `UI_Data_Contract.md` line 3: `> **Version:** v0.4`
  - `UI_Data_Contract.md` lines 258–267 (§9 "Endpoint Categories and Dataset Obligation"): present and complete.
  - `UI_Data_Contract.md` lines 288–298 (§11 "Versioning"): "Changes from v0.3: Added §9 (Endpoint Categories and Dataset Obligation)..." — but the header still reads v0.4.
  - `.claude/rules/R-CON-BP.md` R-CON-BP-04: `VERSION: v0.5`
- **rule_refs:** R-CON-BP-09 (cross-artifact truth consistency); R-CON-BP-04 stability requirement ("Version bump in `UI_Data_Contract.md`" required for changes)
- **contract_refs:** `UI_Data_Contract.md §11` (versioning rules)
- **affected_artifacts:**
  - `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md`
- **why_it_matters:** The rule registry and the contract document are the dual authority for the data contract. When their versions diverge, any agent reasoning about the contract version cannot determine which is canonical. The stability requirement in R-CON-BP-04 explicitly mandates a version bump in this document when changes are made.
- **recommended_action:** Read the §11 changelog carefully against R-CON-BP-04 to determine which is the authoritative version. If §9 represents a v0.5 addition, bump the header to v0.5. If v0.5 includes additional content not in the document, add it. Resolve the discrepancy as a single explicit update.
- **confidence:** medium (the content appears complete, but the version number is unambiguously inconsistent)

---

## 4. Likely Orphaned / Residue Inventory

| Artifact | Reason suspected | Confidence |
|---|---|---|
| `ARCHITECTURE_EXCEPTIONS.md` — R-EXC-PC-01 "application nav content in `src/apps/index.ts`" | The file `src/apps/index.ts` does not exist. Application nav metadata now lives in each app's own `shellConfig.ts`, owned by the application. The exception may be retired entirely since the violation it covered may no longer exist. | medium |
| `ARCHITECTURE_EXCEPTIONS.md` — R-EXC-PC-03 "ShellErrorBoundary `request_id` unspecified" | No `ShellErrorBoundary` component exists in the implementation. The exception covers a component that has not been built. Either the component is planned and the exception is premature, or the component was removed. | medium |
| `10_Design/component_architecture.json` — internal dependency reference `02_Platform/UI` (lines in `dependencies.internal_required` and `shared_views.consumes`) | `02_Platform/UI` does not exist as a directory. Platform UI primitives now live at `02_Platform/Atlas_Shell/platform-ui/`. The architecture artifact references a path from before the consolidation. | high |
| `10_Design/component_architecture.json` — references to `00_Blueprint/UI/01_UI_Contract`, `00_Blueprint/UI/02_UI_DesignLanguage`, `00_Blueprint/UI/03_UI_Implementation` | These paths do not exist under `00_Blueprint`. The actual artifacts are `platform-ui/api/UI_Data_Contract.md`, `UI_DesignLanguage.md`, and `UI_Implementation.md` — all inside the shell component itself. | high |

---

## 5. Missing Rule Signals

### MS-001 — No rule governing internal shared mutable state between platform-ui components

**Pattern observed:** `WarningPlaceholder` mutates the internal request log of `client.ts` through the `getRequestLog()` live-array reference. This creates a hidden coupling between a UI component and the API client's internal data structure. The contract documents acknowledge the behavior but do not specify the mechanism or govern which components may write to the log.

**Locations:** `platform-ui/components/WarningPlaceholder.tsx`, `platform-ui/api/client.ts`

**Suggested governance gap:** Atlas has no rule covering shared mutable state within platform-ui components. R-CON-BP-03 governs durable state at the system level but does not address ephemeral shared structures within a single component layer. A rule or component-level contract clarifying which components may push events to the request log — and through what interface — would prevent this from becoming an implicit convention absorbed by future components.

---

### MS-002 — No rule governing application-domain content in operational configuration of platform components

**Pattern observed:** `nginx.conf` and `vite.config.ts` (dev proxy section) both encode application-specific API route names and port assignments. Each new application requires an addition to both files. This is structurally analogous to the `main.tsx` side-effect import pattern, but the operational configuration files have no formal exception record and no governing rule that distinguishes acceptable operational coupling from boundary drift.

**Locations:** `nginx.conf` (all `location /api/*` blocks), `vite.config.ts` (server.proxy section)

**Suggested governance gap:** The `ARCHITECTURE_EXCEPTIONS.md` pattern (R-EXC-PC-01, R-EXC-PC-02) applies to source-level application references. A parallel signal is needed for operational configuration — either a rule clarifying that proxy and routing configuration in `01_System` or platform component ops files is exempt from the boundary rule, or an exception record covering the nginx and vite proxy coupling.

---

## 6. Remediation Plan

### 1. Immediate fixes (high severity)

**F-001 — Remove TaskTracker CSS from `platform-ui/index.css`**

Remove lines 609–645 from `/home/linse/Prod/Atlas/02_Platform/Atlas_Shell/platform-ui/index.css` (the `.tasks-toolbar`, `.tasks-filters`, `.filter-chip`, `.filter-chip:hover`, `.filter-chip.active` blocks). Create a TaskTracker-owned stylesheet or move these declarations inline into the relevant TaskTracker page component. Verify no other application-specific CSS blocks exist in `platform-ui/index.css`.

---

### 2. Contract and exception record corrections (medium severity)

**F-002 — Update `ARCHITECTURE_EXCEPTIONS.md` to reflect actual implementation**

- R-EXC-PC-01: Update to describe that application nav metadata lives in each application's own `shellConfig.ts` (owned by the application, not the shell). Evaluate whether the violation described still exists in the current pattern — if the shell no longer owns any application-specific content, this exception may be retired.
- R-EXC-PC-02: Update to describe the side-effect import of `shellConfig.ts` files in `main.tsx`, not lazy imports in `src/apps/index.ts`.

**F-005 — Align `UI_Data_Contract.md` version with R-CON-BP-04**

Update the version header in `UI_Data_Contract.md` to reflect the actual version. If §9 content represents v0.5, bump the header to v0.5.

---

### 3. Simplifications (unnecessary complexity)

**F-003 — Extract `agg()` into a shared chart utility module**

Create `platform-ui/utils/chartAgg.ts` exporting a single `agg(vals: number[], method: Aggregation): number` function. Remove the duplicate implementations from `BarChart.tsx`, `LineChart.tsx`, and `ComboChart.tsx`. Update imports.

---

### 4. Internal contract clarification (medium severity)

**F-004 — Formalize the gap-event injection interface in `client.ts`**

Expose a dedicated `pushGapEvent(reason: string, config: unknown): void` function from `client.ts`. Update `WarningPlaceholder.tsx` to call this instead of mutating `getRequestLog()` directly. This makes the mutation contract explicit and eliminates the hidden shared mutable state coupling.

---

### 5. Stale artifact cleanup

- `10_Design/component_architecture.json`: Update path references from `02_Platform/UI` to `02_Platform/Atlas_Shell/platform-ui/`. Update `00_Blueprint/UI/*` path references to the actual local paths (`UI_DesignLanguage.md`, `UI_Implementation.md`, `platform-ui/api/UI_Data_Contract.md`).
- R-EXC-PC-03 in `ARCHITECTURE_EXCEPTIONS.md`: Determine whether `ShellErrorBoundary` is planned or was removed. If removed, retire the exception record. If planned, mark it with a status note indicating the component is not yet implemented.

---

### 6. Rule clarifications to feed back into Atlas governance

- **MS-001:** Consider a component-level rule for platform-ui specifying which components may write to the request log, and through what interface. Candidate: a rule under R-CON-PL stating that shared mutable structures within a platform component must have a single owner with a declared write interface.
- **MS-002:** Consider a clarification or exception pattern for operational configuration (nginx, vite proxy) that acknowledges the application-coupling is structurally unavoidable and is exempt from the platform boundary rule, in the same way that `main.tsx` side-effect imports are formally excepted.
