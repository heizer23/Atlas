# Atlas Audit Report

**Date:** 2026-03-24
**Auditor:** atlas-constitution-auditor
**Scope:** Full constitutional audit — rules, contracts, source-of-truth clarity, shadow governance, gaps, and placement correctness

---

## 1. Executive Summary

Atlas remains a substantially coherent constitutional system with a clear four-layer model, a well-defined primary governing document, and a functioning agent pipeline. However, the audit identifies meaningful fragmentation: constitutional rules are distributed across the Manifest, seven `.claude/rules` files, `CLAUDE.md`, and five major agent definitions — without an explicit delegation map that tells any reader which artifact is canonical for a given rule topic. Several important rules exist only in agent instructions and have never been promoted to Blueprint or `.claude/rules`. The UI Data Contract lives exclusively in `.claude/rules/07_UI_Data_Contract.md` instead of `00_Blueprint/UI/01_UI_Contract` — the location that CLAUDE.md and the app-local `CLAUDE.md` point to as authoritative. The `00_Blueprint/UI/` directories (`01_UI_Contract`, `02_UI_DesignLanguage`, `03_UI_Implementation`) are all empty, meaning references to them from multiple artifacts resolve to nothing. Additionally, a documented sprint folder naming convention is violated in two active sprint folders, and a confirmed sprint-process exception (FoodTracker skipping spec readiness) is recorded only in agent memory with no promotion to a formal process exception.

**Total artifacts reviewed:** 26
**Total rules identified:** 24
**Total contracts identified:** 3
**Critical findings:** 3
**High findings:** 5

### Top 5 Recommended Actions

1. Move `07_UI_Data_Contract.md` to `00_Blueprint/UI/01_UI_Contract/` or create a stub there that declares it the canonical source, resolving the broken reference from `CLAUDE.md` and `03_Application/TaskTracker/CLAUDE.md`.
2. Formally document the FoodTracker skip-specs convention as a controlled process exception in an Atlas process governance artifact (not only in agent memory).
3. Produce a canonical rule delegation map — a single document stating which artifact owns each rule topic — to make the distribution of rules across Manifest, `.claude/rules`, and agents intentional and navigable.
4. Promote the sprint folder naming convention from agent instruction prose to an explicit, machine-checkable rule in `.claude/rules` or Blueprint.
5. Decide and document the fate of the Atlas Shell rule violations (Rule 02, 05, 07) flagged in user memory as deferred — they are overdue for formal resolution or explicit permanent exception.

---

## 2. Definition Map

| Artifact | Apparent Role | Authority Level | Layer Scope | Notes |
|---|---|---|---|---|
| `00_Blueprint/Atlas_Manifest.md` | Primary constitutional document; architectural rules; layer definitions | canonical | All layers | 9 architectural rules; layer classification rules; mission statement |
| `CLAUDE.md` (repo root) | Operational guidance for Claude Code; references Manifest as authoritative | secondary governing | All layers | Restates 4-layer model; adds security rules; references UI governance and error handling; these are additions not present in Manifest |
| `.claude/rules/01_role_of_architecture.md` | Rule: architecture as AI interface | canonical | All layers | Mirrors Manifest Rule 1/3 but more detailed |
| `.claude/rules/02_platform_boundary.md` | Rule: what Platform may and may not do | canonical | 02_Platform | Extends Manifest Rule 7 |
| `.claude/rules/03_contracts_and_boundaries.md` | Rule: explicit contracts over inferred behavior | canonical | All layers | Extends Manifest Rule 4 |
| `.claude/rules/04_no_hidden_state.md` | Rule: durable state must be explicit and owned | canonical | All layers | Extends Manifest Rule 5 |
| `.claude/rules/05_dependency_direction.md` | Rule: dependency direction by layer | canonical | All layers | Extends Manifest Rule 7 |
| `.claude/rules/06_surface_violations.md` | Rule: surface conflicts explicitly | canonical | All layers | Mirrors Manifest Rule 9 |
| `.claude/rules/07_UI_Data_Contract.md` | Contract: UI data payload shape (Dataset, ApiError, Chart mappings) | canonical (misplaced) | 02_Platform / 03_Application | Lives in `.claude/rules` but is referenced as living in `00_Blueprint/UI/01_UI_Contract`; CLAUDE.md and TaskTracker CLAUDE.md point to the Blueprint directory which is empty |
| `00_Blueprint/UI/01_UI_Contract` | Referenced location for UI contract | empty — no content | All UI consumers | Directory exists, no files inside; all references to this location are broken |
| `00_Blueprint/UI/02_UI_DesignLanguage` | Referenced location for design language | empty — no content | UI | Directory exists, no files inside |
| `00_Blueprint/UI/03_UI_Implementation` | Referenced location for UI implementation standards | empty — no content | UI | Directory exists, no files inside |
| `00_Blueprint/SharedViews/chronicle.sql` | Shared database view contract for Calendar/Chronicle | canonical | 03_Application (Chronicle, FoodTracker, WorkoutTracker) | Concrete schema contract; domain-specific business logic embedded in view |
| `.claude/agents/designer-application.md` | Agent instruction + embedded process rules for app design | shadow (partial) | 03_Application | Contains rules about design quality, schema privacy, contract completeness that are not formally stated in `.claude/rules` |
| `.claude/agents/designer-platform.md` | Agent instruction + embedded process rules for platform design | shadow (partial) | 02_Platform | Old version alongside new designer-platform (archived). Contains overlapping platform boundary rules |
| `.claude/agents/implementer.md` | Agent instruction + embedded implementation rules | shadow (partial) | 03_Application | Contains "simplicity rule", UI implementation rule; not in `.claude/rules` |
| `.claude/agents/design-reviewer.md` | Agent instruction + review process rules | shadow (partial) | All layers | Embeds severity definitions, review dimensions, rule reference list |
| `.claude/agents/design-corrector.md` | Agent instruction + correction process rules | shadow (partial) | 03_Application | Embeds source-of-truth hierarchy for corrections |
| `.claude/agents/sprint-orchestrator.md` | Agent instruction + sprint state machine definition | shadow (partial) | All layers | Contains canonical sprint states, transition rules, sprint folder structure — none of these exist anywhere else |
| `.claude/agents/reviewer-spec-readiness.md` | Agent instruction + spec evaluation rules | shadow (partial) | 03_Application | References Atlas UI Data Contract; embeds spec readiness criteria |
| `.claude/agents/implementation-reviewer.md` | Agent instruction + review output rules | shadow (partial) | 03_Application | Embeds conformance rules, evidence rules |
| `.claude/agents/atlas-constitution-auditor.md` | Agent instruction for this audit role | shadow (partial) | All layers | Contains audit method and classification system |
| `.claude/Archive/old_pf-designer_v0.md` | Archived prior version of platform designer | obsolete | 02_Platform | Named `platform-designer` in frontmatter; superseded by `designer-platform.md` |
| `.claude/agent-memory/sprint-orchestrator/project_foodtracker_sprint_conventions.md` | Process exception: FoodTracker skips spec-readiness | shadow rule | 03_Application | A process exception recorded only as agent memory, not as a formal governed exception |
| `03_Application/TaskTracker/CLAUDE.md` | App-local operational guidance | local | 03_Application/TaskTracker | Correctly scoped local; points to broken Blueprint UI reference |
| `01_System/03.ProjectLog.md` | Dynamic operational state document | development artifact | 01_System | Contains live infrastructure values and decisions; not a constitutional artifact |
| `.claude/skills/` files | Mostly empty or stub content | negligible | — | `code-navigation.md`, `repo-search.md`, `bug-investigation.md`, `ui-generation.md` are empty or near-empty stubs |
| `.claude/prompts/sprint-planning.md` | Stub prompt | negligible | — | 4-line stub, no governance content |

