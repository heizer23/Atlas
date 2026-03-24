---
RULE_ID: R-CON-BP-02
TITLE: Contracts and Boundaries
TYPE: CONSTITUTIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-CON-BP-02_contracts_and_boundaries.md
RELATES_TO: R-CON-BP-01
---

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
