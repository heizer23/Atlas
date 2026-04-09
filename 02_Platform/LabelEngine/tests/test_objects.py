"""
LabelEngine — attach, remove, get-labels-for-object, and batch-labels test stubs.

Bodies deferred to Test_Writer.
Source of truth: 20_design/architecture.json deferrals.test_writer
"""

# TODO: POST /api/objects/{object_id}/labels — attaches existing label by name
# TODO: POST /api/objects/{object_id}/labels — creates new label inline and attaches
# TODO: POST /api/objects/{object_id}/labels — duplicate attach is idempotent (no error, no duplicate row)
# TODO: DELETE /api/objects/{object_id}/labels/{label_id} — removes existing attachment
# TODO: DELETE /api/objects/{object_id}/labels/{label_id} — returns 404 ATTACHMENT_NOT_FOUND when pair absent
# TODO: GET /api/objects/{object_id}/labels — returns labels in attached_at ASC order
# TODO: GET /api/objects/{object_id}/labels — returns empty list for object with no labels
# TODO: DB_UNAVAILABLE — all write endpoints return 503 when pool exhausted

# ── POST /api/objects/labels/batch ────────────────────────────────────────────
# TODO: happy path — two objects each with labels; verify both keys present, labels ordered attached_at ASC label_id ASC
# TODO: partial hit — one object has labels, one has none; verify zero-fill (empty list, key present)
# TODO: all requested IDs have no labels — verify all keys present with empty lists
# TODO: empty object_ids [] — verify immediate {"labels": {}} return, no DB query
# TODO: over-limit — 201 object_ids — verify 422 BATCH_TOO_LARGE
# TODO: object_type mismatch — labels attached with a different object_type are NOT returned for a batch with mismatched type
# TODO: missing / empty object_type — verify 422 OBJECT_TYPE_REQUIRED
