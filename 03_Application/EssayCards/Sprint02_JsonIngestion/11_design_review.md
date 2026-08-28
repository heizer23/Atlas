# Design Review — EssayCards (Sprint02_JsonIngestion)

## Verdict
- Status: APPROVED
- Summary: This design directly and correctly applies the two lessons from Sprint01's review cycle. `POST /api/essaycards/essays/ingest` is specified end-to-end (draft, architecture, scaffolding, dependencies.forbidden) to read the raw Starlette `Request` and validate manually — never a Pydantic body model — closing the exact `RequestValidationError`/`ApiError` bypass found in Sprint01 round 1. The `upsert_document(conn, doc)` extraction is specified with a concrete module boundary, function signature, and an explicit unchanged-vs-changed split, and is verifiably behavior-preserving against Sprint01's actual test file (attribute-based assertions, no dataclass-equality checks that a new default-valued field could break). The essay list/picker is correctly identified as already built and no duplicate view is scaffolded. No Critical or Major issues were found.

## Confirmed Problems
None identified.

## Recommended Improvements
1. **Title/slug/body_markdown whitespace normalization inconsistency between ingestion entry points**
   - Location: `10_architecture.json` §internal_flow step 8 (`json_ingest_validate`) vs. `backend/ingest.py::_parse_front_matter` (markdown path — `title.strip(), slug.strip()` — and `_split_body_and_cards`, which stores `body_markdown` as `.strip()`ped content)
   - Improvement: Specify in step 8 (and `_validate_ingest_body`'s scaffold role) whether `title` and `body_markdown` are trimmed before being written into `doc`, and whether `slug`/`anchor_slug`/card `id` are trimmed before the `^[a-zA-Z0-9_-]+$` regex is applied or intentionally left un-trimmed (meaning a value with leading/trailing whitespace is rejected by the JSON path, where the markdown path would silently strip and accept the equivalent front-matter value).
   - Why: 00_draft.md's Goal states the two entry points "behave identically for equivalent content." As written, a JSON payload with padded `title`/`body_markdown` text would persist the padding (the markdown path would not), and a padded `slug` would be rejected outright by the JSON path's regex where the markdown path accepts it after stripping. This is a minor, low-likelihood edge case, not a blocking defect — but it is currently unaddressed by both `10_architecture.json` and `10_scaffolding.json`.

## Scaffold-Only Observations
None identified.

## Hard Rule Violations
None identified.

## Open Uncertainties
None identified.

## Minimal Change Set
None — no required changes remain.

## Approval Condition
None — approved as-is.
