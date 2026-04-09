# R-CON-AL — Constitutional Application Layer Rules

TYPE: CONSTITUTIONAL
SCOPE: APPLICATION_LAYER
CANONICAL_SOURCE: .claude/rules/R-CON-AL.md

---

## R-CON-AL-01 — Query Behavior Explicitness

STATUS: ACTIVE

Every read or reporting endpoint must explicitly define:
- supported parameters
- defaults
- allowed parameter combinations
- ordering
- grouping semantics
- time basis (server vs client)
- boundary construction
- empty-result behavior
- zero-fill behavior (if applicable)

If query construction is shared between frontend and backend, ownership must be explicitly defined.

---

## R-CON-AL-02 — Scope-Mode Closure

STATUS: ACTIVE

For every allowed combination of scope, mode, and query parameters:
- all required outputs must be constructible
- all invariants must remain satisfiable
- required enumeration boundaries must be defined

If any allowed parameter combination cannot be computed from declared inputs, the design is invalid.

---

## R-CON-AL-03 — Invariant Realizability

STATUS: ACTIVE

Every declared invariant must be realizable using the defined inputs, queries, transformations, and helper functions.

If an invariant depends on:
- undeclared pre-queries
- hidden defaults
- unspecified formatting or derivation

the design is incomplete and invalid.

---

## R-CON-AL-04 — Partial Update Semantics

STATUS: ACTIVE

For every PATCH or partial-update endpoint, the design must explicitly distinguish between:
- field omitted
- field provided with value
- field provided as explicit null

If a nullable field can be cleared by the user:
- backend behavior for explicit null must be defined
- frontend payload behavior must specify sending null (not omission)

Existing update patterns must not be reused if they do not preserve these semantics.

---

## R-CON-AL-05 — Update Round-Trip Completeness

STATUS: ACTIVE

For every editable field in a frontend-backend interaction, the design must define the complete update round-trip:
- UI representation of empty or cleared state
- payload sent by the frontend
- backend interpretation (including null vs omit)
- resulting persisted state

A field is not fully designed until all four aspects are explicitly defined.

---

## R-CON-AL-06 — Time Authority

STATUS: ACTIVE

If a feature depends on "current" time, the design must declare the authoritative time source:
- server time
- client time
- persisted domain time
- external system time

If the client provides time-derived inputs, the design must explain how consistency with the authoritative time source is maintained.
