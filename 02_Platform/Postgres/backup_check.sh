#!/usr/bin/env bash
# Watchdog (runs after the dump + offsite jobs): alerts if today's dump is missing locally
# or on Drive. Catches jobs that never ran (cron/docker/network down), not just ones that errored.
set -uo pipefail
DIR=/home/linse/Prod/Atlas/02_Platform/Postgres
. "$DIR/backup_notify.sh"
today=$(date +%Y%m%d)
problems=()

local_f=$(ls "$DIR"/atlas_${today}_*.dump 2>/dev/null | tail -1)
if [ -z "$local_f" ]; then problems+=("no local dump for $today")
elif [ "$(stat -c %s "$local_f")" -lt 10000 ]; then problems+=("local dump suspiciously small")
fi

remote=$(/home/linse/.local/bin/rclone lsf gdrive:atlas-backup/postgres --include "atlas_${today}_*.dump" 2>/dev/null)
[ -n "$remote" ] || problems+=("no Drive copy for $today")

if [ ${#problems[@]} -gt 0 ]; then
  echo "$(date -Is) ERROR: ${problems[*]}" >&2
  notify "Atlas backup MISSING" "${problems[*]}"
  exit 1
fi
echo "$(date -Is) INFO: backup check OK ($remote)"