---

## 3. Rule Registry

### R-01
- **rule_id:** R-01
- **title:** Four-Layer System Model
- **statement:** The system is understood through four layers: Blueprint (governance), System (access/operation), Platform (shared capabilities), Application (domain behavior). All design decisions must be expressible in this model.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §0; Layer Definitions
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Restated verbatim in `CLAUDE.md` (Atlas mental model section), `designer-application.md`, `designer-platform.md`, `implementer.md`, `design-reviewer.md`, `design-corrector.md`, `sprint-orchestrator.md`, `reviewer-spec-readiness.md`, `implementation-reviewer.md`, `atlas-constitution-auditor.md`
- **conflicts:** None — consistent across all instances
- **enforcement_status:** Actively enforced via agent instructions
- **notes:** The layer model is restated in every single agent. This is functionally appropriate for agent context loading but creates ten copies of the same definition. The Manifest is canonical; all others are copies.

---

### R-02
- **rule_id:** R-02
- **title:** Architecture Is the AI Interface
- **statement:** Architecture, contracts, and structure are first-class artifacts. Clarity is a design constraint enabling LLM inspection, reasoning, and extension from explicit artifacts alone.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §1, §2, §3
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Restated as independent rule in `.claude/rules/01_role_of_architecture.md`; referenced in designer agents as rule to apply
- **conflicts:** None
- **enforcement_status:** Referenced by designer and reviewer agents
- **notes:** `.claude/rules/01_role_of_architecture.md` extends the Manifest with preferred/avoid lists that do not appear in the Manifest. The Manifest does not acknowledge this extension file as its elaboration.

---

### R-03
- **rule_id:** R-03
- **title:** Contracts Are More Durable Than Code
- **statement:** Meaning, guarantees, and boundaries are preserved through contracts. Application code is replaceable. Contracts and data objects are changed deliberately. Application table schemas are private; only shared views are contracts.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §4
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Elaborated in `.claude/rules/03_contracts_and_boundaries.md`
- **conflicts:** None
- **enforcement_status:** Referenced by designers and reviewers
- **notes:** The Manifest §4 states "contracts live in 00.Blueprint and are enumerated as: shared database views, UI definitions, and API definitions (TBD)." This is the only place the enumeration of contract types appears. The `.claude/rules` elaboration does not repeat this enumeration.

---

### R-04
- **rule_id:** R-04
- **title:** No Hidden State
- **statement:** All durable state must be inspectable, versioned, and reachable through defined system or platform mechanisms. Ephemeral state is exempt.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §5
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Elaborated with explicit ephemeral/durable distinction in `.claude/rules/04_no_hidden_state.md`
- **conflicts:** None
- **enforcement_status:** Enforced by design reviewers; sprint-orchestrator restates this rule explicitly in its "Atlas Principles" section
- **notes:** The `.claude/rules` elaboration adds the ephemeral exception list, which is not present in the Manifest. This is additive and non-conflicting.

---

### R-05
- **rule_id:** R-05
- **title:** Stability at Edges, Flexibility Inside
- **statement:** Blueprint and System change slowly. Applications are expected to change rapidly or disappear.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §6
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** soft
- **duplicates:** None
- **conflicts:** None
- **enforcement_status:** Stated but not operationally enforced by any agent
- **notes:** This rule has no agent enforcement surface. It is a design principle only.

---

### R-06
- **rule_id:** R-06
- **title:** Platform Provides Capabilities, Applications Provide Meaning
- **statement:** Platform contains no domain logic. Applications never provide platform services.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §7
- **authority_level:** canonical
- **layer_scope:** 02_Platform, 03_Application
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Elaborated in `.claude/rules/02_platform_boundary.md` (substantial elaboration); restated in `designer-platform.md`, `designer-application.md`, `implementer.md`, `design-reviewer.md`
- **conflicts:** Known violation in `02_Platform/Atlas_Shell/src/apps/index.ts` — application-specific nav content embedded in platform component; documented in user memory as accepted exception
- **enforcement_status:** Enforced by design reviewer; known exception accepted without formal exception record in Blueprint
- **notes:** The violation is documented only in user-level memory (`project_atlas_shell_rule_exceptions.md`). There is no formal architectural exception record.

---

### R-07
- **rule_id:** R-07
- **title:** General Capabilities Over Predefined Workflows
- **statement:** The system provides composable primitives; processes emerge from recombination. Design decisions in this area are conservative and human-led.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §8
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** soft
- **duplicates:** None
- **enforcement_status:** Not operationally enforced
- **notes:** Design principle only. No agent enforces it.

---

### R-08
- **rule_id:** R-08
- **title:** Violations Are Surfaced, Not Tolerated
- **statement:** If a proposed design conflicts with this manifest, it must be flagged before proceeding. Regular system audits compare all documentation and code against this manifest.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §9
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Restated as `.claude/rules/06_surface_violations.md`
- **conflicts:** None
- **enforcement_status:** Enforced by design-reviewer and design-corrector; sprint-orchestrator enforces for process violations
- **notes:** The audit obligation ("Regular system audits") has no defined schedule or trigger mechanism in any Atlas artifact. The atlas-constitution-auditor agent exists to perform this but is invoked ad hoc.

---

### R-09
- **rule_id:** R-09
- **title:** LLM Legibility as Design Constraint
- **statement:** Standard libraries, idiomatic patterns, and explicit structure are preferred over clever or minimal implementations. Clarity is preferred over code size or performance micro-optimizations.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §3
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** constitutional
- **hardness:** soft
- **duplicates:** Elaborated in `.claude/rules/01_role_of_architecture.md`
- **enforcement_status:** Referenced by implementer agent; not mechanically enforced
- **notes:** The implementer agent restates this as "boring solutions over clever ones" and "standard libraries."

---

### R-10
- **rule_id:** R-10
- **title:** Platform Boundary Elaboration
- **statement:** A Platform component: is primarily generic, intended for reuse, does not own domain meaning or business rules, is persistent or long-lived. Platform may expose primitives influenced by application needs but must not encode workflow decisions or absorb behavior meaningful only within one application.
- **source_artifact:** `.claude/rules/02_platform_boundary.md`
- **source_section:** Full document
- **authority_level:** canonical
- **layer_scope:** 02_Platform
- **rule_type:** elaboration of R-06
- **hardness:** hard
- **duplicates:** Partially restated in `designer-platform.md` agent instructions
- **conflicts:** None
- **enforcement_status:** Referenced by design-reviewer; checked by platform designer
- **notes:** This is the most detailed expression of the platform boundary rule. It does not reference the Manifest explicitly.

---

