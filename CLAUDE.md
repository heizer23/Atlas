# CLAUDE.md

## Purpose
Operational guidance for Claude Code in the ATLAS repository.

Authoritative reference:
- `00_Blueprint/Atlas_Manifest.md`

If guidance conflicts, surface the conflict explicitly.

## Atlas mental model
ATLAS uses four layers:

- `00_Blueprint` — governance and contracts
- `01_System` — access, control, rebuild, operation
- `02_Platform` — shared technical capabilities without domain logic
- `03_Application` — domain behavior and app-specific meaning

Do not place components outside this structure unless explicitly requested.

## Global rules
- Prefer concise, information-dense responses.
- Infer the simplest solution consistent with the existing structure.
- Prefer small, reviewable changes.
- Do not invent new components without need.
- Surface architectural conflicts before proceeding.

## Security

See R-OPS-BP-02 (`.claude/rules/R-OPS-BP-02_security.md`).

## Repository references
- Rule registry: `00_Blueprint/RULE_REGISTRY.md`
- Error handling: `02_Platform/03_ErrorHandling/`

## Agent delegation
Use specialized agents when appropriate.
Architecture classification, app creation, and major structural decisions belong to the architecture agent.