# Design Corrections — StorageTracker — Sprint01_Core

**Date:** 2026-04-11
**Corrector:** sprint_design_corrector
**Responding to:** 11_design_review.md

## Changes Applied

| # | Issue | File | Change |
|---|-------|------|--------|
| 1 | schema_artifact canonical path | `10_architecture.json` → `persistence.schema_artifact` | Changed from `Sprint01_Core/10_schema.sql` to `schema.sql` (component-root runtime path) |
| 2 | search q param description | `10_architecture.json` → `interfaces.exposed_surfaces` → `GET /api/items/views/search` → `params.q` | Changed from `"required"` to `"optional, default empty string; blank returns empty Dataset"` |

## No Behavioral Changes

Both corrections are documentation-only. No schema, contract, or behavioral logic was altered.
