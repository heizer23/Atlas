# Test Spec — EssayCards — Sprint02_JsonIngestion

## Scope

HTTP-level tests (pytest + Starlette TestClient against a test Postgres database) for the new `POST /api/essaycards/essays/ingest` endpoint, covering structural validation, the all-or-nothing rollback guarantee, the card-id/different-section collision check, and the upsert-onto-existing-essay path. Out of scope: re-verifying Sprint01's existing GET essays/due/review scenarios (unchanged, `test_essays.py`/`test_flashcards.py`/`test_ingest.py` remain the regression suite for those and for the `backend.ingest.ingest()`/`upsert_document()` refactor). UI behavior for the new "Add / Update Essay" view is covered by manual scenarios below — no automated UI test infrastructure is set up for EssayCards.

## Scenarios

### Ingest — creates a new essay via JSON
- **Given:** No essay exists with slug `new-essay-via-json`
- **When:** `POST /api/essaycards/essays/ingest` is called with a well-formed payload — title, `slug: "new-essay-via-json"`, one section with two cards
- **Then:** Response is 200; body has `essay_id` (a new uuid), `slug: "new-essay-via-json"`, `sections_created: 1`, `sections_updated: 0`, `cards_created: 2`, `cards_updated: 0`; `GET /api/essaycards/essays/{essay_id}` confirms the section and both flashcards exist, each new flashcard due immediately

### Ingest — upserts onto an existing essay by slug and preserves review state
- **Given:** Fixture essay slug `origins-of-long-form-formats` exists with section anchor `origins` and card `fc-origins-1`; `fc-origins-1` has a known `last_reviewed_at`/`next_due_at` from fixtures
- **When:** `POST .../ingest` is called with `slug: "origins-of-long-form-formats"`, a section with `anchor_slug: "origins"` (same heading), containing card `id: "fc-origins-1"` with an updated `q` text plus one brand-new card id in the same section
- **Then:** Response is 200; `essay_id` equals the fixture essay's id; `sections_updated` includes the `origins` section; `cards_updated >= 1` and `cards_created >= 1`; `fc-origins-1`'s question text is updated but its `flashcard_review_state.last_reviewed_at`/`next_due_at` are unchanged from before this request

### Ingest — order_index follows payload array order
- **Given:** Fixture essay `origins-of-long-form-formats` has sections `origins` (order_index 0) and `structure` (order_index 1)
- **When:** `POST .../ingest` resubmits the same slug with the sections array reversed (`structure` first, `origins` second), both sections otherwise unchanged
- **Then:** Response is 200; `GET /api/essaycards/essays/{essay_id}` shows `structure` at `order_index: 0` and `origins` at `order_index: 1`

### Ingest — rejects a malformed payload before any write (all-or-nothing rollback)
- **Given:** No essay exists with slug `rollback-test`
- **When:** `POST .../ingest` is called with a payload containing two structurally valid sections plus a third section missing the required `anchor_slug` field
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`; `GET /api/essaycards/essays` confirms no essay with slug `rollback-test` was created, and no section or card from any of the three sections (including the two otherwise-valid ones) was written anywhere

### Ingest — rejects duplicate anchor_slug within payload
- **Given:** No precondition
- **When:** `POST .../ingest` is called with two sections sharing the same `anchor_slug`
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`

### Ingest — rejects duplicate card id within payload
- **Given:** No precondition
- **When:** `POST .../ingest` is called with two cards, in different sections, sharing the same `id`
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`

### Ingest — rejects a card id colliding with an existing card in a different section
- **Given:** Fixture card `fc-origins-1` is attached to section anchor `origins` of essay slug `origins-of-long-form-formats`
- **When:** `POST .../ingest` is called with `slug: "origins-of-long-form-formats"` and a section with `anchor_slug: "structure"` (existing section) containing a card with `id: "fc-origins-1"`
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`; `GET /api/essaycards/essays/{essay_id}` afterward confirms `fc-origins-1` still belongs to section `origins`, unchanged — no write occurred as a result of this request

### Ingest — rejects an unparsable JSON body
- **Given:** No precondition
- **When:** `POST .../ingest` is called with a request body that is not valid JSON
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"` (never FastAPI's default `{"detail": [...]}` 422 shape)

### Ingest — rejects a payload missing a required top-level field
- **Given:** No precondition
- **When:** `POST .../ingest` is called with a JSON object missing the `slug` field
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`

### Ingest — rejects an empty sections array
- **Given:** No precondition
- **When:** `POST .../ingest` is called with `sections: []`
- **Then:** Response is 400; body is `ApiError` with `error.code="VALIDATION_ERROR"`

### [UI — manual] Add / Update Essay view submits JSON and shows a success summary
- **Given:** The user opens the "Add / Update Essay" nav entry in the EssayCards app
- **When:** The user pastes a well-formed JSON payload into the textarea and clicks submit
- **Then:** A success summary appears showing the sections/cards created vs. updated counts, plus a link that opens the newly ingested essay in the reader

### [UI — manual] Add / Update Essay view shows an inline error without clearing the textarea
- **Given:** The user is on the "Add / Update Essay" view
- **When:** The user submits malformed JSON (or JSON that fails backend validation) and clicks submit
- **Then:** The `ApiError` message/detail is shown inline on the page; the textarea still contains exactly the text the user typed, not cleared

### [UI — manual] Essay picker lists more than one ingested essay
- **Given:** At least two essays exist — one ingested via the markdown CLI, one via the new "Add / Update Essay" JSON view
- **When:** The user opens the EssayCards app's essay list (already-existing view, no new work this sprint)
- **Then:** Both essays are listed with working links into their respective reader views, confirming the list view remains correct once JSON ingestion creates additional essays
