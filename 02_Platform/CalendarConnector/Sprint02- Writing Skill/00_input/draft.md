Purpose

Enable the first end-to-end write path from Atlas into Google Calendar by allowing an OpenClaw skill to create a new event in the dedicated Chronos-Dates Google calendar.

This slice extends CalendarConnector from read-only integration to a narrowly scoped write capability that is useful immediately, while avoiding update/delete complexity in the same step.

Scope
Included
Upgrade the Google Calendar connection so it can authorize write access.
Support creating a calendar event through CalendarConnector.
Restrict writes to one fixed target calendar only: the dedicated Chronos calendar.
Allow invocation via a direct synchronous API call from the OpenClaw skill.
Persist a decision log record in Postgres for each write attempt/result.
Return a clear API result describing whether the event was created successfully.
Excluded
Updating existing Google Calendar events.
Deleting Google Calendar events.
Writing to primary or to arbitrary caller-supplied calendar IDs.
Calendar discovery, selection, or management UI.
Rich Google event features beyond the minimum create payload.
Background sync, retry workers, or async execution.
Per-user ownership or per-user calendar routing.
Broader event-source mapping or Chronos business logic.
User Flow
An operator connects CalendarConnector to Google with write-capable consent.
Atlas/OpenClaw decides that a new date should be placed on the calendar.
The OpenClaw skill calls CalendarConnector with the event details.
CalendarConnector validates the request and resolves the fixed Chronos target calendar.
CalendarConnector creates the event in Google Calendar.
CalendarConnector writes a decision log entry in Postgres capturing the request outcome.
CalendarConnector returns a success response including the created external event identifier and normalized summary fields.
Principles
Single valuable slice: create only, not full event lifecycle.
Fixed destination: all writes go only to the dedicated Chronos calendar.
System-scoped behavior: no per-user branching.
Safe expansion path: this slice should not pre-commit the system to update/delete semantics.
Clear auditability: every write attempt must be logged in the decision log.
No caller control over calendar target: the connector owns target-calendar enforcement.
Data Contract
New API Capability

POST /api/calendar/events

Purpose: Create a new event in the dedicated Chronos calendar.

Request Shape

Minimum required fields for this slice:

title
start_at
end_at

Optional fields for this slice:

description
location
all_day

Not included in this slice:

attendees
reminders
recurrence
conferencing
arbitrary Google event fields
caller-supplied calendar_id
Response Shape

Return a structured success payload for created events that includes:

status
google_event_id
title
start_at
end_at
all_day
source_calendar_id
source_calendar_label

Error responses should follow the existing platform error envelope.

Decision Log

A decision log record must be written for each create attempt, including at minimum:

operation type = calendar event create
request timestamp
target calendar identifier
outcome status
resulting Google event ID when successful
error summary when unsuccessful

Exact storage schema is not defined in this slice if an existing decision-log contract already exists elsewhere.

System Behavior
CalendarConnector must require a write-capable Google authorization before accepting event creation.
If the existing connection is read-only, the system must treat it as insufficient for this endpoint until re-consent has completed.
The create endpoint must always target the dedicated Chronos calendar and must not accept target override from the caller.
The connector must perform the same token-validity handling standard already used for reads, including refresh when possible.
On successful creation, the connector returns the created event details and records the success in the decision log.
On provider failure, authorization failure, or invalid input, the connector returns a platform error response and records the failed attempt in the decision log.
Read endpoints remain unchanged in behavior for this slice.
Architecture Impact
OAuth scope model changes: the current read-only connection model must be extended to support write-capable authorization.
Connector responsibility expands: CalendarConnector now owns both read and create operations for the same system-scoped Google connection.
Configuration responsibility increases: the dedicated Chronos calendar must become an explicit connector-level configuration/input rather than an implicit manual detail.
Audit surface added: decision-log persistence becomes part of the write path.

No broader architectural shift is required in this slice.

Constraints
Writes must go only to the dedicated Chronos calendar specified by the user.
Invocation must be direct and synchronous from the OpenClaw skill.
The system remains single-tenant and system-scoped.
The first slice must optimize for the easiest viable OAuth scope upgrade path rather than a more elaborate migration design.
The design must not assume update/delete support exists yet.
Existing read functionality must continue to work after the scope upgrade.
Acceptance Criteria
A connected Atlas instance can complete a Google consent flow that grants write-capable calendar access.
CalendarConnector exposes one create-event endpoint for use by the OpenClaw skill.
A valid create request results in a new event being created in the dedicated Chronos calendar.
The caller cannot redirect the write to any other calendar.
A successful response includes the created Google event ID and normalized event summary fields.
Every create attempt writes a decision log entry in Postgres.
Failure cases also produce decision log entries with outcome and error summary.
Read endpoints continue functioning after the connection is upgraded for write access.
The slice does not introduce update or delete behavior.
Open Questions
Dedicated calendar identifier source: should the connector store the dedicated Chronos calendar as:
a config value, or
a persisted database setting tied to the connection?
Decision log contract: is there already a canonical Postgres table/contract for the decision log, or does this slice need to define one?
All-day semantics: should all_day be supported in this first write slice, or should the first slice allow timed events only?

These are not blockers to choosing the slice, but they do need resolution before final implementation specs.

Out of Scope
Event update semantics
Event deletion semantics
Duplicate detection or idempotency strategy
External-to-internal event mapping model
Multi-calendar routing
Multi-user connection ownership
Calendar permissions UI
Import/export behavior
Conflict handling between manual calendar edits and Atlas-created events