### R-11
- **rule_id:** R-11
- **title:** Dependency Direction
- **statement:** A Platform component may depend on Blueprint contracts and System capabilities. It must not absorb Application logic. Dependencies must flow in declared, explicitly designed directions. No bidirectional or upward coupling.
- **source_artifact:** `.claude/rules/05_dependency_direction.md`
- **source_section:** Full document
- **authority_level:** canonical
- **layer_scope:** All layers
- **rule_type:** elaboration of R-06
- **hardness:** hard
- **duplicates:** Restated in designer agents; reviewers check this explicitly
- **conflicts:** Known violation: `02_Platform/Atlas_Shell/src/apps/index.ts` imports Application layer lazily. Accepted as exception, documented in user memory only.
- **enforcement_status:** Actively enforced by design-reviewer and designer agents
- **notes:** The known Atlas Shell violation inverts this rule.

---

### R-12
- **rule_id:** R-12
- **title:** UI Data Contract Default Rule
- **statement:** Any Atlas endpoint or interface intended to supply data for UI rendering must return a payload conforming to a stable UI data contract. Default is Dataset or ApiError. Alternative contracts require explicit stable contract definition.
- **source_artifact:** `.claude/rules/07_UI_Data_Contract.md`
- **source_section:** Core Rule; Default-First Rule
- **authority_level:** canonical (misplaced)
- **layer_scope:** 02_Platform, 03_Application (all UI-facing endpoints)
- **rule_type:** contract + rule
- **hardness:** hard
- **duplicates:** None — but referenced by location `00_Blueprint/UI/01_UI_Contract` in `CLAUDE.md` and `03_Application/TaskTracker/CLAUDE.md`, neither of which points to the actual file location
- **conflicts:** Placement conflict: rule lives in `.claude/rules/07_UI_Data_Contract.md` but is referenced as if it lives in `00_Blueprint/UI/01_UI_Contract/`. The Blueprint directory is empty.
- **enforcement_status:** Actively enforced by designers and reviewers; reviewer-spec-readiness specifically checks Dataset compatibility
- **notes:** This is the most significant placement problem in the current governance set. See Finding F-01.

---

### R-13
- **rule_id:** R-13
- **title:** Application Tables Are Private
- **statement:** Application table schemas are not contracts. They are private to the application and live inside it. Only views derived from application tables are contracts.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Architectural Rules §4; Layer Definitions (03.Application)
- **authority_level:** canonical
- **layer_scope:** 03_Application
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** Restated in `designer-application.md` quality rules ("Private tables remain private")
- **conflicts:** None
- **enforcement_status:** Enforced by design-reviewer (Persistence Consistency check)
- **notes:** Well-enforced. No drift observed.

---

### R-14
- **rule_id:** R-14
- **title:** Sprint Folder Naming Convention
- **statement:** Sprint folder naming convention: `Sprint<N>_<Title>/` (e.g., `Sprint01_Core_Shell_Navigation/`)
- **source_artifact:** `.claude/agents/designer-platform.md` (Required Inputs §1); `.claude/agents/designer-application.md` (Required Inputs §1)
- **source_section:** Required Inputs, item 1
- **authority_level:** shadow
- **layer_scope:** 03_Application, 02_Platform (sprint folders)
- **rule_type:** process convention
- **hardness:** soft
- **duplicates:** Also implied in `sprint-orchestrator.md` canonical folder structure
- **conflicts:** Violated by `03_Application/Chronicle/Sprint02_Swimlanes and Selector.md` (contains `.md` file extension in folder name) and by `03_Application/Chronicle/Sprint01_First Heatmap/01_input/` (non-canonical `01_input` vs `00_input` prefix)
- **enforcement_status:** Not enforced; violations present in repository
- **notes:** This rule exists only in agent instruction prose. It has no formal home in `.claude/rules` or Blueprint.

---

### R-15
- **rule_id:** R-15
- **title:** Sprint Input Folder Naming Convention
- **statement:** Sprint input files live at `00_input/draft.md` within the sprint folder.
- **source_artifact:** `.claude/agents/designer-application.md`; `.claude/agents/sprint-orchestrator.md`
- **source_section:** Required Inputs §1; Canonical Sprint Folder Structure
- **authority_level:** shadow
- **layer_scope:** All sprint folders
- **rule_type:** process convention
- **hardness:** soft
- **duplicates:** Stated in multiple agent instructions
- **conflicts:** Violated in `03_Application/Chronicle/Sprint01_First Heatmap/` which uses `01_input/` instead of `00_input/`. This is acknowledged in sprint-orchestrator agent memory.
- **enforcement_status:** Not enforced mechanically; violation present and accepted
- **notes:** Convention exists only in agent instructions.

---

### R-16
- **rule_id:** R-16
- **title:** Design Artifact File Naming Convention
- **statement:** Sprint design artifacts are named `architecture.json` and `scaffolding.json` inside `20_design/`.
- **source_artifact:** `.claude/agents/designer-application.md`; `.claude/agents/designer-platform.md`; `.claude/agents/sprint-orchestrator.md`
- **source_section:** Produce Artifacts; Canonical Sprint Folder Structure
- **authority_level:** shadow
- **layer_scope:** All sprint design phases
- **rule_type:** process convention
- **hardness:** soft
- **duplicates:** Stated in multiple agent instructions
- **conflicts:** Violated in `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/` which uses `component_architecture.json` and `component_scaffold.json` instead of canonical names. The sprint-orchestrator and design-reviewer agents look for `architecture.json` and `scaffolding.json` explicitly.
- **enforcement_status:** Not enforced; violation breaks orchestrator artifact detection
- **notes:** Deviation in Sprint04 may cause `sprint-orchestrator` and `implementation-reviewer` to fail to detect artifacts. See Finding F-05.

---

### R-17
- **rule_id:** R-17
- **title:** Security: Least Privilege
- **statement:** Default to least privilege and minimal exposure. Warn when a proposal introduces unnecessary exposure. Do not suggest opening ports unless clearly required and secured.
- **source_artifact:** `CLAUDE.md`
- **source_section:** Security
- **authority_level:** shadow
- **layer_scope:** All layers
- **rule_type:** operational guideline
- **hardness:** soft
- **duplicates:** Partially restated in `design-reviewer.md` §7 ("Security and Exposure")
- **conflicts:** None
- **enforcement_status:** Referenced by design-reviewer; not in `.claude/rules` or Manifest
- **notes:** This is a cross-cutting security rule with no formal home in the constitutional layer. Lives only in `CLAUDE.md` and agent instructions.

---

### R-18
- **rule_id:** R-18
- **title:** Sprint Canonical States
- **statement:** Sprint state machine has exactly 10 legal states: DRAFT_READY, SPECS_READY, DESIGN_CREATED, DESIGN_REVIEWED_CHANGES_REQUIRED, DESIGN_APPROVED, IMPLEMENTATION_IN_PROGRESS, AWAITING_HUMAN_REVIEW, IMPLEMENTATION_REVIEWED, SPRINT_COMPLETE, BLOCKED.
- **source_artifact:** `.claude/agents/sprint-orchestrator.md`
- **source_section:** Canonical Sprint States
- **authority_level:** shadow
- **layer_scope:** All sprint coordination
- **rule_type:** process definition
- **hardness:** hard
- **duplicates:** None
- **conflicts:** None
- **enforcement_status:** Enforced by sprint-orchestrator agent internally
- **notes:** The full sprint state machine exists only inside agent instructions. It is a significant process contract with no formal home.

---

