"""
Integration tests for the Notifications HTTP endpoints using FastAPI TestClient.

Covers request validation, response shapes, and error responses.
These tests mock the Postgres pool and FCM client to run without external services.

Test scenarios per architecture.json deferrals.test_writer.
"""

# TODO (test_writer): implement the following test cases using FastAPI TestClient
#
# POST /api/notifications/
#   - valid body returns HTTP 201 with NotificationRecord (has id, status=pending, no fcm_token)
#   - missing required field (e.g., title) returns HTTP 422 (Pydantic validation)
#   - deep_link not starting with atlas:// returns HTTP 422
#   - fire_at in the past is accepted, returns 201
#
# DELETE /api/notifications/{notification_id}
#   - pending notification: returns HTTP 200 with {"cancelled": "<id>"}
#   - dispatched notification: returns HTTP 200 (no-op)
#   - already-cancelled notification: returns HTTP 200 (no-op, idempotent)
#   - non-existent id: returns HTTP 404 with error.code=NOTIFICATION_NOT_FOUND
#
# POST /api/notifications/{notification_id}/replace
#   - valid old_id and new body: returns HTTP 201 with new NotificationRecord (new UUID)
#   - non-existent old_id: returns HTTP 404 with error.code=NOTIFICATION_NOT_FOUND
#   - new body fails validation: returns HTTP 422 without cancelling old record
#
# Response shape invariants
#   - All success responses must not contain fcm_token field
#   - All error responses must use the api_error envelope: {"error": {"code", "message", ...}}
