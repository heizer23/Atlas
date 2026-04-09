# Design Corrections — TaskTracker Sprint06_Label_Contract_Fix

**Date:** 2026-04-09
**Correcting:** design_review.md blocking issue #1

## Correction Applied

**Issue:** design_review.md identified a fourth ShellEntry.tsx call site at lines ~1102–1103 (TaskCreatePanel.handleLabelQueryChange) that was missing from the design.

**Changes made:**

1. `20_design/architecture.json` internal_flow step 4 — updated description to reference four call sites, adding (d) lines ~1102–1103 in TaskCreatePanel.handleLabelQueryChange with the same res.rows mapping as the other search call sites.

2. `20_design/architecture.json` deferrals.application_implementer — updated to specify all four call sites.

3. `20_design/architecture.json` deferrals.reviewer — updated confirmation checklist to list all four call sites including ~1102.

4. `20_design/scaffolding.json` ShellEntry.tsx modifications — added fourth modification entry for TaskCreatePanel search call site (~line 1102–1103).

No architectural decisions changed. The correction adds coverage for an existing call site that was missed in the initial design pass.
