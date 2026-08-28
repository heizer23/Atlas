# Test Spec — EssayCards — Sprint01_Core

## Scope

Backend API tests (pytest + httpx/Starlette TestClient against a test Postgres database) for the four HTTP endpoints, plus direct (non-HTTP) tests of the ingestion function and the scheduling formula. UI behavior is covered by manual scenarios below — no automated UI test infrastructure is set up for EssayCards in this sprint.

## Scenarios

### List essays returns Dataset
- **Given:** The database contains at least one essay (fixture 'The Origins of Long-Form Formats')
- **When:** GET /api/essaycards/essays is called with no params
- **Then:** Response is 200; body is a Dataset with meta.object_type='essay'; rows contains at least one entry; each row has id, title, slug; rows are ordered by created_at ascending

### List essays empty
- **Given:** The essaycards.essays table is empty
- **When:** GET /api/essaycards/essays is called
- **Then:** Response is 200; Dataset with rows=[] and meta.total=0

### Essay detail returns ordered sections
- **Given:** Fixture essay 'The Origins of Long-Form Formats' has two sections with known order_index values
- **When:** GET /api/essaycards/essays/{fixture_essay_id} is called
- **Then:** Response is 200; Dataset with a single row; row.sections is a list ordered by order_index ascending; each section entry has id, heading, anchor_slug, order_index, body_markdown; body_markdown does not contain the raw ```flashcards fence text

### Essay detail not found
- **Given:** No essay exists with id "00000000-0000-0000-0000-000000000000"
- **When:** GET /api/essaycards/essays/00000000-0000-0000-0000-000000000000
- **Then:** Response is 404; body is ApiError

### Due flashcards — no params returns system-wide queue
- **Given:** Fixtures include due cards belonging to two different essays
- **When:** GET /api/essaycards/flashcards/due is called with no params
- **Then:** Response is 200; Dataset rows include due cards from both essays; rows are ordered by next_due_at ascending; each row has id, flashcard_id, question, answer, essay_id, section_id, anchor_slug, next_due_at, and id equals flashcard_id

### Due flashcards — scoped to essay
- **Given:** Fixture essay A has a due card and fixture essay B has a due card
- **When:** GET /api/essaycards/flashcards/due?essay_id={essay_A_id}
- **Then:** Response is 200; Dataset rows include only cards where essay_id={essay_A_id}

### Due flashcards — scoped to essay and section
- **Given:** Fixture essay A has two sections, each with a due card
- **When:** GET /api/essaycards/flashcards/due?essay_id={essay_A_id}&section_id={section_1_id}
- **Then:** Response is 200; Dataset rows include only the due card belonging to section_1, not the card belonging to the essay's other section

### Due flashcards — section_id without essay_id is rejected
- **Given:** No precondition
- **When:** GET /api/essaycards/flashcards/due?section_id={any_section_id}
- **Then:** Response is 400; body is ApiError with error.code="VALIDATION_ERROR"

### Due flashcards — excludes not-yet-due cards
- **Given:** Fixture card 'fc-not-due' has next_due_at set one hour in the future
- **When:** GET /api/essaycards/flashcards/due (no scope, or scoped to that card's essay)
- **Then:** Response is 200; the rows do not include 'fc-not-due'

### Due flashcards — empty result when nothing due
- **Given:** All fixture cards in a given essay have next_due_at in the future
- **When:** GET /api/essaycards/flashcards/due?essay_id={that_essay_id}
- **Then:** Response is 200; Dataset with rows=[] and meta.total=0

### Review — grade again schedules five seconds out
- **Given:** Fixture card 'fc-origins-1' has last_reviewed_at=null
- **When:** POST /api/essaycards/flashcards/{fc-origins-1_id}/review with body {"grade": "again"}
- **Then:** Response is 200; body.last_reviewed_at is close to the request time; body.next_due_at is approximately body.last_reviewed_at + 5 seconds (flat interval, no floor/doubling logic applied)

### Review — grade good on a never-reviewed card uses the floor
- **Given:** Fixture card 'fc-origins-2' has last_reviewed_at=null (never reviewed)
- **When:** POST /api/essaycards/flashcards/{fc-origins-2_id}/review with body {"grade": "good"}
- **Then:** Response is 200; body.next_due_at is approximately body.last_reviewed_at + 20 minutes (the floor; there is no prior interval to double)

### Review — grade good on a repeat review doubles elapsed time
- **Given:** Fixture card 'fc-origins-3' has last_reviewed_at set to 60 minutes before now
- **When:** POST /api/essaycards/flashcards/{fc-origins-3_id}/review with body {"grade": "good"}
- **Then:** Response is 200; since 2 * 60 minutes (120 minutes) exceeds the 20-minute floor, body.next_due_at is approximately the new last_reviewed_at + 120 minutes

### Review — invalid grade rejected
- **Given:** Fixture card 'fc-origins-1' exists
- **When:** POST /api/essaycards/flashcards/{fc-origins-1_id}/review with body {"grade": "maybe"}
- **Then:** Response is 400; body is ApiError with error.code="VALIDATION_ERROR"

### Review — unknown flashcard not found
- **Given:** No flashcard exists with id "00000000-0000-0000-0000-000000000000"
- **When:** POST /api/essaycards/flashcards/00000000-0000-0000-0000-000000000000/review with body {"grade": "good"}
- **Then:** Response is 404; body is ApiError with error.code="NOT_FOUND"

### Ingestion — creates essay, sections, and flashcards due immediately
- **Given:** A well-formed markdown fixture file with front matter, two `## Heading {#anchor}` sections, and one ```flashcards block per section
- **When:** backend.ingest.ingest() is called directly against that file
- **Then:** An essay row exists matching the front matter slug/title; both sections exist with correct order_index, heading, anchor_slug, body_markdown (excluding the flashcards fence); all flashcards exist with the exact author-assigned card_key; each new flashcard's review state has last_reviewed_at=null and next_due_at equal to the flashcard's created_at