### R-19
- **rule_id:** R-19
- **title:** Agent Reviewer Verdict Vocabulary
- **statement:** Valid reviewer verdicts are exactly: READY, CHANGES_REQUIRED, APPROVED, BLOCKED, COMPLETE, REJECTED. Non-conforming verdicts mark the sprint BLOCKED.
- **source_artifact:** `.claude/agents/sprint-orchestrator.md`
- **source_section:** Reviewer Verdict Rules
- **authority_level:** shadow
- **layer_scope:** All sprint review phases
- **rule_type:** process contract
- **hardness:** hard
- **duplicates:** None
- **conflicts:** The design-reviewer agent uses verdict labels "APPROVED", "APPROVED_WITH_CHANGES", "BLOCKED" — not from the orchestrator's allowed list. "APPROVED_WITH_CHANGES" is not a valid orchestrator verdict; the orchestrator would need to map this.
- **enforcement_status:** Partially broken — see Finding F-03
- **notes:** design-reviewer produces "APPROVED_WITH_CHANGES" but orchestrator only recognizes "APPROVED" and "CHANGES_REQUIRED". This is a latent conflict.

---

### R-20
- **rule_id:** R-20
- **title:** Human Review Gate Before Implementation Review
- **statement:** After implementation, the sprint must pause for a human review gate before implementation review proceeds. Human approval must be explicitly recorded in state files.
- **source_artifact:** `.claude/agents/sprint-orchestrator.md`
- **source_section:** Human Review Gate
- **authority_level:** shadow
- **layer_scope:** All sprint implementation phases
- **rule_type:** process rule
- **hardness:** hard
- **duplicates:** None — exists only in sprint-orchestrator
- **enforcement_status:** Enforced by sprint-orchestrator
- **notes:** Important governance gate with no formal home outside agent instructions.

---

### R-21
- **rule_id:** R-21
- **title:** Agent Memory Must Not Substitute for Architectural State
- **statement:** Durable process state must live in files, not in chat memory.
- **source_artifact:** `.claude/agents/sprint-orchestrator.md`
- **source_section:** Atlas Principles §1
- **authority_level:** shadow
- **layer_scope:** All sprint coordination
- **rule_type:** process rule
- **hardness:** hard
- **duplicates:** Aligns with R-04 (no hidden state) but stated separately only in orchestrator context
- **conflicts:** None
- **enforcement_status:** Enforced by sprint-orchestrator
- **notes:** This is an application of R-04 to sprint process state. The connection to R-04 is implicit.

---

### R-22
- **rule_id:** R-22
- **title:** No Governance Replication in Design Artifacts
- **statement:** Design agents must not copy or restate rules, requirements, or governance text from repository files. Reference the file path instead.
- **source_artifact:** `.claude/agents/designer-application.md`; `.claude/agents/designer-platform.md`
- **source_section:** Quality Rules §2
- **authority_level:** shadow
- **layer_scope:** 02_Platform, 03_Application (design phase)
- **rule_type:** process rule
- **hardness:** soft
- **duplicates:** None
- **conflicts:** None
- **enforcement_status:** Stated in agent quality rules; not independently enforced
- **notes:** Governance rule about governance duplication — a meta-rule. Has no formal home.

---

### R-23
- **rule_id:** R-23
- **title:** Prefer Small, Reviewable Changes
- **statement:** Prefer small, reviewable changes. Do not invent new components without need.
- **source_artifact:** `CLAUDE.md`
- **source_section:** Global rules
- **authority_level:** shadow
- **layer_scope:** All layers
- **rule_type:** operational guideline
- **hardness:** soft
- **duplicates:** Restated in `designer-platform.md` (Quality Standards), `designer-application.md` (Behavioral Constraints), `implementer.md` (Implementation Principles)
- **conflicts:** None
- **enforcement_status:** Guidance only
- **notes:** Reasonable operational default. Lives in CLAUDE.md and agents but not in `.claude/rules` or Blueprint.

---

### R-24
- **rule_id:** R-24
- **title:** API Contract Promotion Threshold
- **statement:** An API contract is promoted to Blueprint only when two or more apps need to consume or produce the same shape. Until then, it lives as the app's AppDefinition plus the router code.
- **source_artifact:** `00_Blueprint/Atlas_Manifest.md`
- **source_section:** Layer Definitions — 00.Blueprint, Contract types
- **authority_level:** canonical
- **layer_scope:** 03_Application, 00_Blueprint
- **rule_type:** constitutional
- **hardness:** hard
- **duplicates:** None
- **conflicts:** None
- **enforcement_status:** Not mechanically enforced; no agent checks this promotion threshold
- **notes:** Important rule for deciding when application contracts must be elevated. No agent currently enforces the promotion trigger.

---

## 4. Contract Registry

### C-01
- **contract_id:** C-01
- **name:** UI Data Contract (Dataset / ApiError)
- **source_of_truth:** `.claude/rules/07_UI_Data_Contract.md`
- **version:** v1.0
- **scope:** All Atlas endpoints and interfaces supplying data for UI rendering
- **producers:** All application and platform endpoints that serve UI-rendered data
- **consumers:** All frontend components consuming Atlas data payloads; `reviewer-spec-readiness`; `design-reviewer`; `designer-application`; `implementer`
- **known_redefinitions:** None confirmed — but `CLAUDE.md` references `00_Blueprint/UI/01_UI_Contract` as the location (empty); `TaskTracker/CLAUDE.md` references the same empty directory
- **status:** active — enforced, but misplaced
- **notes:** This contract is actively used and well-enforced. Its canonical artifact location (`07_UI_Data_Contract.md` inside `.claude/rules`) does not match the declared reference location (`00_Blueprint/UI/01_UI_Contract`). The Blueprint directory is empty. This is the most significant contract placement problem in Atlas. The contract also contains both the TypeScript type definitions and the Python Pydantic models inline, which means consumers must cross-reference agent instructions rather than a first-class Blueprint artifact.

---

### C-02
- **contract_id:** C-02
- **name:** Chronicle Shared Calendar View
- **source_of_truth:** `00_Blueprint/SharedViews/chronicle.sql`
- **version:** v2 (Sprint02 extended with `application_group`, `sort_order`)
- **scope:** Chronicle application (consumer); FoodTracker, WorkoutTracker (implicit producers via SQL view)
- **producers:** FoodTracker (`foodtracker.food_logs`), WorkoutTracker (`workout.workout_log`)
- **consumers:** Chronicle application
- **known_redefinitions:** Sprint02 extension documented in agent memory only (`project_chronicle_sprint_conventions.md`); the SQL file itself has not been confirmed updated to Sprint02 schema in this audit
- **status:** active
- **notes:** This is a well-placed contract — lives in `00_Blueprint/SharedViews/`. However, the Sprint02 schema additions (`application_group`, `sort_order`) are documented in agent memory but the physical SQL file has not been verified as updated to include them. If the Sprint02 changes were only applied at the database level and the Blueprint SQL is not updated, the contract definition is stale. The Manifest (§4) states shared database views are a contract type — this is consistent.

---

