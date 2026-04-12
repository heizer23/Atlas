Goal

Stabilize and complete NumericSeries for real-world usage by:

fixing UI and formatting issues in measurement entry and display
introducing a measurement catalog as the semantic foundation
enabling batch measurement ingestion
defining a Chronos-compatible integration contract based on explicit measurement definitions
improving sparkline visualization to reflect real temporal data
Background

The current implementation has several issues:

input fields render with incorrect (black) styling
recorded_at is displayed in raw/unreadable format
date/time picker works on mobile but not reliably on web
sparkline does not reflect actual time spacing
sparkline does not use full vertical range
list row lacks min/max context
Chronos integration exists but is not robust enough for real usage

Additionally, there is currently no explicit definition of measurement types, which forces implicit interpretation and prevents reliable external ingestion.

Scope
Included
UI fixes (form styling, timestamp display, date input)
sparkline redesign
measurement catalog (new schema + contract)
batch measurement endpoint
Chronos integration (thin adapter over API)
series alignment with measurement definitions
Excluded
OCR / image parsing
advanced analytics
cross-series aggregation
platform-level changes
Core Design Decisions
1. Series = Measurement
each series directly represents one measurement type
no additional abstraction layer
simplifies API and Chronos integration
2. Measurement Catalog (NEW)

NumericSeries introduces a measurement definition structure.

Schema
{
  "key": "body_fat_pct",
  "label": "Body Fat",
  "unit": "%",
  "value_type": "decimal",
  "description": "Body fat percentage.",
  "aliases": []
}
Rules
key → canonical identifier (used in API + DB)
label → UI + LLM anchor
description → required, one line
unit → mandatory
value_type → explicit (no inference)
aliases → optional, extended over time
3. Chronos Integration Model

Chronos acts as a thin contract adapter.

Allowed:

mapping input → measurement key
unit normalization (based on catalog)
calling API

Not allowed:

inventing new meanings
guessing ambiguous mappings
duplicating validation logic

If mapping is unclear → fail

Functional Requirements
A. Measurement Catalog

NumericSeries must expose measurement definitions via:

Option A (preferred):

GET /api/measurement-definitions → Dataset

Additionally:

source-of-truth artifact in 00_architecture/measurement_definitions.json
B. Batch Measurement Endpoint

New endpoint:

POST /api/measurements/batch
Request
{
  "recorded_at": "2026-04-12T07:30:00Z",
  "measurements": [
    { "key": "weight", "value": 93.0 },
    { "key": "body_fat_pct", "value": 18.4 }
  ]
}
Behavior
atomic: all succeed or all fail
unknown key → reject request
invalid unit/value → reject request
missing recorded_at → handled per design (must be explicit)
Response
success → 201
error → ApiError
C. UI Fixes
1. Input Styling
remove black background
use Atlas UI tokens
reference existing working form components
2. Timestamp Display
replace raw DB format
define:
display format
timezone authority (must be explicit)
3. Date/Time Input

Must work on:

mobile
web

Designer must choose ONE:

native datetime-local (fixed properly)
split date + time fields
lightweight custom picker

No implicit browser-dependent behavior allowed.

D. Sparkline Redesign
Horizontal behavior
position points proportional to time distance
Vertical behavior
normalize between min and max
always use full height
Left side
top: max value
bottom: min value
Right side
current value (latest measurement)
Edge cases (must be defined)
single data point
identical values
empty dataset
identical timestamps
E. Series List Row Layout

Row must include:

label
sparkline (center)
min/max (left)
current value (right)

Alignment and spacing must be explicitly defined.

F. Chronos Skill

Defined and implemented in this sprint as thin adapter.

Input (example)
{
  "measurements": [
    { "label": "Weight", "value": 93 },
    { "label": "Body Fat", "value": 18.4 }
  ]
}
Behavior
map label/aliases → key
construct batch request
call /api/measurements/batch
Constraints
must not contain business logic
must not silently remap unknown values
must fail on ambiguity
Query & Time Rules

Designer must explicitly define:

ordering of measurements
time authority (server vs client)
default handling for missing timestamps
dataset size for sparkline
empty result behavior
Schema Changes

This sprint introduces:

measurement definition structure
potential new table or static artifact
alignment of series with measurement keys

Migration strategy must be defined:

initial seeding of measurement catalog
handling of existing series
Test Requirements (10_test_spec.md required)

Minimum scenarios:

single measurement creation
batch creation (multiple measurements)
batch failure on unknown key
timestamp handling correctness
sparkline data generation with uneven intervals
identical value handling
UI date input works on web
Chronos mapping success
Chronos failure on unknown/ambiguous label
Acceptance Criteria

Sprint is complete when:

UI fields render correctly (no black styling)
timestamps are readable and correctly formatted
date input works on web and mobile
measurement catalog exists and is accessible
batch endpoint works and is atomic
Chronos can submit multiple measurements in one request
sparkline reflects real time spacing
sparkline uses full vertical range
min/max shown on left, current value on right
no hidden logic exists in Chronos
Implementation Guidance
prefer simple, stable solutions over perfect ones
do not overengineer the catalog
avoid introducing hidden semantics
keep Chronos thin and deterministic

If you want next step, I’d suggest:

1. I generate the initial measurement catalog (weight, body fat, etc.)
2. Then we immediately derive 10_architecture.json so the designer has zero ambiguity

That’s where most drift usually happens.