---
name: Atlas Rule Source Map
description: Canonical source locations for Atlas constitutional rules and contracts; updated by audit passes
type: reference
---

# Atlas Rule and Contract Source Map

Last updated: 2026-03-24 (First Audit)

## Constitutional Rules — Canonical Sources

| Rule | Canonical Source | Notes |
|---|---|---|
| Four-layer model | `00_Blueprint/Atlas_Manifest.md` §0 | Restated in all 8 agents + CLAUDE.md — 10 copies total, all consistent |
| Architecture as AI interface | `00_Blueprint/Atlas_Manifest.md` §1,2,3 + `.claude/rules/01_role_of_architecture.md` | Rules file extends Manifest with preferred/avoid lists |
| Contracts > code | `00_Blueprint/Atlas_Manifest.md` §4 | Contract type enumeration (views, UI, API) only in Manifest |
| No hidden state | `00_Blueprint/Atlas_Manifest.md` §5 + `.claude/rules/04_no_hidden_state.md` | Ephemeral exception list only in rules file |
| Platform boundary | `00_Blueprint/Atlas_Manifest.md` §7 + `.claude/rules/02_platform_boundary.md` | Rules file has most detailed expression |
| Dependency direction | `.claude/rules/05_dependency_direction.md` | |
| Surface violations | `00_Blueprint/Atlas_Manifest.md` §9 + `.claude/rules/06_surface_violations.md` | |
| Contracts and boundaries | `.claude/rules/03_contracts_and_boundaries.md` | |
| Application tables are private | `00_Blueprint/Atlas_Manifest.md` §4 | |
| API contract promotion threshold | `00_Blueprint/Atlas_Manifest.md` §00.Blueprint contract types | Only stated in Manifest; no agent enforces it |

## Contracts — Canonical Sources

| Contract | Canonical Source | Status |
|---|---|---|
| UI Data Contract (Dataset/ApiError) | `.claude/rules/07_UI_Data_Contract.md` v1.0 | MISPLACED — should be in `00_Blueprint/UI/01_UI_Contract/`; that directory is empty |
| Chronicle Shared Calendar View | `00_Blueprint/SharedViews/chronicle.sql` | Sprint02 additions (application_group, sort_order) may not be reflected in file |
| Sprint Process Contract | `.claude/agents/sprint-orchestrator.md` | SHADOW — should be in `.claude/rules/08_sprint_process.md` |

## Known Shadow Governance Accumulation Sites

1. `.claude/agents/sprint-orchestrator.md` — contains the full sprint state machine, folder conventions, artifact naming, verdict vocabulary, human gate rule
2. `.claude/agent-memory/sprint-orchestrator/` — contains process exceptions (FoodTracker skip-specs) that should be formal governed artifacts
3. `CLAUDE.md` — contains security rules not present in `.claude/rules` or Manifest
4. `~/.claude/projects/.../memory/` (user-level) — Atlas Shell accepted violations deferred here; should be in repository

## Known Accepted Violations

| Location | Rules Violated | Disposition |
|---|---|---|
| `02_Platform/02_Atlas_Shell/src/apps/index.ts` | R-06 (platform boundary), R-11 (dependency direction) | Accepted; documented in user memory only (should be in `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md`) |
| `02_Platform/02_Atlas_Shell` (ShellErrorBoundary) | R-12 (UI Data Contract — request_id undefined) | Accepted; documented in user memory only |

## Known Process Exceptions

| Application | Exception | Formal Record |
|---|---|---|
| FoodTracker | Skips 10_specs layer and reviewer-spec-readiness step | Agent memory only (`project_foodtracker_sprint_conventions.md`) — NOT formally promoted |
| Chronicle Sprint01 | Uses `01_input/` instead of `00_input/` | Acknowledged in agent memory; not corrected |

## Active Gaps (from 2026-03-24 audit)

- G-01: No formal sprint process contract artifact
- G-02: No architectural exception record mechanism
- G-03: No rule governing shell integration (lazy Application import from Platform)
- G-04: No rule defining `.claude/rules` vs Blueprint placement boundary
- G-05: `app-definition-generator` skill and `implementation-reviewer` agent define overlapping schemas with no declared relationship

## Structural Deviations in Active Sprints

| Sprint | Deviation | Impact |
|---|---|---|
| `FoodTracker/Sprint04_Standard Dishes/` | `component_architecture.json` / `component_scaffold.json` instead of canonical names | Sprint-orchestrator cannot detect artifacts deterministically |
| `Chronicle/Sprint02_Swimlanes and Selector.md/` | Sprint folder name contains `.md` extension | Non-canonical; may cause filesystem or tooling issues |
| `Chronicle/Sprint01_First Heatmap/01_input/` | Uses `01_input/` prefix instead of `00_input/` | Deviation from canonical; orchestrator knows about this |
