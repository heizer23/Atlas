---
RULE_ID: R-CON-BP-01
TITLE: Architecture as AI Interface
TYPE: CONSTITUTIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-CON-BP-01_architecture_as_ai_interface.md
RELATES_TO: 00_Blueprint/Atlas_Manifest.md
---

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
