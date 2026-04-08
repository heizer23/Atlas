Purpose

Deliver the smallest end-to-end slice that lets a user:

define a measurement label,
add numeric values over time to that label,
see all labels in a list with a sparkline and latest value,
open a detail view to edit the series,
read and write series data through an API, including batch read for multiple series.

This slice proves the core product loop without introducing categories, units logic, advanced analytics, or complex measurement types.

Scope
Included
User-defined labels for measurement series
One numeric value per measurement entry
Timestamp per measurement entry
List view showing:
label name
sparkline
latest value
Sorting list by label name
Detail view for one label showing:
all recorded measurements in editable form
add new measurement
edit existing measurement value and timestamp
delete measurement entry
delete the label
API to fetch multiple value series in one request
API to add values for OpenClaw
Excluded
Multi-user support
Authentication and permissions
Units conversion
Composite measurements in one record
Alerts, targets, trends, insights, or anomaly detection
Tagging, folders, or grouping
Custom sorting beyond label name
Rich charting beyond sparkline and simple detail history
Import/export
Attachments, notes, or comments
User Flow
List View

The user opens the app and sees a list of labels sorted alphabetically.

Each row shows:

label name
sparkline based on recent values
latest recorded value

The user can select a row to open its detail view.

Detail View

The user sees the full measurement history for that label in editable form.

They can:

add a new value with timestamp
edit an existing value
delete an entry
delete the label

After edits, the list view reflects the updated latest value and sparkline.

API Usage

An external client such as OpenClaw can:

request multiple series at once
submit one or more new measurements for a label
Principles
Keep the model flat: label + measurements
One measurement entry contains one numeric value
Optimize for fast manual review and entry
Make list view useful without opening details
Avoid special-case handling for health domains in this slice
Data Contract
Decided

Label: Use the existing labelengine

Measurement Entry
id
labelId
value as numeric
recordedAt
Implications
Blood pressure should be represented as two labels in this slice, for example:
Blood Pressure Systolic
Blood Pressure Diastolic

This keeps the first slice consistent with the “pairs and labels” model.

Unknown
Whether labels need optional metadata such as unit, color, or description
Whether API clients identify labels by internal ID, name, or both
System Behavior
A label can exist with no measurements
A sparkline is empty when no values exist
Latest value is the most recent entry by timestamp
Editing a measurement can change both value and timestamp
Deleting a label removes its measurement history
Batch series read returns all requested labels with their measurements, including empty series where applicable
Add-value API accepts new measurements for an existing label
If a write references an unknown label, behavior must be explicitly chosen before implementation
Architecture Impact
Introduces two core entities: labels and measurements
Establishes the app’s primary read model:
label summary for list view
full measurement history for detail view
Establishes the first external contract for OpenClaw integration
Keeps future extension possible for:
units
grouping
composite metrics
derived metrics
Constraints
The slice should assume numeric values only
The slice should remain usable with many labels, but does not need advanced performance optimization yet
The sparkline should summarize existing values only; no forecasting or interpolation
The API should support batch retrieval because single-series-only access is insufficient for your stated use case
Acceptance Criteria
UI
User can create a label with a unique name
List view shows all labels sorted by name
Each label row shows name, sparkline, and latest value
User can open a detail view for a label
Detail view shows all measurements for that label
User can add, edit, and delete measurement entries
User can delete a label from detail view
After any change, list view and detail view remain consistent
API
Client can request multiple series in one call
Response returns each requested label with its measurements
Client can add new measurement values for a label
Newly added values are visible in both list and detail views after write success
Data Rules
Each measurement has exactly one numeric value and one timestamp
Latest value is derived from the newest timestamp
Deleted labels no longer appear in list results
Open Questions
Should label names be globally unique, or can duplicates exist?
Should deleting a label permanently delete its history, or should it be recoverable?
For OpenClaw writes, should unknown labels:
be rejected,
be auto-created,
or be configurable?
Do you want measurements editable inline in the detail list, or through a simple edit form per row?
Do you want the batch-read API to return full history, or only a limited recent window by default?