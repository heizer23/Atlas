# CLAUDE.md

## Purpose
This file is the operational working guide for Claude Code in the ATLAS repository.
It summarizes the governing rules from the System documentation.
The underlying SYS documents remain authoritative.

## Authoritative references
Read and follow these documents when relevant:
- `01_System/00.01_Architecture_Manifest_LLM.md`
- `01_System/01.Development_Standards.md`

If this file conflicts with those documents, surface the conflict explicitly.

## Core operating model
ATLAS uses four layers:
- `00_Blueprint` = governance and contracts
- `01_System` = access, control, rebuild, operation
- `02_Platform` = shared technical capabilities without domain logic
- `03_Application` = domain behavior and app-specific meaning

Do not place components outside this structure unless explicitly requested.

## Architectural rules
- Treat the layer model as mandatory.
- Blueprint defines durable contracts and governance.
- Platform provides reusable technical capabilities only.
- Applications provide meaning and domain behavior.
- Application table schemas are private to the application.
- Shared contracts must be explicit and belong in Blueprint.
- Prefer explicit contracts and clear boundaries over implicit behavior.
- No hidden durable state.

## LLM working rules
- Prefer direct, information-dense responses.
- Infer the simplest solution that is consistent with the existing structure.
- Do not invent new components or architecture without need.
- Ask for missing information immediately.
- If a task is too large, first break it into subtasks.
- Prefer small, reviewable changes.
- Make choices that simplify future refactoring and reconstruction.

## Security rules
- Default to least privilege and minimal exposure.
- Warn when a proposed action introduces unnecessary exposure.
- Do not suggest opening ports unless clearly required and secured.
- Recommend secure patterns pragmatically; avoid unnecessary complexity for a one-person system.

## Consistency enforcement
- If a request conflicts with the architecture or standards, flag it explicitly before continuing.
- Controlled deviations are allowed only when marked clearly as deviations.
- When a deviation is proposed, ask whether to:
  1. accept the deviation for pragmatic reasons
  2. update the governing documentation

## Implementation guidance
- Favor durable, minimal, reproducible solutions.
- Avoid enterprise-scale complexity unless required by the constraints.
- Prefer standard, idiomatic, LLM-legible patterns.
- When presenting alternatives, use numbered options.

## Repository-specific references
- UI definitions are governed by `00_Blueprint/UI/`
- Error handling must follow `02_Platform/03_ErrorHandling/`

## New Application Creation Protocol

When creating a new application, follow this sequence.

### 1. Classify correctly
Before creating anything, decide whether the requested behavior belongs in:
- `00_Blueprint`
- `01_System`
- `02_Platform`
- `03_Application`

If it does not clearly belong in `03_Application`, flag the issue before proceeding.

### 2. Check for existing capability
Before creating a new app, inspect whether the requested behavior:
- already exists in another application
- should be added to an existing application
- depends on a platform capability that already exists
- requires a new Blueprint contract

Do not create a new app if the request is better handled as an extension of an existing one.

### 3. Create the minimum required application structure
For a new application, create:

- `03_Application/<AppName>/CLAUDE.md`
- `03_Application/<AppName>/00_AppDefinition.md`

Only create backend, UI, API, or database files after the definition has been reviewed or explicitly requested.

### 4. Write the app definition first
`00_AppDefinition.md` must define:
- purpose
- primary user
- MVP goal
- user stories
- core data fields
- main states / enums if needed
- MVP screens or interfaces
- non-goals

This file defines what the application does.
Do not place global architecture rules here.

### 5. Use global rules, do not duplicate them
Global architecture, UI governance, security rules, and platform-wide error handling belong in root `CLAUDE.md` or the authoritative SYS documents.

App-local files may reference relevant locations, but should not restate global rules in full.

### 6. Identify required contracts
Before implementation, determine whether the app requires:
- existing UI contracts from `00_Blueprint/UI/`
- existing platform error handling from `02_Platform/03_ErrorHandling/`
- a new shared contract in Blueprint
- only private application tables and internal logic

Application tables are private unless explicitly elevated into a shared contract.

### 7. Plan before implementation
Before generating code, produce a short implementation plan containing:
1. proposed file structure
2. backend data model
3. API shape if relevant
4. UI structure if relevant
5. dependencies on Platform or Blueprint
6. open assumptions or risks

Do not jump directly from user story to broad implementation unless explicitly instructed.

### 8. Prefer one vertical slice
For MVP, implement the smallest useful end-to-end slice first.

Prefer:
- one simple screen
- one clear API path
- one minimal private schema
- one coherent workflow

Avoid broad scaffolding for future features.

### 9. Surface deviations explicitly
If the requested app requires violating the architecture, contracts, or standards:
- flag the contradiction first
- mark the proposal as a controlled deviation
- ask whether to:
  1. accept the deviation pragmatically
  2. update the governing documentation

Do not silently drift the architecture.

### 10. Output discipline
When asked to create a new app, the default output order is:
1. classification check
2. app definition draft
3. implementation plan
4. code scaffolding
5. implementation

Do not skip earlier steps unless explicitly requested.