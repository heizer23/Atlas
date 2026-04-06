---
name: Audit Sequencing Pattern
description: Validated sequencing for full system audits — proven effective in the 2026-04-06 run
type: feedback
---

## Full System Audit Sequence (validated)

1. Rule Compliance Reviewer — registry completeness, header format, canonical source integrity
2. Architecture/Structure Reviewer — layer placement, boundary violations, dependency direction
3. Security Reviewer — port exposure, privilege levels (run before contract/impl, not last)
4. Contract Compliance Reviewer — Dataset shape, error envelope, exception registration
5. Sprint Process Reviewer — state transitions, artifacts, verdict vocabulary
6. Implementation Reviewer — code vs. design spec, schema consistency

**Why this order works:**
- Governance findings (1+2) establish the baseline interpretation framework
- Security (3) surfaces exposure issues before implementation is examined
- Contract (4) must precede implementation (6) because you need to know what the contract says before judging whether code conforms
- Sprint process (5) reads sprint_state.json files which are independent of contract details
- Implementation (6) is last because it depends on knowing contracts, architecture, and design artifacts

## What to Check in Each Pass

### Rule Compliance
- All registered rules have canonical source files that exist
- No rules referenced in CLAUDE.md that aren't registered
- APPLICATION-scope exceptions are local; PLATFORM_COMPONENT exceptions are central
- sprint_conventions.md files cite which rules they override

### Architecture/Structure
- No cross-layer imports without registered exceptions
- Platform components: no domain logic
- Applications: no providing services to platform
- Shared views: in 00_Blueprint/SharedViews/ only

### Security
- Postgres: always 127.0.0.1 only
- Externally-exposed services: must have auth
- 0.0.0.0 bindings: need explicit justification
- Secrets: gitignored, never in compose environment values directly

### Contract Compliance
- All Python routers: import from platform_contracts, not local redefinitions
- All error responses: use api_error() from platform_errorhandling
- Non-Dataset shapes: must have registered ARCHITECTURE_EXCEPTIONS.md entry
- FormField definitions: frontend only, backend does not emit them

### Sprint Process
- sprint_state.json: `next_recommended_agent` null only when SPRINT_COMPLETE
- Human gate: must be explicitly recorded before implementation-reviewer invoked
- sprint_conventions.md: must exist in the specific app's directory to apply
- Required artifacts: check per state table in R-PRO-BP-01 §4

### Implementation
- init_schema() (where used): must match current schema.sql
- Row id field: always string, always present
- model_fields_set: required for nullable field clearing in PATCH endpoints
- platform_contracts import: never redefined locally
