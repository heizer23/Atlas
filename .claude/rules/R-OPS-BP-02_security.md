---
RULE_ID: R-OPS-BP-02
TITLE: Security: Least Privilege and Minimal Exposure
TYPE: OPERATIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-OPS-BP-02_security.md
RELATES_TO: R-CON-BP-01
---

Default to least privilege and minimal exposure in all design and implementation decisions.

Rules:
- Warn explicitly when a proposal introduces unnecessary exposure
- Do not suggest opening ports unless clearly required and explicitly secured
- Prefer the most restricted configuration that satisfies the stated requirement
- Surface security concerns before proceeding, not as an afterthought

This rule applies to all layers. Security is not an application-layer concern — it applies equally to platform design, system configuration, and Blueprint contracts.
