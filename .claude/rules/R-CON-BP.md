# R-CON-BP — Constitutional Blueprint Rules

TYPE: CONSTITUTIONAL
SCOPE: BLUEPRINT
CANONICAL_SOURCE: .claude/rules/R-CON-BP.md

---

## R-CON-BP-01 — Architecture as AI Interface

STATUS: ACTIVE
RELATES_TO: 00_Blueprint/Atlas_Manifest.md

Design for machine legibility as well as human understanding.

Architecture, contracts, boundaries, and structure are first-class artifacts.
Clarity is a functional requirement because later agents must be able to inspect, reason about, and extend the system from explicit artifacts alone.

Prefer:
- explicit structure
- standard patterns
- stable semantic anchors
- named boundaries
- clearly stated assumptions
- clearly stated non-scope

Avoid:
- implicit coupling
- clever but opaque abstractions
- underspecified responsibilities
- hidden assumptions

---

## R-CON-BP-02 — Contracts and Boundaries

STATUS: ACTIVE
RELATES_TO: R-CON-BP-01

Contracts are more durable than implementation.

The designer must make boundaries explicit:
- public interfaces
- integration points
- dependencies
- ownership boundaries
- assumptions and guarantees

Prefer explicit contracts over inferred behavior.

Do not blur:
- public vs private structures
- reusable interfaces vs local implementation detail
- platform capability vs application-specific usage

---

## R-CON-BP-03 — Durable State Must Be Explicit

STATUS: ACTIVE
RELATES_TO: R-CON-BP-02

State that affects system behavior or correctness must be explicit and owned.

Durable state must:
- have a clear owner (component or contract)
- have a defined storage location
- have a clear lifecycle

Examples:
- database tables
- persisted configuration
- contract schemas
- event logs
- durable queues

This state must not exist implicitly inside:
- undocumented files
- framework internals
- untracked services

### Allowed Operational State

Ephemeral implementation state is allowed and does not require architectural documentation.

Examples:
- caches
- temporary files
- retry buffers
- background worker queues
- framework session memory
- migration helpers
- build artifacts

These are acceptable if:
- they do not affect long-term correctness
- they can be safely recreated
- the system continues to function if they are cleared

**Guiding question:** If deleting the state would break correctness or lose important information, it must be explicit and owned.

---

## R-CON-BP-04 — UI Data Contract

STATUS: ACTIVE
VERSION: v0.5

### Endpoint categories

Atlas distinguishes two categories of application endpoints:

**Read endpoints** (GET) that return UI-visible data must return a `Dataset`.
The UI layer renders exclusively from `Dataset` structures and must not depend on application-specific response shapes.

**Mutation endpoints** (POST, PUT, PATCH, DELETE) that perform actions are exempt from the Dataset requirement. They must follow these rules instead:
- On success: return an appropriate HTTP status code (`201`, `200`, `204`). A response body is optional. If a body is returned, it must be a typed record or `ApiError` — never an ad-hoc untyped shape invented for the endpoint.
- On error: return `ApiError` (`{ error: { code, message, detail?, request_id } }`). Never return a bespoke error shape.
- A mutation endpoint that returns a `Dataset` as its success response (e.g., a set-and-return-all pattern) is valid and does not violate this rule.

**The key distinction:** if the frontend consumes the response to render a data view, it is a read endpoint and must return `Dataset`. If the frontend consumes it only to confirm success or display an error, it is a mutation endpoint and is exempt.

Applications must not couple to UI implementation details (React components, hooks, styling).

### Contract Authority

The `Dataset` structure is defined in two authoritative files. Import from them — never redefine locally.

| File | Language |
|---|---|
| `02_Platform/02_Atlas_Shell/platform-ui/api/types.ts` | TypeScript |
| `02_Platform/packages/platform_contracts/contracts.py` | Python |

### Contract Reference

Full type definitions, chart mappings, validation rules, error envelope, and examples:
`02_Platform/02_Atlas_Shell/platform-ui/api/UI_Data_Contract.md`

### Stability Requirement

The `Dataset` contract is stable and versioned. Breaking changes require:
1. Explicit decision — not a side effect of feature work
2. Version bump in `UI_Data_Contract.md`
3. Migration plan for affected producers and consumers

Additive changes (new optional fields) are non-breaking. Removals or renames are breaking.

---

## R-CON-BP-06 — Consumer Pattern Fidelity

STATUS: ACTIVE

If a component integrates with an existing Atlas consumer mechanism, the design must match the actual consumption pattern of that mechanism.

The design must explicitly verify:
- how the consumer loads the module
- whether the consumer expects side effects, named exports, default exports, registration calls, or route objects
- whether the scaffold reflects that exact pattern

It is not permitted to invent an interface if the consumer already defines the contract.

---

## R-CON-BP-07 — Canonical Artifact Path

STATUS: ACTIVE

If an artifact path is referenced by multiple design sections, exactly one canonical path must be used everywhere.

This applies especially to:
- migrations
- schema artifacts
- shared SQL files
- contract files
- route entry files

A path reference that differs across artifacts is a design error.

---

## R-CON-BP-08 — Contract Self-Containment

STATUS: ACTIVE

Any declared contract must be complete and unambiguous without requiring cross-reference to unrelated sections.

Specifically:
- contract statements must not rely on risks, notes, or external explanations for correctness
- ambiguity between expected-case and worst-case behavior must be resolved within the contract itself

Contracts must stand independently as authoritative definitions.

---

## R-CON-BP-09 — Cross-Artifact Truth Consistency

STATUS: ACTIVE

If a design decision is concretely expressed in any artifact (architecture, scaffold, schema, interface), all other relevant artifacts must reflect the same decision.

Specifically:
- no artifact may present an outdated or alternative interpretation of an already-resolved decision
- schema constraints override behavioral ambiguity
- scaffolding decisions override abstract alternatives

If contradictions exist across artifacts, the design is invalid.

---

## R-CON-BP-10 — Input Sufficiency

STATUS: ACTIVE

Every helper, query step, and transformation must receive all inputs required to perform its declared behavior.

If a step depends on:
- database results
- time context
- prior transformations
- derived metadata

that dependency must be explicitly declared via:
- function signature
- step ordering
- or a defined pre-step

No behavior may rely on undeclared or implicit inputs.

---

## R-CON-BP-11 — Behavioral Completeness

STATUS: ACTIVE

Every interface must define behavior for all allowed input states, and that behavior must align with the internal processing flow.

Specifically:
- every branch in internal_flow must map to an interface-visible behavior
- every interface case must be implemented in internal_flow
- no behavior may depend on unspecified internal state

If either direction is incomplete or inconsistent, the design is invalid.
