# Test Spec — StoryReader — Sprint01_Core

## Scope

Backend API and ingestion-CLI behavior for stories, versions, and annotations, including
the paragraph-split algorithm, the create/update/delete reaction semantics, and the
Codex-facing export endpoint. Out of scope: any AI-side behavior on Codex's end, and any
statistics/analytics rendering.

## Scenarios

### Story list — empty state
- **Given:** no story has ever been ingested.
- **When:** `GET /api/storyreader/stories` is called.
- **Then:** the response is a Dataset with zero rows (not an error).

### Story list — marked-passage count reflects the latest version only
- **Given:** the fixture story "lighthouse" (slug `lighthouse`) has two versions, and two
  annotations exist on version 2 (its latest) while one annotation exists on version 1.
- **When:** `GET /api/storyreader/stories` is called.
- **Then:** the "lighthouse" row's `marked_passage_count` is 2, and `latest_version` is 2.

### Story detail — version list for the switcher
- **Given:** the fixture story "lighthouse" has versions 1 and 2.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}` is called.
- **Then:** the response is a Dataset single row whose `versions` field is `[1, 2]`.

### Story detail — unknown story
- **Given:** no story exists with the given id.
- **When:** `GET /api/storyreader/stories/{unknown_id}` is called.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### Ingestion — first publish creates version 1
- **Given:** a markdown file with front matter `slug: harbor-lights`, `title: Harbor
  Lights`, and no story named `harbor-lights` exists yet.
- **When:** `python -m backend.ingest content/harbor-lights.md` is run.
- **Then:** a new story row is created with `latest_version = 1`, a matching
  `story_versions` row (version 1) is created, and the CLI prints an `action: "created"`
  JSON summary including the new `story_id`.

### Ingestion — unchanged content is a no-op
- **Given:** the fixture story "lighthouse" whose version 1 body matches
  `content/lighthouse.md` exactly.
- **When:** `python -m backend.ingest content/lighthouse.md` is run twice in a row.
- **Then:** no new `story_versions` row is created by either run, and both runs print
  `action: "unchanged"`.

### Ingestion — changed content appends a new version
- **Given:** the fixture story "lighthouse" at version 1, and a file
  `content/lighthouse.md` whose body text differs from version 1's stored text.
- **When:** `python -m backend.ingest content/lighthouse.md` is run.
- **Then:** a new `story_versions` row is inserted with `version = 2`, `stories.
  latest_version` becomes 2, and version 1's stored `body_markdown` is unchanged.

### Ingestion — slug/filename mismatch is rejected
- **Given:** a file at `content/foo.md` whose front matter declares `slug: bar`.
- **When:** `python -m backend.ingest content/foo.md` is run.
- **Then:** the command exits non-zero, prints an error to stderr, and no story or
  version row is written.

### Ingestion — re-ingestion can change title without a new version
- **Given:** the fixture story "lighthouse" with `title: "The Lighthouse"`, and a file
  `content/lighthouse.md` with the same body text but `title: "The Old Lighthouse"`.
- **When:** `python -m backend.ingest content/lighthouse.md` is run.
- **Then:** the story's `title` is updated to "The Old Lighthouse", no new
  `story_versions` row is created, and the CLI prints `action: "unchanged"`.

### Paragraph split — blank-line-separated paragraphs
- **Given:** a body_markdown of two plain-text blocks separated by a blank line.
- **When:** `split_paragraphs` is called on that text.
- **Then:** it returns exactly two paragraph strings, in order.

### Paragraph split — a multi-line list is one paragraph
- **Given:** a body_markdown block of three consecutive `- item` lines with no blank
  line between them.
- **When:** `split_paragraphs` is called on that text.
- **Then:** it returns exactly one paragraph string for that block (not three).

### Paragraph split — a fenced code block is one paragraph with fences dropped
- **Given:** a body_markdown block delimited by ``` fence lines containing two lines of
  code.
- **When:** `split_paragraphs` is called on that text.
- **Then:** it returns exactly one paragraph string for that block, containing the two
  code lines space-joined, with no literal fence markers in the output.

### Version content — default resolves to latest
- **Given:** the fixture story "lighthouse" with `latest_version = 2`.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/latest` is called.
- **Then:** the response's `version` field is 2 and `paragraphs` reflects version 2's
  body text.

### Version content — explicit old version remains readable
- **Given:** the fixture story "lighthouse" with versions 1 and 2.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/1` is called.
- **Then:** the response's `version` field is 1 and `paragraphs` reflects version 1's
  original body text, unaffected by version 2 existing.

### Version content — unknown version number
- **Given:** the fixture story "lighthouse" has only versions 1 and 2.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/7` is called.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### Version content — malformed version segment
- **Given:** the fixture story "lighthouse" exists.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/not-a-number` is
  called.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`.

### Annotations list — reading order
- **Given:** the fixture story "lighthouse" version 2 has three annotations at
  paragraph_index 0, 1, and 1 (two annotations in paragraph 1 at different char
  offsets).
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/2/annotations` is
  called.
