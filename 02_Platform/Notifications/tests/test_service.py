"""
Unit tests for NotificationService (create, cancel, replace) and
dispatch_due_notifications.

Test scenarios per architecture.json deferrals.test_writer.
These tests require a live Postgres instance with the notifications schema applied.
For unit isolation, database.get_db and fcm_client.send_fcm_message should be mocked.
"""

# TODO (test_writer): implement the following test cases
#
# NotificationService.create
#   - POST with valid body returns NotificationRecord with generated id and status=pending
#   - POST with missing required field raises ValidationError (pydantic)
#   - POST with fire_at in the past is accepted and persisted with status=pending
#   - POST with deep_link not starting with atlas:// raises ValidationError
#   - Returned NotificationRecord does not contain fcm_token field
#
# NotificationService.cancel
#   - cancel on pending record updates status to cancelled
#   - cancel on dispatched record returns without error (no state change)
#   - cancel on already-cancelled record returns without error (idempotent)
#   - cancel on failed record returns without error (idempotent for all terminal states)
#   - cancel on non-existent id raises NotificationNotFoundError
#
# NotificationService.replace
#   - replace cancels old record and creates new record with a new UUID
#   - replace with non-existent old_id raises NotificationNotFoundError without creating new record
#   - replace propagates create error if cancel succeeds but create fails
#
# dispatch_due_notifications
#   - pending record with fire_at in the past triggers FCM send and updates status=dispatched
#   - pending record with fire_at in the future is not dispatched
#   - dispatched record is not processed again (status=dispatched filtered out by query)
#   - FCM failure updates status=failed, does not raise, logs at ERROR level
#   - INFO log on successful dispatch contains notification_id, fire_at, dispatched_at, delta_ms
#   - fcm_token does not appear in any log output (check log handler captures)
#   - delta_ms is computed as (dispatched_at - fire_at), not (dispatched_at - created_at)
#
# Startup
#   - missing FCM credential env var causes RuntimeError at startup (not silent degradation)
#   - APScheduler dispatch job is registered and running after start_scheduler()
