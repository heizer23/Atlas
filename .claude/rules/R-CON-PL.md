# R-CON-PL — Constitutional Platform Layer Rules

TYPE: CONSTITUTIONAL
SCOPE: PLATFORM_LAYER
CANONICAL_SOURCE: .claude/rules/R-CON-PL.md

---

## R-CON-PL-01 — Platform Boundary

STATUS: ACTIVE
RELATES_TO: R-CON-BP-01

A Platform component provides reusable technical capability.

It:
- is primarily generic
- is intended for reuse
- does not own domain meaning or business rules
- is persistent or long-lived
- supports applications without determining their workflow behavior

Platform provides capability.
Applications provide meaning.

Platform may:
- expose reusable primitives influenced by application needs
- standardize technical patterns, adapters, and integration surfaces
- carry domain-shaped data without interpreting its business meaning

Platform should not:
- encode application-specific workflow decisions
- become the owner of business rules
- absorb behavior that is meaningful only within one application

When designing a platform component:
- define what capability is provided
- define who may consume it
- define what it explicitly does not do
- state any domain-shaped assumptions that exist only for technical interoperability
- keep ownership of meaning and workflow in the application layer

---

## R-CON-PL-02 — Dependency Direction

STATUS: ACTIVE
RELATES_TO: R-CON-PL-01

Respect Atlas layer boundaries.

A Platform component may depend on Blueprint contracts and System capabilities as allowed by the architecture.
It must not absorb Application logic or define Application behavior.

Design dependencies explicitly:
- what this component depends on
- what may depend on this component
- what must remain outside its scope

Avoid bidirectional conceptual coupling.
Avoid pulling application meaning into platform design.
