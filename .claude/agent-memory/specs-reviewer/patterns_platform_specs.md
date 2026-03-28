---
name: Atlas Platform Spec Patterns
description: Recurring gaps and correct practices observed in Platform-layer spec reviews
type: reference
---

## Recurring Missing Items in Platform Specs

### 1. Status / lifecycle fields omitted from data contracts
Platform specs frequently define the user-visible fields of an entity but omit internal lifecycle fields (e.g., `status`, `dispatched_at`, `created_at`). These are required when the platform has a background process that must distinguish entity states for idempotency or correctness. Always check: does the spec describe any background process? If so, does the entity contract carry enough state to make that process correct?

### 2. Credential and secret loading not specified
Specs that integrate with external services (FCM, SMTP, webhooks) often omit how credentials are loaded. Per R-OPS-BP-02 (security, least privilege), the credential mechanism must be declared. Flag if absent: environment variable, file path, and what must not happen (hardcoded values).

### 3. Scheduling mechanism left implicit
Specs that require time-based dispatch ("dispatch at fireAt") routinely omit the scheduler technology. This is always a blocking ambiguity for Platform-layer components because the choice (APScheduler vs. Celery vs. cron) has significant infrastructure implications. Must be resolved in design_specs.md, not left to the designer.

### 4. Missing fields required for own behavior
Draft specs define the public API contract but omit fields only needed internally (e.g., the fcm_token field in Notifications was missing — the public contract does not expose it but the platform needs it to dispatch). Always ask: can the platform execute its own behavior with only the fields listed?

### 5. Cross-agent boundary artifacts described in prose
When two implementation agents share a boundary (e.g., Atlas Claude / Android Claude via FCM payload), the boundary artifact must be a required design artifact (JSON file), not a prose note. Prose does not survive agent context switching without interpretation.

## Atlas UI Data Contract — When It Does NOT Apply
R-CON-BP-04 applies only to components that surface data in the Atlas web UI. Platform components that are server-side services, background workers, or mobile integrations do not produce Dataset/ColumnSchema responses and should not be evaluated against this contract. Do not flag the absence of Dataset usage as a gap in these components.

## Platform Boundary Check
For every Platform-layer spec, verify: are the proposed API endpoints in a standalone Platform service or embedded in an application router? Per R-CON-PL-01, Platform capability must not be hosted inside an application backend. If a spec's architecture would embed the platform endpoints in e.g. WorkoutTracker's FastAPI router, flag this as an Atlas violation.

## Timing Tolerance Acceptance Criteria
When a spec states a timing tolerance (e.g., "2 seconds"), check whether it is average-case or worst-case. A polling-based scheduler has a worst-case latency equal to the poll interval. If the acceptance criterion could be interpreted as worst-case, either the poll interval must be reduced or the criterion must be documented as expected-case. Flag this ambiguity explicitly.
