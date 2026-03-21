# Rule: Dependency Direction

Respect Atlas layer boundaries.

A Platform component may depend on Blueprint contracts and System capabilities as allowed by the architecture.
It must not absorb Application logic or define Application behavior.

Design dependencies explicitly:
- what this component depends on
- what may depend on this component
- what must remain outside its scope

Avoid bidirectional conceptual coupling.
Avoid pulling application meaning into platform design.