### C-03
- **contract_id:** C-03
- **name:** Sprint Process Contract (State Machine, Folder Structure, Artifact Naming)
- **source_of_truth:** `.claude/agents/sprint-orchestrator.md`
- **version:** unversioned
- **scope:** All Atlas sprints
- **producers:** sprint-orchestrator (writes `sprint_state.json`, `orchestrator_log.md`)
- **consumers:** All sprint agents; human operators
- **known_redefinitions:** Sprint folder naming convention also appears in designer agent instructions; FoodTracker sprint exception recorded in agent memory only
- **status:** active — but misplaced
- **notes:** The sprint process contract is significant enough to warrant its own Blueprint or `.claude/rules` artifact. It currently lives entirely inside agent instructions. Version is undeclared. Process exceptions (FoodTracker) are tracked only in memory.

---

## 5. Findings

### F-01
- **finding_id:** F-01
- **category:** misplaced_definition
- **severity:** critical
- **title:** UI Data Contract Lives in `.claude/rules` but Is Referenced as Living in Empty Blueprint Directory
- **claim:** `CLAUDE.md` and `03_Application/TaskTracker/CLAUDE.md` both cite `00_Blueprint/UI/01_UI_Contract` as the location of UI governance. That directory exists but contains no files. The actual UI Data Contract lives at `.claude/rules/07_UI_Data_Contract.md`. Any agent or human following the stated reference finds nothing.
- **evidence:**
  - `CLAUDE.md` line 34: `UI governance: 00_Blueprint/UI/`
  - `03_Application/TaskTracker/CLAUDE.md` line 13: `UI contract: 00_Blueprint/UI/01_UI_Contract`
  - `00_Blueprint/UI/01_UI_Contract` directory: empty (confirmed via Glob — no files)
  - Actual contract at: `.claude/rules/07_UI_Data_Contract.md` (7,000+ words, v1.0 status)
- **why_it_matters:** Agents and humans following the stated reference location find an empty directory. The contract is only reachable if you already know its non-canonical location. This breaks the "architecture is the primary interface to AI" principle — an agent inspecting Blueprint finds no UI contract there.
- **affected_artifacts:** `CLAUDE.md`, `03_Application/TaskTracker/CLAUDE.md`, `00_Blueprint/UI/01_UI_Contract/` (empty), `.claude/rules/07_UI_Data_Contract.md`
- **recommended_action:** Move `07_UI_Data_Contract.md` into `00_Blueprint/UI/01_UI_Contract/UI_Data_Contract.md`, update `.claude/rules/07_UI_Data_Contract.md` to a redirect stub (one line: "This contract has moved to `00_Blueprint/UI/01_UI_Contract/UI_Data_Contract.md`"), and update agent instructions that reference the `.claude/rules` path.
- **promotion_target:** `00_Blueprint/UI/01_UI_Contract/`
- **confidence:** high

---

### F-02
- **finding_id:** F-02
- **category:** shadow_rule
- **severity:** high
- **title:** Sprint Process Contract Exists Only Inside Agent Instructions
- **claim:** The Atlas sprint state machine — including canonical states, allowed transitions, human review gate, folder structure, artifact naming, and reviewer verdict vocabulary — is defined exclusively inside `.claude/agents/sprint-orchestrator.md`. This is a significant process contract governing every sprint in Atlas and has no presence in Blueprint or `.claude/rules`.
- **evidence:**
  - Sprint states defined in `sprint-orchestrator.md` §"Canonical Sprint States": 10 states listed
  - Sprint folder structure defined in `sprint-orchestrator.md` §"Canonical Sprint Folder Structure"
  - Human review gate rule defined in `sprint-orchestrator.md` §"Human Review Gate"
  - None of these appear in any `.claude/rules` file, the Manifest, or any Blueprint artifact
- **why_it_matters:** Process contracts are at least as important to Atlas coherence as data contracts. If the sprint-orchestrator agent were replaced or its instructions changed, the sprint process contract would change without any constitutional record. The state machine is an explicit governance artifact masquerading as an agent instruction.
- **affected_artifacts:** `.claude/agents/sprint-orchestrator.md`
- **recommended_action:** Extract the sprint process contract (states, transitions, folder structure, artifact naming, reviewer vocabulary) from the orchestrator instructions into a dedicated `.claude/rules/08_sprint_process.md` or `00_Blueprint/SprintProcess.md`. The orchestrator instructions should reference that document rather than embedding it.
- **promotion_target:** `.claude/rules/08_sprint_process.md`
- **confidence:** high

---

### F-03
- **finding_id:** F-03
- **category:** conflict
- **severity:** high
- **title:** Reviewer Verdict Vocabulary Conflict Between `design-reviewer` and `sprint-orchestrator`
- **claim:** The `design-reviewer` agent produces verdict labels including `APPROVED_WITH_CHANGES`. The `sprint-orchestrator` defines exactly six valid verdicts (`READY`, `CHANGES_REQUIRED`, `APPROVED`, `BLOCKED`, `COMPLETE`, `REJECTED`). `APPROVED_WITH_CHANGES` is not in this list. When the orchestrator reads a design review with this verdict, it cannot resolve the state and should mark the sprint BLOCKED per its own rules.
- **evidence:**
  - `design-reviewer.md` §Verdict options: `APPROVED | APPROVED_WITH_CHANGES | BLOCKED`
  - `sprint-orchestrator.md` §Reviewer Verdict Rules: "only treat these verdicts as valid: READY, CHANGES_REQUIRED, APPROVED, BLOCKED, COMPLETE, REJECTED"
  - Sprint04 design review file `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/design_review.md` line 2: `Status: APPROVED_WITH_CHANGES`
  - Sprint04 `sprint_state.json` would need to handle this mapping — not confirmed verified
- **why_it_matters:** This is a direct contract conflict between two agents in the same pipeline. The review produces a verdict the orchestrator does not recognize as valid. Either the sprint gets incorrectly BLOCKED or the orchestrator silently misinterprets the verdict — both are failures.
- **affected_artifacts:** `.claude/agents/design-reviewer.md`, `.claude/agents/sprint-orchestrator.md`, `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/design_review.md`
- **recommended_action:** Align the verdict vocabulary. Either: (a) add `APPROVED_WITH_CHANGES` to the orchestrator's valid verdict list with a defined transition (route to design-corrector), or (b) change the design-reviewer to produce `CHANGES_REQUIRED` instead of `APPROVED_WITH_CHANGES`. Document the canonical verdict vocabulary as a shared contract, not embedded in two separate agent instructions.
- **promotion_target:** `.claude/rules/08_sprint_process.md` (shared verdict vocabulary)
- **confidence:** high

---

### F-04
- **finding_id:** F-04
- **category:** shadow_rule
- **severity:** high
- **title:** FoodTracker Spec-Readiness Skip Is a Process Exception Recorded Only in Agent Memory
- **claim:** FoodTracker sprints skip the `10_specs/` layer and the `reviewer-spec-readiness` step entirely. This is a confirmed, intentional process exception. It is recorded only in `.claude/agent-memory/sprint-orchestrator/project_foodtracker_sprint_conventions.md` — agent operational memory — not in any formal process governance artifact.
- **evidence:**
  - `project_foodtracker_sprint_conventions.md`: "FoodTracker sprints skip the `10_specs/` layer entirely. The `reviewer-specs-readiness` agent is not invoked... This is a confirmed convention, not a process violation."
  - Sprint-orchestrator canonical states include `SPECS_READY` as a required state
  - No `.claude/rules` file, Blueprint artifact, or sprint-local document formally documents this exception
