---
name: Skip specs reviewer stage
description: The sprint_specs_reviewer stage is permanently skipped — DRAFT_READY routes directly to the designer.
type: feedback
---

The `sprint_specs_reviewer` stage is skipped in all sprints. Route `DRAFT_READY` directly to `sprint_design_application` or `sprint_design_platform` depending on layer.

**Why:** User decided specs are good enough and the extra stage adds friction without value.

**How to apply:** Never launch `sprint_specs_reviewer`. Never require `10_specs/design_specs.md` as a blocker. Jump straight from `DRAFT_READY` to designer.
