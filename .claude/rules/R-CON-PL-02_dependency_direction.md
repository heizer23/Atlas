---
RULE_ID: R-CON-PL-02
TITLE: Dependency Direction
TYPE: CONSTITUTIONAL
SCOPE: PLATFORM_LAYER
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-CON-PL-02_dependency_direction.md
RELATES_TO: R-CON-PL-01
---

Respect Atlas layer boundaries.

A Platform component may depend on Blueprint contracts and System capabilities as allowed by the architecture.
It must not absorb Application logic or define Application behavior.

Design dependencies explicitly:
- what this component depends on
- what may depend on this component
- what must remain outside its scope

Avoid bidirectional conceptual coupling.
Avoid pulling application meaning into platform design.