- **why_it_matters:** Process exceptions recorded only in agent memory are fragile. Memory can be cleared, contexts can be reset, and new agents will not inherit undocumented exceptions. An exception that is "confirmed" but unwritten is shadow governance. If the exception is legitimate, it should be a first-class governed artifact.
- **affected_artifacts:** `.claude/agent-memory/sprint-orchestrator/project_foodtracker_sprint_conventions.md`, `.claude/agents/sprint-orchestrator.md`
- **recommended_action:** Promote to a formal process exception document. Options: (a) create a `00_input/sprint_conventions.md` in the FoodTracker application folder that documents the exception, and update the sprint-orchestrator to check for a per-application `sprint_conventions.md` that may override canonical state transitions; or (b) make the spec-readiness step optional by default (with opt-in), removing the need for exceptions.
- **promotion_target:** `03_Application/FoodTracker/sprint_conventions.md` or `.claude/rules/08_sprint_process.md` with exception mechanism
- **confidence:** high

---

### F-05
- **finding_id:** F-05
- **category:** misplaced_definition
- **severity:** high
- **title:** Sprint04 Design Artifacts Use Non-Canonical File Names, Breaking Orchestrator Detection
- **claim:** Sprint04 (`FoodTracker/Sprint04_Standard Dishes/`) uses `component_architecture.json` and `component_scaffold.json` instead of the canonical `architecture.json` and `scaffolding.json`. The sprint-orchestrator agent, design-reviewer agent, design-corrector agent, and implementation-reviewer agent all look for the canonical file names explicitly.
- **evidence:**
  - Canonical artifact names per `sprint-orchestrator.md` §DESIGN_CREATED required artifacts: `20_design/architecture.json`, `20_design/scaffolding.json`
  - Actual Sprint04 files: `20_design/component_architecture.json`, `20_design/component_scaffold.json` (confirmed via Glob)
  - `design-reviewer.md` §Required Design Artifacts: `20_design/architecture.json`, `20_design/scaffolding.json`
  - `design_review.md` Sprint04 line 13 references `component_architecture.json` (reviewer adapted to non-canonical name)
- **why_it_matters:** Sprint04 is currently in a state that the orchestrator cannot deterministically resolve because the required artifact names don't match the canonical specification. If the orchestrator is invoked, it will likely declare the sprint BLOCKED due to missing `architecture.json`. Any downstream agent that relies on the canonical name will fail to find the artifacts.
- **affected_artifacts:** `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_architecture.json`, `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_scaffold.json`, `.claude/agents/sprint-orchestrator.md`
- **recommended_action:** Either rename the Sprint04 files to canonical names, or add a formal escape mechanism in the sprint process for multi-component sprints where designers use component-prefixed names. The latter would require updating the orchestrator's artifact detection logic and documenting the convention.
- **promotion_target:** Not applicable — this is a concrete artifact naming violation
- **confidence:** high

---

### F-06
- **finding_id:** F-06
- **category:** duplicate_rule
- **severity:** medium
- **title:** Four-Layer Model Restated in Every Agent Instruction (Ten Copies)
- **claim:** The four-layer model (Blueprint/System/Platform/Application) is restated verbatim or near-verbatim in all eight agent definitions, `CLAUDE.md`, and the Manifest — ten total instances. No instance delegates to another or states it is a copy.
- **evidence:**
  - Manifest §0: primary definition
  - `CLAUDE.md` §Atlas mental model: restatement
  - All eight `.claude/agents/*.md` files: each contains "ATLAS uses four layers" section
- **why_it_matters:** Ten copies without delegation create maintenance risk. If the layer model changes, all ten must be updated. More subtly, each copy is slightly different in wording, which creates ambiguity about which copy is authoritative.
- **affected_artifacts:** `CLAUDE.md`, all eight agent files
- **recommended_action:** The restatement in agent instructions is functionally necessary for agent context loading and cannot be removed without loss of agent function. However, each instance should include a pointer: "Layer model canonical definition: `00_Blueprint/Atlas_Manifest.md` §0." This makes the delegation explicit without requiring agents to load the full Manifest.
- **promotion_target:** Not applicable — delegation pointer needed, not promotion
- **confidence:** high

---

### F-07
- **finding_id:** F-07
- **category:** shadow_rule
- **severity:** medium
- **title:** Security Rule (Least Privilege) Lives Only in `CLAUDE.md` and Agent Instructions
- **claim:** The security rule — default to least privilege, warn on unnecessary exposure, do not suggest opening ports unless secured — appears in `CLAUDE.md` and is referenced by `design-reviewer.md` §7 but exists nowhere in `.claude/rules` or the Manifest.
- **evidence:**
  - `CLAUDE.md` §Security: three bullet rules
  - `design-reviewer.md` §2, item 7: "Security and Exposure — Does the design default to least privilege?"
  - No `.claude/rules` file covers security
  - Manifest does not mention security as an architectural rule
- **why_it_matters:** Security rules are cross-cutting and architectural. A rule that only lives in `CLAUDE.md` is less durable than a rule in `.claude/rules`. Agents that do not load `CLAUDE.md` (or future agents added without it) will not have this constraint.
- **affected_artifacts:** `CLAUDE.md`, `.claude/agents/design-reviewer.md`
- **recommended_action:** Promote to `.claude/rules/09_security.md` covering: least privilege default, exposure warnings, port exposure constraints. Reference from `CLAUDE.md` rather than redefining there.
- **promotion_target:** `.claude/rules/09_security.md`
- **confidence:** medium

---

### F-08
- **finding_id:** F-08
- **category:** gap
- **severity:** medium
- **title:** No Formal Record of Accepted Rule Violations (Atlas Shell Exceptions)
- **claim:** Three confirmed rule violations in `02_Platform/Atlas_Shell` (Rule 02, Rule 05, Rule 07) are documented as "accepted exceptions" only in user-level memory (`~/.claude/projects/.../memory/project_atlas_shell_rule_exceptions.md`). There is no formal exception record in the Atlas repository.
- **evidence:**
  - `project_atlas_shell_rule_exceptions.md`: "Three rule violations were identified in the `02_Platform/Atlas_Shell` design and accepted as-is pending a future system audit"
  - Memory is 8 days old; the exceptions were deferred "to next system audit" — this audit is that event
  - No corresponding exception record exists in `02_Platform/Atlas_Shell/`, `.claude/rules/`, or Blueprint
- **why_it_matters:** Accepted exceptions that exist only in external memory are invisible to the repository. Any agent operating on the Atlas Shell will encounter these rule violations without context, and will either flag them as blockers or silently normalize them — both are wrong outcomes. The "pending future system audit" condition has now been met.
- **affected_artifacts:** `02_Platform/Atlas_Shell/` (design artifacts), `~/.claude/.../memory/project_atlas_shell_rule_exceptions.md`
- **recommended_action:** Create a formal exception record at `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` documenting the three exceptions, their accepted rationale, and their resolution criteria. This makes them discoverable by agents operating in that component. Decide whether to resolve or formally accept-indefinitely each exception.
- **promotion_target:** `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md`
- **confidence:** high

---

