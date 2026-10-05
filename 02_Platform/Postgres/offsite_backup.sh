#!/usr/bin/env bash
# Off-site backup to Google Drive (rclone remote "gdrive", scope drive.file).
# Uses `copy`, never `sync`: local rotation/deletion must not propagate to the remote.
set -euo pipefail
RCLONE=/home/linse/.local/bin/rclone
REMOTE=gdrive:atlas-backup

$RCLONE copy /home/linse/Prod/Atlas/02_Platform/Postgres "$REMOTE/postgres" \
  --include "atlas_*.dump" --log-level ERROR
# EssayCards uploaded images + originals/ archive (not covered by pg_dump)
$RCLONE copy /mnt/data/essaycards/images "$REMOTE/essaycards-images" --log-level ERROR

# Other apps' on-disk data (logs-only dirs intentionally skipped).
$RCLONE copy /mnt/data/familyatlas "$REMOTE/familyatlas" --log-level ERROR
$RCLONE copy /mnt/data/storyreader/content "$REMOTE/storyreader-content" --log-level ERROR
# chronos: exclude secrets/pairing material (least privilege) and logs
$RCLONE copy /mnt/data/chronos "$REMOTE/chronos" --log-level ERROR \
  --exclude "credentials/**" --exclude "identity/**" --exclude "devices/**" \
  --exclude "telegram/**" --exclude "openclaw*.json*" --exclude "logs/**" --exclude "*.log"
