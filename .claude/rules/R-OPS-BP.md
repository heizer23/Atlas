# R-OPS-BP — Operational Blueprint Rules

TYPE: OPERATIONAL
SCOPE: BLUEPRINT
CANONICAL_SOURCE: .claude/rules/R-OPS-BP.md

---

## R-OPS-BP-01 — Surface Violations Explicitly

STATUS: ACTIVE
RELATES_TO: R-CON-BP-01

If the requested design conflicts with Atlas architecture, boundaries, or existing system structure, do not silently normalize it.

Instead:
- flag the conflict explicitly
- describe the contradiction
- state the local consequence for the design
- keep the handoff traceable

---

## R-OPS-BP-02 — Security: Least Privilege and Minimal Exposure

STATUS: ACTIVE
RELATES_TO: R-CON-BP-01

Default to least privilege and minimal exposure in all design and implementation decisions.

Rules:
- Warn explicitly when a proposal introduces unnecessary exposure
- Do not suggest opening ports unless clearly required and explicitly secured
- Prefer the most restricted configuration that satisfies the stated requirement
- Surface security concerns before proceeding, not as an afterthought

This rule applies to all layers. Security is not an application-layer concern — it applies equally to platform design, system configuration, and Blueprint contracts.
