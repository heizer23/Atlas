#!/usr/bin/env bash
# Off-site backup to Google Drive (rclone remote "gdrive", scope drive.file).
# Uses `copy`, never `sync`: local rotation/deletion must not propagate to the remote.
# Every target is attempted; any failure triggers one phone notification.
set -uo pipefail
. /home/linse/Prod/Atlas/02_Platform/Postgres/backup_notify.sh
RCLONE=/home/linse/.local/bin/rclone
REMOTE=gdrive:atlas-backup
failed=()

copy() {  # copy <label> <src> [extra rclone args...]
  local label=$1 src=$2; shift 2
  echo "$(date -Is) INFO: copy $label"
  $RCLONE copy "$src" "$REMOTE/$label" --log-level INFO "$@" || failed+=("$label")
}

copy postgres /home/linse/Prod/Atlas/02_Platform/Postgres --include "atlas_*.dump"
# EssayCards uploaded images + originals/ archive (not covered by pg_dump)
copy essaycards-images /mnt/data/essaycards/images
# Other apps' on-disk data (logs-only dirs intentionally skipped).
copy familyatlas /mnt/data/familyatlas
copy storyreader-content /mnt/data/storyreader/content
# chronos: exclude secrets/pairing material (least privilege) and logs
copy chronos /mnt/data/chronos \
  --exclude "credentials/**" --exclude "identity/**" --exclude "devices/**" \
  --exclude "telegram/**" --exclude "openclaw*.json*" --exclude "logs/**" --exclude "*.log"

if [ ${#failed[@]} -gt 0 ]; then
  echo "$(date -Is) ERROR: failed: ${failed[*]}" >&2
  notify "Atlas offsite backup FAILED" "Failed targets: ${failed[*]}. See ~/offsite_backup.log"
  exit 1
fi
echo "$(date -Is) INFO: offsite backup OK"
