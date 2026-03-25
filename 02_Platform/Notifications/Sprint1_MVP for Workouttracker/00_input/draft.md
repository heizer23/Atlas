Purpose

Define the first production-oriented notification platform slice for the Android app: a generic one-time notification pipeline that supports the workout rest timer use case through the target architecture:

Atlas server → FCM → Android shell → native Android notification → deep link into Atlas

This slice must also define a clean delivery split between two implementation agents:

Atlas Claude
Android Claude

The goal is one end-to-end slice with clear ownership boundaries, not two independent partial features.

Scope
Included
A platform-level notification record stored in Postgres
Creation of a single future notification
Initial trigger from workout tracker
Delivery through FCM
Rendering as a native Android notification
Tap behavior that deep links into Atlas
Lifecycle operations:
create
cancel
replace
Short-delay scheduling such as ~2 minutes ahead
Generic notification rendering style for all sources in this slice
User-visible display of:
title
body
label
Explicit work split between:
Atlas Claude deliverables
Android Claude deliverables
Excluded
Recurring notifications
Weekly/monthly schedules
Long-horizon scheduling guarantees
Feature-specific notification schemas
Notification inbox/history
Notification preferences/settings
Rich actions, grouping, channels strategy beyond what is minimally required
Detailed retry/recovery design for delivery failures
Native destination screens outside Atlas
User Flow
User starts a rest period in the workout tracker inside Atlas.
Workout tracker requests creation of a generic one-time notification.
Atlas stores the notification in Postgres.
At the scheduled time, Atlas sends the notification through FCM.
Android shell receives the message.
Android shell shows a native Android notification using the generic platform style.
The notification visibly includes the label.
User taps the notification.
Android shell opens the provided Atlas deep link.
Replace flow
A source decides an existing notification must change.
The old notification is deleted.
A new notification is created.
In the common case, all fields remain the same except id and fireAt.
Principles
Platform-agnostic: the contract must not encode workout semantics
Single valuable slice: one-time notifications only
Target architecture first: do not build a temporary local-only path
Clear ownership: Atlas and Android responsibilities must be separable
Minimal lifecycle: create, cancel, replace only
Generic rendering: same Android presentation pattern for all sources in this slice
Stable contract: fields should remain useful when more features adopt the platform
Tight timing, modest first tolerance: acceptable initial delivery variance is up to 2 seconds
Data Contract
Notification entity
Required
id
Unique identifier for this notification record
source
Originating feature or subsystem, for example workout_tracker
fireAt
Exact scheduled datetime
title
Primary notification text
body
Secondary notification text
label
User-visible label and metadata tag
deepLink
Atlas destination to open on tap
Not included
recurrence type
recurrence rule
app name
feature-specific payload fields
semantic fields such as restDuration, exerciseId, or similar
Replacement rule

Replacement is not an in-place update requirement in this slice.

Defined behavior:

old notification is deleted
new notification is created
new notification receives a new id
System Behavior
Must do
Accept a request to create a one-time notification
Persist the notification in Postgres
Dispatch it through FCM at the scheduled time
Render it as a native Android notification
Display the label to the user
Open the provided Atlas deep link when tapped
Cancel an existing notification by id
Replace a notification by deleting the old one and creating a new one
Use one generic Android notification style for all sources
Must not do yet
Support recurrence
Interpret business meaning from the source
Introduce source-specific rendering rules
Solve months-ahead reliability in this slice
Add a notification management UI
Architecture Impact
Introduced platform boundary
Feature layer requests notifications through a generic contract
Notification platform owns persistence and lifecycle
Atlas server owns scheduling state and dispatch responsibility
FCM acts as delivery transport
Android shell owns native display and deep-link handoff into Atlas
Agent boundary

This slice should be implemented as two coordinated deliverables:

Atlas Claude delivers the server-side notification platform behavior
Android Claude delivers the Android shell receiving, rendering, and deep-link behavior

The boundary between them is the FCM payload contract plus the expected deep-link handling behavior.

Deliverables by Agent
Atlas Claude deliverables

Atlas Claude is responsible for everything up to successful FCM dispatch.

Included
Define and persist the generic notification record in Postgres
Add platform-level notification lifecycle support:
create
cancel
replace
Connect the workout tracker to this platform contract
Ensure replacement behavior deletes the old notification and creates a new one
Dispatch due notifications through FCM
Produce the payload needed by Android shell to render and route the notification
Ensure the deep link points to the correct Atlas destination
Keep the notification contract feature-agnostic
Explicitly not owned by Atlas Claude
Native Android notification rendering
Android notification tap handling implementation
Android-specific presentation behavior after FCM receipt
Android Claude deliverables

Android Claude is responsible for everything after FCM is received on device.

Included
Receive the FCM message in the Android shell
Map the incoming payload to a generic native Android notification
Render title, body, and label in the notification UI
Use the agreed generic presentation style
Handle notification tap behavior
Open the provided Atlas deep link from the Android shell
Support cancel/removal behavior on device as required by the agreed payload and lifecycle
Explicitly not owned by Android Claude
Notification scheduling logic on the server
Persistence in Postgres
Workout tracker notification creation rules
FCM dispatch timing decisions on the server
Constraints
Must work with the current Android shell and Chrome Custom Tab setup
Must remain independent of source-feature semantics
Must deep-link into Atlas, not a feature-specific native screen
Must support short lead times such as 2 minutes
Initial acceptable timing variance is up to 2 seconds
Must show label in the user-facing notification
Must use a single generic Android notification style in this slice
Must be implementable by two separate agents with minimal ambiguity at the boundary
Acceptance Criteria
End-to-end
Workout tracker can create a one-time notification through the platform contract
The notification record is stored in Postgres with only generic platform fields
Atlas dispatches the notification through FCM at the scheduled time
Android shell displays a native notification with title, body, and label
Tapping the notification opens the specified Atlas deep link
A notification can be canceled by id
A notification can be replaced by deleting the old record and creating a new one
Replacement produces a new id
No recurrence concepts are required anywhere in the first slice
No workout-specific fields are present in the platform contract
All notifications use the same generic Android rendering style
For the initial rest-timer use case, delivery within 2 seconds of target time is acceptable
Atlas Claude acceptance
Atlas exposes or uses a generic notification creation path for workout tracker
Atlas persists notification records with the agreed contract
Atlas supports cancel and replace semantics
Atlas dispatches the agreed payload through FCM
Atlas does not depend on workout-specific notification fields in the platform model
Android Claude acceptance
Android shell can receive the agreed FCM payload
Android shell renders a native notification with the required visible fields
Android shell opens the provided Atlas deep link when tapped
Android shell uses the agreed generic rendering behavior for this slice
Open Questions
None that block this slice
Coordination note

The only area that must be explicitly aligned before implementation starts is the payload contract between Atlas and Android. That contract should be treated as part of this slice, not as an implementation detail to be improvised independently.

Out of Scope
Recurring reminders
Weekly workout reminders
Habit tracker notification patterns
Cooking helper notifications
Long-term scheduling optimization
Delivery retry policy details
Notification analytics/reporting
Notification history UI
Per-feature customization of Android notification appearance
User controls for muting or configuring notification categories
Optional Next Slice

Introduce recurring notification scheduling as a separate concept from notification delivery, reusing the same persisted notification contract and Android display path, without changing the generic rendering model.