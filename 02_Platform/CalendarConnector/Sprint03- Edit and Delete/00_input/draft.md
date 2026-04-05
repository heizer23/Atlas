Purpose

Enable a complete minimal event-management capability in CalendarConnector by supporting idempotent create, update, and delete of Atlas-linked Google Calendar events in the dedicated Chronos-Dates calendar, while adding a lightweight internal event index in Postgres to make lookup stable, fast, and explicit.

This keeps Google Calendar as the operational calendar surface, but removes dependence on searching Google as the primary lookup mechanism.

Scope
Included
Create, update, and delete calendar events.
Idempotent create behavior by atlas_event_id.
Idempotent delete behavior.
A lightweight Postgres event index mapping Atlas event identity to Google event identity.
Direct synchronous invocation from the OpenClaw skill.
Fixed write target: dedicated Chronos-Dates calendar only.
Decision log entry for every operation attempt and outcome.
Excluded
Atlas as canonical source of truth for meeting content.
Full internal event model in Postgres.
Two-way sync from Google Calendar into Atlas.
Bulk reconciliation or rebuild jobs.
Advanced Google Calendar features such as attendees, recurrence, reminders, conferencing.
Multi-calendar support.
Manual-edit conflict resolution.
User Flow
Create
OpenClaw sends a create request with atlas_event_id.
CalendarConnector checks the internal event index.
If a live mapping exists, the connector returns the existing event instead of creating a duplicate.
If no mapping exists, the connector creates the event in the dedicated Chronos-Dates calendar.
CalendarConnector writes the Atlas↔Google mapping into the internal event index.
CalendarConnector records the result in the decision log.
CalendarConnector returns the event reference.
Update
OpenClaw sends an update request with atlas_event_id.
CalendarConnector resolves the Google event via the internal event index.
CalendarConnector updates the supported fields in Google Calendar.
CalendarConnector records the result in the decision log.
CalendarConnector returns the updated event reference.
Delete
OpenClaw sends a delete request with atlas_event_id.
CalendarConnector resolves the Google event via the internal event index.
If the event exists, CalendarConnector deletes it in Google Calendar.
CalendarConnector marks the mapping as no longer active, or otherwise makes it unusable for future lookup.
CalendarConnector records the result in the decision log.
CalendarConnector returns success.
Principles
Google-first, not Google-only: Google Calendar remains the working calendar surface, but Atlas gains stable indexed linkage.
Idempotency is part of the slice: retries must be safe.
Atlas identity is the stable key: atlas_event_id is the primary cross-system identifier.
Minimal persistence: store only what is needed for reliable lookup and lifecycle management.
Single target surface: all writes go only to the dedicated Chronos-Dates calendar.
No premature domain model: the event index is not a full meeting store.
Data Contract
API Capabilities

POST /api/calendar/events
Create an event idempotently.

PATCH /api/calendar/events
Update an existing Atlas-linked event.

DELETE /api/calendar/events
Delete an existing Atlas-linked event idempotently.

Request Shape
Create

Required:

atlas_event_id
title
start_at
end_at

Optional:

description
location
all_day
Update

Required:

atlas_event_id

Optional updatable fields:

title
start_at
end_at
description
location
all_day

At least one updatable field must be present.

Delete

Required:

atlas_event_id
Response Shape

For create/update success:

status
atlas_event_id
google_event_id
title
start_at
end_at
all_day
source_calendar_id
source_calendar_label

For delete success:

status
atlas_event_id
google_event_id when known

Errors use the existing platform error envelope.

Internal Data Contract
Lightweight Event Index

Add a Postgres table for Atlas↔Google event linkage.

Minimum fields:

internal row id
atlas_event_id — unique stable Atlas identifier
google_event_id — Google event identifier
calendar_id — fixed Chronos-Dates calendar identifier
status — active / deleted / error-equivalent lifecycle marker
created_at
updated_at
last_success_at nullable
last_error nullable
Purpose
Resolve update/delete without searching Google first.
Enforce idempotent create.
Preserve stable cross-system linkage.
Provide a minimal upgrade path toward stronger internal ownership later.

This table is an index, not a full canonical event store.

System Behavior
Shared
All operations are restricted to the dedicated Chronos-Dates calendar.
Caller cannot override calendar target.
All created Google events must carry the stable atlas_event_id in Google event metadata.
Every operation attempt must produce a decision log entry.
Create
Check internal event index by atlas_event_id.
If an active mapping exists, return the existing event and do not create a duplicate.
If no active mapping exists, create the event in Google Calendar.
Persist the new mapping in the event index.
If Google creation succeeds but index persistence fails, the operation must be treated as failed and explicitly surfaced; the slice must not silently ignore index inconsistency.
Update
Resolve the event through the internal event index.
If no active mapping exists, return not-found.
Update only supported fields.
Preserve atlas_event_id metadata on the Google event.
If the mapped Google event is missing remotely, return an explicit error and record it in both decision log and index state.
Delete
Resolve the event through the internal event index.
If no active mapping exists, return idempotent success.
If the mapped Google event exists, delete it remotely.
Mark the index entry as no longer active rather than removing historical trace completely.
Architecture Impact
CalendarConnector gains a small internal persistence layer for event linkage.
Event lifecycle operations stop depending on provider-side search as the main lookup path.
The connector remains Google-first in behavior, but becomes more robust for retries and future evolution.
This slice creates a clean stepping stone toward a future Atlas-owned source of truth without requiring that decision now.
Constraints
The event index must remain lightweight and must not evolve into a full meeting model in this slice.
Only the dedicated Chronos-Dates calendar is writable.
The system remains single-tenant and system-scoped.
The slice must not require background workers.
The slice must not introduce update/delete by raw Google event ID as the primary API contract.
Acceptance Criteria
Create is idempotent by atlas_event_id and does not create duplicates.
Create stores a Google event mapping in the internal event index.
Update resolves events through the internal event index.
Delete resolves events through the internal event index.
Delete is idempotent when no active mapping exists.
All writes are restricted to the dedicated Chronos-Dates calendar.
Every created Google event stores the Atlas stable ID in Google metadata.
Every create, update, and delete attempt writes a decision log entry.
The internal event index records operation health sufficiently to diagnose broken mappings.
Existing read functionality remains unaffected.
Open Questions
Should the event index retain deleted mappings as deleted, or allow hard deletion after successful remote delete?
retain as deleted
hard delete row
When a mapped Google event is missing during update/delete, should the index entry become:
error
deleted
unchanged with only last_error
Should create return whether the result was:
newly created
existing mapping returned
Out of Scope
Full Atlas meeting storage
Google-to-Atlas import
Manual Google edit reconciliation
Bulk re-sync or repair
Advanced event semantics
Attendee workflows
Recurrence handling