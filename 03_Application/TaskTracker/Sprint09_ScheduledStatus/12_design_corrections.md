# Design Corrections — tasktracker — Sprint09_ScheduledStatus

**Date:** 2026-05-04
**Corrector:** sprint_design_corrector
**In response to:** 11_design_review.md

## Changes Applied

### 1. Added UI scenarios to test spec (blocking issue #1 from review)

Added three `[UI — manual]` scenarios to `10_test_spec.md`:
- `[UI — manual] Scheduled tab renders tasks with formatted scheduled time` — verifies the Scheduled tab appears in the tab bar with correct order, and rows show formatted scheduled_at and priority chip.
- `[UI — manual] Create form shows scheduled_at input when scheduled status selected` — verifies the datetime-local input appears and is required when status=scheduled is selected in the create form.
- `[UI — manual] Task detail clears scheduled_at when status changed away from scheduled` — verifies the round-trip of clearing scheduled_at via the edit panel.

These scenarios are marked `[UI — manual]` because automated Playwright UI test infrastructure is not confirmed for TaskTracker at this time.

## No changes to architecture.json or scaffolding.json

The blocking issue was entirely in the test spec. Architecture and scaffold artifacts are unchanged.