### F-09
- **finding_id:** F-09
- **category:** missing_contract
- **severity:** medium
- **title:** Blueprint References UI Governance Directories That Are All Empty
- **claim:** The Manifest declares that Blueprint contains UI contracts. `CLAUDE.md` references `00_Blueprint/UI/` for UI governance. Three Blueprint UI directories exist (`01_UI_Contract`, `02_UI_DesignLanguage`, `03_UI_Implementation`) but all are empty. No UI design language or implementation standards exist at the Blueprint level.
- **evidence:**
  - Manifest §Layer Definitions 00.Blueprint: "UI — design language, component contracts, and implementation standards"
  - `CLAUDE.md` §Repository references: `UI governance: 00_Blueprint/UI/`
  - Glob of `00_Blueprint/UI/**` returns only directory entries, no files
- **why_it_matters:** The Manifest promises three categories of UI contract artifacts. Two (`02_UI_DesignLanguage`, `03_UI_Implementation`) do not exist at all. One (`01_UI_Contract`) exists as a directory but has no content. The actual UI contract lives in a `.claude/rules` file. The gap between promised and actual Blueprint content makes the Manifest inaccurate.
- **affected_artifacts:** `00_Blueprint/Atlas_Manifest.md`, `00_Blueprint/UI/02_UI_DesignLanguage/`, `00_Blueprint/UI/03_UI_Implementation/`
- **recommended_action:** Either (a) populate these directories with their promised content, or (b) update the Manifest to accurately describe what UI governance currently exists and where. The minimum action is to move the UI Data Contract from `.claude/rules` to `00_Blueprint/UI/01_UI_Contract/` (which also resolves F-01).
- **promotion_target:** `00_Blueprint/UI/`
- **confidence:** high

---

### F-10
- **finding_id:** F-10
- **category:** unclear_scope
- **severity:** low
- **title:** Chronicle Sprint02 SQL View Extension Is Documented in Agent Memory, Not in the Blueprint SQL File
- **claim:** Sprint02 adds `application_group` and `sort_order` columns to `shared_views.calendar_event_view`. This is documented in sprint-orchestrator agent memory (`project_chronicle_sprint_conventions.md`) but the Blueprint SQL file at `00_Blueprint/SharedViews/chronicle.sql` has not been confirmed updated with these columns in this audit.
- **evidence:**
  - `project_chronicle_sprint_conventions.md`: "`shared_views.calendar_event_view` gains `application_group` and `sort_order` columns"
  - Current `chronicle.sql` (read in this audit): does not contain `application_group` or `sort_order` in the view definition
- **why_it_matters:** If the Blueprint SQL file is not updated when the contract changes, the Blueprint artifact becomes stale. Any agent or human consulting `chronicle.sql` would see the old contract. The shared view is an explicit Blueprint contract per the Manifest.
- **affected_artifacts:** `00_Blueprint/SharedViews/chronicle.sql`, `.claude/agent-memory/sprint-orchestrator/project_chronicle_sprint_conventions.md`
- **recommended_action:** Verify whether Sprint02 has been completed and the SQL view applied. If the changes are live, update `chronicle.sql` to reflect the current schema including the Sprint02 additions. The Blueprint SQL artifact must track the live contract, not a prior sprint's state.
- **promotion_target:** `00_Blueprint/SharedViews/chronicle.sql`
- **confidence:** medium (requires verification against actual DB or Sprint02 implementation artifacts)

---

### F-11
- **finding_id:** F-11
- **category:** obsolete_definition
- **severity:** low
- **title:** Archived Platform Designer (`old_pf-designer_v0.md`) Conflicts in Name with Active Agent
- **claim:** `.claude/Archive/old_pf-designer_v0.md` contains frontmatter `name: platform-designer` — the same name as the active `.claude/agents/designer-platform.md` which is named `designer-platform`. The archived file's `name` field matches a real but different agent name that currently exists in the repository.
- **evidence:**
  - `old_pf-designer_v0.md` frontmatter `name: platform-designer`
  - Active agent: `.claude/agents/designer-platform.md` frontmatter `name: designer-platform`
  - Sprint-orchestrator refers to both `platform-designer` and `platform-implementer` by name in its routing table — the archived name conflicts with the orchestrator's expected name
- **why_it_matters:** If Claude Code loads the Archive directory or if the `name: platform-designer` frontmatter causes the archived agent to be available under that name, it could be inadvertently invoked instead of or alongside the current platform designer. The archive naming creates ambiguity.
- **affected_artifacts:** `.claude/Archive/old_pf-designer_v0.md`, `.claude/agents/designer-platform.md`
- **recommended_action:** Rename the archived file's frontmatter `name` field to `old_platform_designer_v0` or similar to prevent collision, or move it out of any directory structure that Claude Code scans for agents.
- **promotion_target:** Not applicable
- **confidence:** medium

---

## 6. Gaps and Promotion Candidates

### G-01
- **gap_id:** G-01
- **description:** No formal sprint process contract artifact exists outside of agent instructions
- **evidence_of_need:** Sprint states, transitions, folder structure, artifact naming, reviewer verdicts, and human gate rules all defined in `sprint-orchestrator.md`. Multiple active sprints follow this contract. FoodTracker exception and Chronicle input folder deviation required workarounds. Sprint04 artifact naming deviation breaks orchestrator detection.
- **likely_target:** `.claude/rules/08_sprint_process.md` or `00_Blueprint/SprintProcess.md`
- **recommendation:** Extract sprint state machine, canonical folder structure, artifact naming convention, reviewer verdict vocabulary, and human gate rule to a dedicated rules document. Update all agent instructions to reference it. Include a per-application exception mechanism so FoodTracker's skip-specs convention can be formally declared.

---

### G-02
- **gap_id:** G-02
- **description:** No architectural exception record mechanism exists in Atlas
- **evidence_of_need:** Atlas Shell violations (Rule 02, 05, 07) accepted as exceptions are recorded in user memory outside the repository. FoodTracker sprint process exception is recorded in agent memory. No Atlas component has a formal exception record artifact. The audit rule (R-08) says violations must be surfaced — but there is no defined place to record accepted violations as formal exceptions with rationale and resolution criteria.
- **likely_target:** A per-component `ARCHITECTURE_EXCEPTIONS.md` pattern, or a global `.claude/rules/exceptions/` directory for formally accepted deviations
- **recommendation:** Define an exception record pattern. At minimum: create `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` to resolve the deferred Atlas Shell violations. Document the pattern in `.claude/rules` or Blueprint so future accepted exceptions have a known home.

---

### G-03
- **gap_id:** G-03
- **description:** No rule governs when a platform component may use lazy Application imports (the Shell integration pattern)
- **evidence_of_need:** Atlas Shell uses `React.lazy(() => import('@workout/ShellEntry'))` — Application imported by Platform. This pattern is the actual mechanism by which applications integrate into the Shell. It is acknowledged as a Rule 05 violation and accepted. However, the acceptance creates a pattern that other platform components might follow without understanding the exception context. No rule defines when cross-direction lazy loading is permitted.
- **likely_target:** The Atlas Shell architecture exception record (G-02 target) or `.claude/rules/02_platform_boundary.md` (addendum on shell integration pattern)
- **recommendation:** Document the shell integration exception explicitly. Either add a clause to `02_platform_boundary.md` noting that "shell-type platform components that exist to compose application UIs may use lazy Application imports as a controlled pattern" with explicit constraints, or document it as an exception in the component's exception record.

---

