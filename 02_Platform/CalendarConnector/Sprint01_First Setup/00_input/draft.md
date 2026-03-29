You are implementing the first Atlas calendar integration slice.

Read and follow the Atlas architectural rules and manifest first, especially the rules around:
- architecture as AI interface
- contracts and boundaries
- no hidden state
- dependency direction
- platform boundary
- surface violations explicitly

Design and implementation must align with these principles:
- Platform provides reusable technical capability
- Applications and agents provide meaning
- Durable state must be explicit and inspectable
- Do not create hidden coupling between login and calendar access
- Do not introduce domain logic into Platform

Context
- Atlas already has a working Google OAuth client used for Atlas login
- Reuse the existing GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from secrets
- Do not create a second Google OAuth client
- Do not break or materially change the existing login flow
- Calendar access must be implemented as a separate OAuth authorization flow, with separate persisted connection state
- A user being logged into Atlas with Google must NOT imply Atlas has calendar access
- Current initial development callback URI is:
  http://localhost:8000/auth/google/callback
- This is for local development only
- Production callback will later use the real Atlas HTTPS domain

Goal
Implement a first reusable Platform capability for Google Calendar integration that:
1. connects Atlas to a Google Calendar account through a separate consent flow
2. stores calendar connection and token state explicitly in the database
3. reads events from the connected Google Calendar for a requested time window
4. is usable later by Chronos and other Atlas applications
5. does not yet implement background sync, write-back, or complex UI

Placement
Implement this as a new Platform component, not as Chronos logic and not as application-specific logic.

Recommended placement:
- 02_Platform/CalendarConnector

If the repo naming conventions require adaptation, stay consistent with the existing Atlas structure, but preserve the Platform classification.

Scope for this slice
In scope:
- separate calendar connect start endpoint
- separate calendar connect callback endpoint
- Google token exchange
- explicit DB persistence for calendar connection state
- explicit DB persistence for token state
- read events endpoint for a requested time window
- clear separation from existing login behavior
- minimal inspectable status surface

Out of scope:
- writing events to Google Calendar
- Atlas-specific target calendar creation
- background sync workers
- recurring sync jobs
- webhook push notifications
- UI polish
- multi-provider abstraction beyond what is needed for clean internal structure
- Chronos-specific behavior
- task/calendar business logic

Architectural requirements
1. Separation of concerns
- Existing Google login remains its own flow
- Calendar connection is a separate flow and separate state object
- Shared helper code is allowed
- Shared permission state is not allowed

2. No hidden state
Persist explicit records for:
- connection status
- granted scopes
- token expiry
- refresh token presence
- timestamps for creation/update/last successful use/last error if reasonable

3. Platform boundary
This component may:
- handle provider OAuth for calendar capability
- store connection metadata
- fetch and normalize Google Calendar events
- expose reusable interfaces/endpoints

This component must not:
- decide what events “mean”
- create reminders or business workflows
- embed Chronos behavior
- assume application-specific use cases

4. Dependency direction
- Platform may depend on existing Blueprint contracts and allowed System capabilities
- Do not pull Application meaning into the Platform design

5. Inspectability
Provide a minimal way to inspect whether the calendar connection exists and whether it is healthy.

Implementation requirements

A. Endpoints
Implement at least these endpoints, or equivalent routes consistent with the Atlas codebase:

1. GET /calendar/google/connect/start
- starts Google consent flow for calendar access
- requests only minimal scope for the first slice:
  https://www.googleapis.com/auth/calendar.readonly
- must be clearly separate from login
- should include state handling appropriate for CSRF protection

2. GET /calendar/google/connect/callback
- receives Google auth code
- exchanges code for tokens
- persists connection/token state explicitly
- returns a simple success/failure response consistent with Atlas patterns

3. GET /calendar/events?from=...&to=...
- reads events from the connected Google Calendar for the provided time window
- returns a normalized response
- if no valid connection exists, return a contract-valid error response

4. Optional but recommended:
GET /calendar/status
- returns a minimal inspectable view of current connection health/state
- no secrets in response

B. Persistence
Create explicit database structures for the calendar connection.

Minimum recommended model:
1. calendar_connection
- id
- provider (for now "google")
- account_email or account_label if available
- status (e.g. connected, expired, revoked, error)
- granted_scopes
- created_at
- updated_at
- last_success_at nullable
- last_error nullable

2. calendar_token
- connection_id
- access_token
- refresh_token
- token_expiry
- token_type if available
- scope string if available
- created_at
- updated_at

If the existing Atlas conventions prefer one table instead of two, that is acceptable, but the state must remain explicit and inspectable.

Sensitive fields must not be exposed in API responses.

C. Event normalization
Normalize Google events into a simple internal shape that is reusable.

At minimum include:
- id
- external_event_id
- title / summary
- description
- start_at
- end_at
- all_day boolean
- source_calendar_id
- source_calendar_label if easily available
- location
- status

Do not overdesign a universal calendar abstraction yet. Keep it minimal but clean.

D. Error handling
Use existing Atlas error handling conventions.
If there is an established Platform error envelope or request_id pattern, follow it.
Do not invent ad hoc inconsistent error shapes.

E. Secrets/config
Reuse existing:
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET

Do not require a new Google OAuth client.
Add only the minimum additional config needed.

F. Login isolation
Do not modify the existing login flow such that login automatically requests calendar scope.
Do not make calendar connection an implicit side effect of login.
Do not assume a logged-in Google user has an active calendar connection.

Deliverables
Produce:
1. implementation in the appropriate Platform location
2. any DB migration(s)
3. any required config additions or notes
4. a concise architecture/design note in the component folder explaining:
   - purpose
   - scope
   - non-scope
   - owned state
   - public endpoints/interfaces
   - why login and calendar connection are separate
5. a short implementation status note summarizing:
   - what was added
   - what remains out of scope
   - any open questions or controlled deviations

Quality bar
- Minimal, working, explicit
- No speculative abstraction layers unless they reduce real friction immediately
- No background workers
- No UI-heavy work
- No Chronos-specific logic
- Prefer direct, readable code over premature generalization

If you detect a contradiction with Atlas architecture or the current repo structure, surface it explicitly before proceeding and then choose the smallest controlled deviation.

There is already an existing Google OAuth login flow in the codebase, but its exact location is not known. You must locate it by searching the repository.

Reuse existing OAuth helper logic where appropriate (e.g. auth URL construction, token exchange), but do not modify the login behavior itself beyond safe extraction of shared utilities.

If no reusable structure exists, create minimal shared helpers in a way that does not break the existing login flow.