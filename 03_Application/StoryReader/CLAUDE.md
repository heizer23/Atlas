# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
StoryReader is a mobile-first reader for markdown stories, built to capture fast,
low-friction passage feedback while reading on a phone: select a sentence or paragraph,
tap one of four reactions (👍 positive / 👎 negative / 😐 neutral / ❓ unclear), done —
no confirmation, no comments. A per-story feedback list shows every marked passage in
reading order; tapping a row jumps back to the passage in the Reader.

Stories are authored and published entirely outside this app, by a separate agent
("Codex") that has direct SSH access to the server. This section is the authoritative
reference for both the human and Codex — restated from `Sprint01_Core/00_draft.md`
§Codex Integration.

## Codex Integration

**Publishing a story or a new version**
1. Write/overwrite `<content_dir>/<slug>.md` over your SSH session — YAML front matter
   with `title` and `slug` (stable identity, never changes once assigned), then the
   markdown body.
2. Run the one-shot ingestion CLI (no upload endpoint exists or is needed):
   ```
   docker exec atlas-storyreader python -m backend.ingest content/<slug>.md
   ```
3. First ingestion of a slug creates the story (version 1). Re-ingestion compares the
   file's content by hash against the story's current latest version:
   - Unchanged body text → no-op (`action: "unchanged"`); `title` may still be updated.
   - Changed body text → a new, immutable version is appended (`action: "new_version"`).
   - A front-matter `slug` that does not match the filename (`<slug>.md`) aborts
     ingestion before any write (`action` is never printed; a message goes to stderr
     and the process exits non-zero).
4. On success the CLI prints a one-line JSON summary to stdout, e.g.:
   ```
   {"action": "created", "slug": "harbor-lights", "story_id": "<uuid>", "version": 1}
   ```
   **This is your only low-friction way to learn a new story's `story_id`** — no
   endpoint accepts a `slug` as an alternative to `story_id` in any URL path (see
   `Sprint01_Core/10_architecture.json` §contracts.invariants). If you don't have the
   id handy, resolve it via `GET /api/storyreader/stories` (every row carries `slug`).

**Retrieving annotations for discussion**
```
curl http://127.0.0.1:8026/api/storyreader/stories/{story_id}/versions/{version}/annotations/export
```
Returns bespoke JSON (not a Dataset — built for this round trip, not for a
Dataset-consuming UI component): `slug`, `title`, `version`, `annotation_count`, and
`annotations` — each carrying `selected_text`, `context_before`, `context_after`,
`reaction` (verbatim `positive`/`negative`/`neutral`/`unclear` — never translated into a
guessed "reason"), `created_at`, `updated_at` — in reading order. Empty is valid
(`annotation_count: 0`) when nothing has been marked yet on that version.

Publishing a new version never touches, migrates, or re-anchors annotations from an
older version — an annotation belongs to the exact `(story_id, version)` it was made
against; a brand-new version starts with zero annotations.

## Port
StoryReader backend runs on host port 8026 (container port 8000), bound to
`127.0.0.1` only (least exposure — Codex reaches it via `curl` over its own SSH
session; the browser UI reaches it through Atlas Shell's nginx proxy over `atlas-net`,
which is unaffected by the loopback-only host binding).

## Schema
`storyreader` schema in the shared Atlas Postgres instance.
Tables: `storyreader.stories`, `storyreader.story_versions` (immutable, append-only),
`storyreader.annotations`. Schema initialized idempotently at startup from
`schema.sql`.

## Content folder
`STORYREADER_CONTENT_DIR` (host-side, set in `01_System/secrets.env`) is used only in
`compose.yml`'s volume mapping (`${STORYREADER_CONTENT_DIR}:/app/content:ro`) — the
Python app always reads the fixed container path `/app/content` and never reads this
env var itself, so the bind-mount source can be repointed without a code change.

## Pattern references
Follow the same patterns as StorageTracker / EssayCards (03_Application):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses on GET endpoints
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts (mobilePrimaryNav primary target)

One deliberate scope boundary: there is no in-app authoring/editing UI and no delete
endpoint for a story or a version — ingestion (CLI-only) is the sole way content
enters this app, and it is append-only, same convention as EssayCards' essay/section
ingestion.