### G-04
- **gap_id:** G-04
- **description:** No rule defines the promotion threshold for `.claude/rules` vs Blueprint placement of cross-cutting rules
- **evidence_of_need:** The UI Data Contract (a Blueprint-quality artifact) lives in `.claude/rules`. Security rules live in `CLAUDE.md`. Process rules live in agent instructions. There is no stated principle for what distinguishes a `.claude/rules` item from a Blueprint item. The Manifest says Blueprint contains contracts and governance — but `.claude/rules` is also governance. The boundary between them is implicit.
- **likely_target:** `00_Blueprint/Atlas_Manifest.md` (addendum to §00.Blueprint section defining `.claude/rules` role relative to Blueprint)
- **recommendation:** Add a clause to the Manifest defining the distinction: Blueprint contains durable cross-system contracts and architectural rules that change rarely and require explicit versioning. `.claude/rules` contains operational elaborations and process-level constraints for AI agents that are allowed to evolve more frequently. When a `.claude/rules` item rises to contract-level durability, it should be promoted to Blueprint.

---

### G-05
- **gap_id:** G-05
- **description:** The `app-definition-generator` skill and the `implementation-reviewer` agent define overlapping output schemas with no declared relationship
- **evidence_of_need:** `.claude/skills/app-definition-generator.md` defines a `definition.md` output schema (sections 1–8 + Validation Warnings). `.claude/agents/implementation-reviewer.md` defines an `implementation_status.md` output schema (sections 1–9 + Validation Warnings). The two schemas are structurally nearly identical — same sections in same order, same Validation Warnings list — but exist as separate definitions with no cross-reference. The skill predates the agent and appears to be its conceptual predecessor.
- **likely_target:** Declare one as the canonical schema and make the other reference it, or explicitly state the difference between a "definition" (state before sprint) and "implementation_status" (state after sprint).
- **recommendation:** Add a note to each artifact explicitly stating its relationship to the other and the intended lifecycle position. If the schemas are intentionally identical, a shared schema document would reduce duplication. If they are intentionally different, the differences should be stated.

---

## 7. Consolidation Plan

### 1. Immediate Constitutional Fixes

**Priority 1 — Resolve broken Blueprint UI reference (F-01, F-09)**
Move `.claude/rules/07_UI_Data_Contract.md` to `00_Blueprint/UI/01_UI_Contract/UI_Data_Contract.md`. Create a redirect stub at the old location. This is the most critical placement fix — it makes the contract discoverable from its declared location and aligns the Blueprint layer with what the Manifest promises.

**Priority 2 — Align reviewer verdict vocabulary (F-03)**
Add `APPROVED_WITH_CHANGES` to the sprint-orchestrator's valid verdict list with a defined transition (route to design-corrector, equivalent to `CHANGES_REQUIRED`). This fixes an active pipeline conflict. Document the canonical verdict vocabulary as a shared artifact rather than embedded in two separate agent instructions.

**Priority 3 — Rename Sprint04 design artifacts (F-05)**
Rename `component_architecture.json` → `architecture.json` and `component_scaffold.json` → `scaffolding.json` in `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/`. Update any references within those files if they self-reference. This restores orchestrator-detectability of Sprint04's design artifacts.

**Priority 4 — Create Atlas Shell exception record (F-08, G-02)**
Create `02_Platform/Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md` formally documenting the three accepted violations (Rule 02, 05, 07), their rationale, and resolution criteria. Remove the item from user-level memory or update it to point to the repository record.

**Priority 5 — Verify and update chronicle.sql (F-10)**
Check whether Sprint02 was completed and the SQL view extended. If so, update `00_Blueprint/SharedViews/chronicle.sql` to include `application_group` and `sort_order` columns to keep the Blueprint contract artifact current.

---

### 2. Rules to Promote

| Current location | Target | Rule ID |
|---|---|---|
| `CLAUDE.md` §Security | `.claude/rules/09_security.md` | R-17 |
| `sprint-orchestrator.md` (states, transitions, folder structure, naming, verdicts, human gate) | `.claude/rules/08_sprint_process.md` | R-14, R-15, R-16, R-18, R-19, R-20, R-21 |
| Agent instructions (sprint-orchestrator, designer) §4-layer model | Add canonical reference pointer to each copy | R-01 |
| User memory (FoodTracker skip-specs exception) | `03_Application/FoodTracker/sprint_conventions.md` + sprint-orchestrator exception mechanism | R-18 exception |

---

### 3. Duplicates to Remove or Reference-Consolidate

1. **Four-layer model** (R-01): Ten copies across all agents and `CLAUDE.md`. Cannot remove from agents (required for context), but add "Canonical: `00_Blueprint/Atlas_Manifest.md` §0" to each copy. Accept residual duplication as necessary for agent context.

2. **`old_pf-designer_v0.md`** (F-11): Rename frontmatter `name` field to avoid collision with active agent name. Consider moving to a location outside active `.claude/` scan paths.

3. **`app-definition-generator.md` vs `implementation-reviewer.md`** (G-05): Cross-reference the two documents. State that the skill produces pre-sprint state snapshots and the agent produces post-sprint implementation records. If schemas should align, state so explicitly.

---

### 4. Scopes to Clarify

1. **`.claude/rules` vs `00_Blueprint` placement boundary** (G-04): Add a clarifying clause to the Manifest defining when a rule rises to Blueprint level vs stays in `.claude/rules`. Without this, placement decisions for new rules are arbitrary.

2. **Accepted architectural exceptions** (G-02): Define a formal exception record pattern so Atlas Shell deviations and future exceptions have a known, discoverable home.

3. **Shell integration pattern** (G-03): Explicitly document whether the lazy-import cross-direction pattern in the Shell is a controlled exception or an emerging pattern. If controlled, state the constraints. Do not leave it as a rule violation with no formal disposition.

4. **API contract promotion threshold** (R-24): The rule exists in the Manifest but no agent enforces it. Add a check to `design-reviewer.md` that surfaces a finding when a new application endpoint shape resembles an existing application's shape, prompting the multi-app consumption threshold question.

---

### 5. Obsolete Definitions to Retire

1. **`.claude/Archive/old_pf-designer_v0.md`**: Rename frontmatter name field to eliminate collision risk (F-11). This is the only artifact in `.claude/Archive/` — the archive as a concept is not formally defined.

2. **Empty context files**: `.claude/context/atlas-overview.md` and `.claude/context/architecture-summary.md` exist but contain no content (both are 1-line empty files). Either populate or remove. Empty files that appear to be governance artifacts are confusing.

3. **Empty skill stubs**: `.claude/skills/code-navigation.md`, `.claude/skills/repo-search.md`, `.claude/skills/bug-investigation.md`, `.claude/skills/ui-generation.md` are all empty or near-empty stubs. If not in use, remove. If planned, mark explicitly as stubs-in-progress.

4. **`01_System/03.ProjectLog.md` as governance**: This file currently functions as a dynamic infrastructure state document. It contains live infrastructure values (Pi IP, Cloudflare tunnel, OAuth config) that are not architectural artifacts. Consider whether this belongs in `01_System` as a durable document or is a temporary operations note that should live elsewhere.

---

*Report generated by atlas-constitution-auditor on 2026-03-24. Based on inspection of 26 governance-relevant artifacts across `00_Blueprint`, `CLAUDE.md`, `.claude/rules`, `.claude/agents`, `.claude/agent-memory`, and `03_Application` sprint artifacts.*