- **Then:** the three rows are returned ordered by `paragraph_index` ascending, then
  `char_start` ascending.

### Annotations list — no implicit latest
- **Given:** the fixture story "lighthouse" exists.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/latest/annotations` is
  called.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR` (the literal
  "latest" is not accepted on this endpoint).

### Create annotation — new span
- **Given:** the fixture story "lighthouse" version 2, paragraph 0's rendered text is at
  least 20 characters long, and no annotation exists yet at paragraph_index 0,
  char_start 0, char_end 10.
- **When:** `POST /api/storyreader/annotations` is called with that exact span,
  `selected_text` equal to the true substring, and `reaction: "positive"`.
- **Then:** the response is HTTP 201 with the new annotation record, including its
  generated `id`.

### Create annotation — reaction changed at the same exact span
- **Given:** an existing annotation from the previous scenario with `reaction:
  "positive"` at paragraph_index 0, char_start 0, char_end 10.
- **When:** `POST /api/storyreader/annotations` is called again with the identical span
  but `reaction: "unclear"`.
- **Then:** the response is HTTP 200, the same annotation `id` is returned, `reaction`
  is now "unclear", and `created_at` is unchanged while `updated_at` has advanced.

### Create annotation — selected_text must match the true substring
- **Given:** the fixture story "lighthouse" version 2, paragraph 0.
- **When:** `POST /api/storyreader/annotations` is called with char_start/char_end that
  correspond to different text than the `selected_text` value supplied.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and no row is
  written.

### Create annotation — invalid reaction rejected
- **Given:** a valid span with no existing annotation.
- **When:** `POST /api/storyreader/annotations` is called with `reaction: "meh"`.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and no row is
  written.

### Create annotation — char_end not after char_start
- **Given:** a valid paragraph.
- **When:** `POST /api/storyreader/annotations` is called with `char_start: 5,
  char_end: 5`.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`.

### Create annotation — unknown story or version
- **Given:** an annotation body naming a `story_id` that does not exist.
- **When:** `POST /api/storyreader/annotations` is called.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### Delete annotation — toggle-off removes the row
- **Given:** an existing annotation with a known `id`.
- **When:** `DELETE /api/storyreader/annotations/{id}` is called.
- **Then:** the response is HTTP 204, and a subsequent `GET .../annotations` for that
  version no longer includes that row.

### Delete annotation — unknown id
- **Given:** no annotation exists with the given id.
- **When:** `DELETE /api/storyreader/annotations/{unknown_id}` is called.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### Publishing a new version never touches existing annotations
- **Given:** the fixture story "lighthouse" version 1 has one annotation.
- **When:** ingestion publishes a new version 2 with different body text.
- **Then:** version 1's annotation row is unchanged (same id, same fields), and
  `GET .../versions/2/annotations` returns zero rows.

### Export — self-contained JSON for Codex
- **Given:** the fixture story "lighthouse" version 2 has two annotations, in reading
  order.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/2/annotations/export`
  is called.
- **Then:** the response is HTTP 200 with a JSON body (not a Dataset envelope)
  containing `slug`, `title`, `version: 2`, `annotation_count: 2`, and an `annotations`
  array of exactly those two annotations in reading order, each carrying `reaction`
  verbatim (never translated into a guessed label).

### Export — empty version is valid, not an error
- **Given:** the fixture story "lighthouse" version 1 has zero annotations.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/1/annotations/export`
  is called.
- **Then:** the response is HTTP 200 with `annotation_count: 0` and `annotations: []`.

### Export — unknown version
- **Given:** the fixture story "lighthouse" has only versions 1 and 2.
- **When:** `GET /api/storyreader/stories/{lighthouse_id}/versions/9/annotations/export`
  is called.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### [UI — manual] Tap-to-react saves without confirmation
- **Given:** a user is viewing the Reader for a story version with no existing
  annotation on the passage they select.
- **When:** the user selects a sentence and taps the "positive" reaction button.
- **Then:** the passage immediately shows a quiet highlight with a small positive-reaction
  icon, with no confirmation dialog or extra tap, and the Feedback list for that version
  now includes the new entry.

### [UI — manual] Tapping the active reaction again removes it
- **Given:** a passage in the Reader is already highlighted with the "unclear" reaction.
- **When:** the user taps the passage and then taps "unclear" again (the currently-active
  one).
- **Then:** the highlight disappears immediately and the entry no longer appears in the
  Feedback list, with no confirmation step.

### [UI — manual] Feedback list row jumps back to its passage
- **Given:** the Feedback list for a story version shows at least one annotation row.
- **When:** the user taps that row.
- **Then:** the app navigates to the Reader for the same story and version, scrolls the
  corresponding passage into view, and briefly highlights it.
