# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
TaskTracker is a lightweight single-user task tracking application.

## Scope
Build the smallest useful daily task tracker first.

## Must-follow references
- Root `CLAUDE.md`
- `00_AppDefinition.md`
- `00_Blueprint/UI/`
- `02_Platform/03_ErrorHandling/`

## Rules
- Do not invent UI patterns outside the Blueprint UI definitions.
- Do not invent app-specific error handling outside platform conventions.
- Keep the MVP small.
- Prefer one simple vertical slice over broad partial scaffolding.