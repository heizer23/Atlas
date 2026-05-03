# Test Spec — FoodTracker — Sprint08_UI_Update

## Scope
Backend test coverage for the copy_entry endpoint's new optional logged_at body parameter. UI changes (date picker, fixed Save button, template date injection) are not covered by automated backend tests and are marked manual.

## Scenarios

### Copy with explicit logged_at uses caller date
- **Given:** A food_logs entry exists with id 'fix-copy-src-01'
- **When:** POST /api/food/entries/fix-copy-src-01/copy with body `{"logged_at": "2026-01-15T08:30:00"}`
- **Then:** HTTP 201; response body logged_at equals "2026-01-15T08:30:00"; all nutrition fields match the source row

### Copy without body falls back to current date
- **Given:** A food_logs entry exists with id 'fix-copy-src-01'
- **When:** POST /api/food/entries/fix-copy-src-01/copy with no body (empty)
- **Then:** HTTP 201; response body logged_at is a valid ISO-8601 datetime string (current timestamp); all nutrition fields match the source row

### Copy with invalid logged_at falls back gracefully
- **Given:** A food_logs entry exists with id 'fix-copy-src-01'
- **When:** POST /api/food/entries/fix-copy-src-01/copy with body `{"logged_at": "not-a-date"}`
- **Then:** HTTP 201; response body logged_at is a valid ISO-8601 datetime string (falls back to current timestamp, does not error)

### Copy nonexistent entry returns 404
- **Given:** No entry with id 'fix-nonexistent-99' exists
- **When:** POST /api/food/entries/fix-nonexistent-99/copy with body `{"logged_at": "2026-01-15T08:30:00"}`
- **Then:** HTTP 404; error.code equals "NOT_FOUND"

### [UI — manual] Date picker in EntriesPage pre-fills today
- **Given:** User opens the Entries page
- **When:** The page loads
- **Then:** A date input is visible in the page header, defaulting to today's date

### [UI — manual] Copy uses selected date from EntriesPage picker
- **Given:** User has selected 2026-01-15 in the EntriesPage date picker
- **When:** User clicks Copy in the three-dots menu for any entry
- **Then:** The copied entry appears with logged_at = 2026-01-15T12:00:00 (or similar time)

### [UI — manual] EntryDetailPage shows date and time split controls
- **Given:** User opens an entry detail
- **When:** The detail page loads
- **Then:** A date input and a time input are displayed (not a raw text input for logged_at)

### [UI — manual] Fixed Save button visible without scrolling
- **Given:** User opens an entry detail with a long form
- **When:** User scrolls down to the bottom of the form
- **Then:** The Save button remains visible at the top-right corner of the viewport throughout scrolling

### [UI — manual] FoodIntake template shows selected date
- **Given:** User has selected 2026-01-15 in the FoodIntake date picker
- **When:** User opens the template
- **Then:** The template's timestamp field shows a date of 2026-01-15

### [UI — manual] FoodIntake Accept button is fixed top-right in preview state
- **Given:** User has validated a meal and is in the preview state
- **When:** The preview is displayed
- **Then:** The Accept button is visible at the top-right of the viewport; Back button is inline
