-- Sprint01_Immediate_Notify migration
-- Notifications platform — notifications.notification table
--
-- Makes label, deep_link, and fire_at nullable to support immediate-send rows.
-- Existing rows are unaffected (their values remain non-null).
-- Safe to run on a live table.
--
-- NULL fire_at semantics: fire_at=NULL means immediate send.
-- The dispatch job (WHERE status='pending' AND fire_at <= NOW()) never matches
-- NULL fire_at rows because NULL comparisons evaluate to NULL (not true).
-- No change to dispatch_job.py is required.
--
-- label and deep_link store empty string '' for immediate-send rows.
-- They are passed to send_fcm_message() per the FCM payload contract v1.0.

ALTER TABLE notifications.notification ALTER COLUMN fire_at   DROP NOT NULL;
ALTER TABLE notifications.notification ALTER COLUMN label     DROP NOT NULL;
ALTER TABLE notifications.notification ALTER COLUMN label     SET DEFAULT '';
ALTER TABLE notifications.notification ALTER COLUMN deep_link DROP NOT NULL;
ALTER TABLE notifications.notification ALTER COLUMN deep_link SET DEFAULT '';
