# Atlas Rule Registry

The authoritative index of all formally registered Atlas rules.

Governing document for the rule system: `R-CON-BP-05` (`.claude/rules/R-CON-BP-05_rule_system.md`)

Rules are classified by **Type × Scope**. Application-scope rules are not centrally registered.

---

## Taxonomy

### Types
| Code | Name | Meaning |
|------|------|---------|
| CON | CONSTITUTIONAL | Defines what Atlas is structurally allowed to be |
| OPS | OPERATIONAL | Governs how agents or contributors should behave |
| PRO | PROCESS | Governs workflow, states, handoffs, required artifacts |
| EXC | EXCEPTION | Approved deviation from another rule |

### Scopes
| Code | Name | Meaning |
|------|------|---------|
| BP | BLUEPRINT | Cross-system, durable, architectural, contract-governing |
| PL | PLATFORM_LAYER | Applies to the Platform layer as a whole |
| PC | PLATFORM_COMPONENT | Applies to one specific platform component |
| APP | APPLICATION | Local, not centrally registered |

### Rule ID Format
`R-[TYPE]-[SCOPE]-[NN]`

---

## Registered Rules

### Blueprint — Constitutional

| Rule ID | Title | Canonical Source | Status |
|---------|-------|-----------------|--------|
| R-CON-BP-01 | Architecture as AI Interface | `.claude/rules/R-CON-BP-01_architecture_as_ai_interface.md` | ACTIVE |
| R-CON-BP-02 | Contracts and Boundaries | `.claude/rules/R-CON-BP-02_contracts_and_boundaries.md` | ACTIVE |
| R-CON-BP-03 | Durable State Must Be Explicit | `.claude/rules/R-CON-BP-03_no_hidden_state.md` | ACTIVE |
| R-CON-BP-04 | UI Data Contract | `.claude/rules/R-CON-BP-04_ui_data_contract.md` | ACTIVE |
| R-CON-BP-05 | Atlas Rule System | `.claude/rules/R-CON-BP-05_rule_system.md` | ACTIVE |

### Blueprint — Operational

| Rule ID | Title | Canonical Source | Status |
|---------|-------|-----------------|--------|
| R-OPS-BP-01 | Surface Violations Explicitly | `.claude/rules/R-OPS-BP-01_surface_violations.md` | ACTIVE |
| R-OPS-BP-02 | Security: Least Privilege and Minimal Exposure | `.claude/rules/R-OPS-BP-02_security.md` | ACTIVE |

### Blueprint — Process

| Rule ID | Title | Canonical Source | Status |
|---------|-------|-----------------|--------|
| R-PRO-BP-01 | Sprint Process Contract | `.claude/rules/R-PRO-BP-01_sprint_process.md` | ACTIVE |

### Platform Layer — Constitutional

| Rule ID | Title | Canonical Source | Status |
|---------|-------|-----------------|--------|
| R-CON-PL-01 | Platform Boundary | `.claude/rules/R-CON-PL-01_platform_boundary.md` | ACTIVE |
| R-CON-PL-02 | Dependency Direction | `.claude/rules/R-CON-PL-02_dependency_direction.md` | ACTIVE |

### Platform Component — Exception

| Rule ID | Title | Canonical Source | Status |
|---------|-------|-----------------|--------|
| R-EXC-PC-01 | Application Nav Content in Platform Shell | `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` | ACTIVE |
| R-EXC-PC-02 | Shell Lazy Application Import Pattern | `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` | ACTIVE |
| R-EXC-PC-03 | ShellErrorBoundary ApiError request_id Source Unspecified | `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` | ACTIVE |

---

## Open Registration Candidates

These have been identified but not yet formally registered:

| Candidate | Type | Scope | Source | Audit Finding |
|-----------|------|-------|--------|---------------|
_(No open candidates remaining)_

---

## Notes

- Scope is semantic reach, not file location. A rule in `.claude/rules/` may have `SCOPE: BLUEPRINT`.
- APPLICATION-scope rules exist but are not registered here. They live as local notes, specs, or conventions within the application directory.
- PLATFORM_COMPONENT rules live in or near the component directory (e.g., `02_Platform/XX_Component/COMPONENT_RULES.md`).
