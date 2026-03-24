---
RULE_ID: R-OPS-BP-01
TITLE: Surface Violations Explicitly
TYPE: OPERATIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-OPS-BP-01_surface_violations.md
RELATES_TO: R-CON-BP-01
---

If the requested design conflicts with Atlas architecture, boundaries, or existing system structure, do not silently normalize it.

Instead:
- flag the conflict explicitly
- describe the contradiction
- state the local consequence for the design
- keep the handoff traceable
