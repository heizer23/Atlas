---
RULE_ID: R-CON-BP-05
TITLE: Atlas Rule System
TYPE: CONSTITUTIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
CANONICAL_SOURCE: .claude/rules/R-CON-BP-05_rule_system.md
---

Atlas defines a formal rule system to ensure explicit, inspectable governance.

The authoritative index of registered rules is at `00_Blueprint/RULE_REGISTRY.md`.

---

## 1. Rule Classification

Every formal rule is defined by two axes:

**Type** — what kind of rule it is:
- `CONSTITUTIONAL` — defines system structure and invariants
- `OPERATIONAL` — governs agent and contributor behavior
- `PROCESS` — governs workflows, states, and delivery structure
- `EXCEPTION` — records approved deviations from other rules

**Scope** — where the rule applies:
- `BLUEPRINT` — applies system-wide across all layers and applications
- `PLATFORM_LAYER` — applies to Platform as a layer
- `PLATFORM_COMPONENT` — applies to a specific platform capability
- `APPLICATION` — applies only within a single application

---

## 2. Rule Header Format

Every formally registered rule must declare these fields:

```
RULE_ID: R-[TYPE]-[SCOPE]-[NN]
TITLE: <human-readable name>
TYPE: CONSTITUTIONAL | OPERATIONAL | PROCESS | EXCEPTION
SCOPE: BLUEPRINT | PLATFORM_LAYER | PLATFORM_COMPONENT | APPLICATION
STATUS: ACTIVE | DEPRECATED | SUPERSEDED
CANONICAL_SOURCE: <file path>
```

Optional fields:
```
RELATES_TO: <rule ID>
EXCEPTION_TO: <rule ID>
SUPERSEDES: <rule ID>
VERSION: <version string>
```

**Rule ID format:** `R-[TYPE_CODE]-[SCOPE_CODE]-[NN]`

Type codes: `CON`, `OPS`, `PRO`, `EXC`
Scope codes: `BP`, `PL`, `PC`, `APP`

Examples: `R-CON-BP-01`, `R-PRO-BP-01`, `R-EXC-PC-01`

---

## 3. Rule Registration Boundary

Only the following rules are centrally registered in `00_Blueprint/RULE_REGISTRY.md`:

- `BLUEPRINT` scope rules
- `PLATFORM_LAYER` rules
- `PLATFORM_COMPONENT` rules
- `EXCEPTION` rules that deviate from any of the above

`APPLICATION`-scope rules are:
- local to the application
- discardable
- not centrally registered
- treated as conventions or specifications rather than governance

**APPLICATION-scope deviations from PROCESS rules** do not require central registration. They may be recorded as a local `sprint_conventions.md` or equivalent file within the application directory. These are conventions, not exceptions.

---

## 4. Canonical Source Principle

Each rule has exactly one canonical source.

- Rules must not be duplicated across multiple files
- All references must point to the canonical source
- Restatements in agent instructions or operational files are permitted only when necessary for agent context loading, and must be explicitly marked as non-authoritative (e.g. `_This is a local copy for agent context._`)
- If a restatement conflicts with the canonical source, the canonical source wins

---

## 5. Separation of Concerns

The following concepts must remain distinct:

- **Scope** — the semantic reach of the rule (which layer or component it governs)
- **Canonical Source** — the file where the rule is defined
- **Source of Authority** — the higher principle or artifact that justifies the rule

Scope does not imply storage location. A rule physically stored in `.claude/rules/` may have `SCOPE: BLUEPRINT`.

---

## 6. PROCESS Rule Applicability

PROCESS rules apply prospectively.

Artifacts produced before a PROCESS rule was established — including sprint folders, design documents, and delivery artifacts — are not considered violations and must not be retroactively updated.

When a PROCESS rule changes, only work initiated after the change date is required to conform. Completed sprints and closed deliverables are frozen.

---

## 7. Non-Rule Artifacts

Not all guidance is a rule.

The following are not considered formal rules:

- temporary process instructions
- slice-specific decisions
- local application conventions
- audit heuristics or classification logic
- agent behavioral notes

These may exist but must not be treated as canonical governance unless formally promoted.

---

## 8. Promotion Principle

A concept should be promoted to a formal rule only if:

- it is reused across multiple decisions or contexts, **or**
- losing it would cause system inconsistency, **or**
- it can be expressed as a stable, durable constraint

Otherwise it remains local or process-specific.

EXCEPTION rules are an explicit exception to this criterion: a single approved deviation from a registered rule warrants an EXCEPTION record regardless of reuse, because the absence of that record makes the violation invisible to future agents.