### Ingestion — re-ingesting an unchanged file preserves review state
- **Given:** The essay from the previous scenario has been ingested, and one of its flashcards has since been graded via POST .../review (last_reviewed_at and next_due_at are now non-default values)
- **When:** backend.ingest.ingest() is called again against the same unchanged source file
- **Then:** The flashcard's last_reviewed_at and next_due_at are unchanged from before re-ingestion

### Ingestion — re-ingesting edited text updates content only
- **Given:** The essay has been ingested once; the source file is then edited to change one flashcard's question text but keep its id (card_key) the same
- **When:** backend.ingest.ingest() is called again against the edited file
- **Then:** The flashcard's question text is updated to the new value; its review state (last_reviewed_at, next_due_at) is unchanged

### Ingestion — missing anchor slug aborts with no rows written
- **Given:** A markdown fixture file where one `##` heading has no `{#anchor}` suffix
- **When:** backend.ingest.ingest() is called against that file
- **Then:** An IngestionError is raised; no essay, section, or flashcard row is written to the database as a result of this call

### Ingestion — malformed flashcards YAML aborts with no rows written
- **Given:** A markdown fixture file where a ```flashcards block contains a card entry missing the required `a` (answer) key
- **When:** backend.ingest.ingest() is called against that file
- **Then:** An IngestionError is raised naming the section's anchor_slug and the offending card; no essay, section, or flashcard row is written

### Ingestion — multiple flashcards blocks in one section aborts
- **Given:** A markdown fixture file where one section contains two separate ```flashcards fenced blocks
- **When:** backend.ingest.ingest() is called against that file
- **Then:** An IngestionError is raised; no rows are written

### Ingestion — duplicate card id within file aborts
- **Given:** A markdown fixture file where two flashcards (in different sections) share the same author-assigned id
- **When:** backend.ingest.ingest() is called against that file
- **Then:** An IngestionError is raised; no rows are written

### [UI — manual] Reader view renders sections in order with a Review this section action
- **Given:** An essay has been ingested and the EssayCards app is accessible from Atlas Shell
- **When:** User navigates to the essay's reader view
- **Then:** Sections render in order_index order with rendered markdown body; at the end of each section a "Review this section" button is visible

### [UI — manual] Review session flip-and-grade flow
- **Given:** The user has clicked "Review this section" on a section that has at least one due card
- **When:** The review session loads, shows the card's question, the user clicks Flip, then clicks a grade button
- **Then:** Flip reveals the answer plus a "Jump to passage" link back to that exact section; after grading, the session advances to the next card in the originally-loaded due queue without a new fetch, and ends once that queue is exhausted

### [UI — manual] Jump to passage navigates to the exact section
- **Given:** The review session is showing a flipped card whose "Jump to passage" link points at a known section anchor
- **When:** The user clicks "Jump to passage"
- **Then:** The reader view opens scrolled to that section (matching the DOM anchor for anchor_slug), not just the top of the essay

### [UI — manual] Global "Due for review" entry point surfaces cards from all sections
- **Given:** Due cards exist in more than one section of an essay, some from sections read earlier in a prior session
- **When:** The user opens the top-level "Due for review" nav entry
- **Then:** The review session opens with no section filter and includes due cards from every section, not just the most recently read one
