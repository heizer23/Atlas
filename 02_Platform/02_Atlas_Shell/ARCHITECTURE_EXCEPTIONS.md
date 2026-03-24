# Atlas Shell — Architecture Exceptions

This file formally records accepted deviations from Atlas architectural rules for the `02_Platform/02_Atlas_Shell` component.

All exceptions were identified during the system audit of 2026-03-24 and are accepted as deliberate design decisions given the standalone Vite application architecture of the Shell.

---

## R-EXC-PC-01 — Application nav content embedded in Shell

```
RULE_ID: R-EXC-PC-01
TITLE: Application Nav Content in Platform Shell
TYPE: EXCEPTION
SCOPE: PLATFORM_COMPONENT
STATUS: ACTIVE
EXCEPTION_TO: R-CON-PL-01 (Platform Boundary)
CANONICAL_SOURCE: 02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md
```

**Violation:** Application-specific navigation content (app labels, paths, `appId` values) is defined in `src/apps/index.ts` inside a platform component. Platform components should not carry application-specific meaning.

**Accepted rationale:** The Shell's core purpose is to compose application entry points into a unified navigation surface. Some degree of application-specific registration content is structurally unavoidable. The registration data is inert metadata (labels, paths) — not business logic — and the Shell does not interpret its domain meaning.

**Constraint:** Registration entries in `src/apps/index.ts` must remain pure navigation metadata (label, path, appId, icon). No application business logic, domain rules, or application-internal state may leak into this file.

**Resolution criteria:** If a dynamic app registration mechanism is introduced (e.g., apps self-register via a platform API), this exception may be retired.

---

## R-EXC-PC-02 — Platform imports Application layer via lazy loading

```
RULE_ID: R-EXC-PC-02
TITLE: Shell Lazy Application Import Pattern
TYPE: EXCEPTION
SCOPE: PLATFORM_COMPONENT
STATUS: ACTIVE
EXCEPTION_TO: R-CON-PL-02 (Dependency Direction)
CANONICAL_SOURCE: 02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md
```

**Violation:** The Shell imports Application layer modules via `React.lazy(() => import('@workout/ShellEntry'))` in `src/apps/index.ts`. This inverts the expected dependency direction (Platform should not depend on Application).

**Accepted rationale:** The Shell's purpose is to compose application UIs into a single navigable surface. Lazy-loaded application entry points are the mechanism by which this composition happens. The import is deferred (lazy), scoped to a thin entry point contract (`ShellEntry`), and does not couple the Shell to application internals.

**Constraint:** Lazy imports must target only the designated shell entry point export of each application (`ShellEntry` or equivalent). The Shell must not import application-internal components, hooks, stores, or domain logic.

**Resolution criteria:** If a module federation or plugin architecture is adopted that eliminates direct imports, this exception may be retired.

---

## R-EXC-PC-03 — ShellErrorBoundary request_id unspecified

```
RULE_ID: R-EXC-PC-03
TITLE: ShellErrorBoundary ApiError request_id Source Unspecified
TYPE: EXCEPTION
SCOPE: PLATFORM_COMPONENT
STATUS: ACTIVE
EXCEPTION_TO: R-CON-BP-04 (UI Data Contract — ApiError shape)
CANONICAL_SOURCE: 02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md
```

**Violation:** `ShellErrorBoundary` must produce an `ApiError`-shaped error payload (per R-CON-BP-04) when a client-side render error occurs, including a `request_id` field. The design does not specify what value to use for `request_id` in a client-side (non-network) error context.

**Accepted rationale:** The `request_id` field in ApiError is defined for server-originating errors where a backend trace ID exists. For client-side render errors, no backend request is involved. A synthetic client-generated ID (e.g., a timestamp-based string prefixed `client-`) satisfies the shape contract while being distinguishable from backend trace IDs.

**Constraint:** The ShellErrorBoundary implementation must produce a `request_id` value of the form `client-<timestamp>` or equivalent. It must not omit the field.

**Resolution criteria:** If a client-side error reporting pipeline is introduced that generates real trace IDs, this exception may be retired and the constraint updated.
