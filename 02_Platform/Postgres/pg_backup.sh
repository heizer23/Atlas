#!/usr/bin/env bash
# Daily pg_dump: write to .tmp, validate the archive, only then publish + rotate (keep 14).
set -uo pipefail
DIR=/home/linse/Prod/Atlas/02_Platform/Postgres
. "$DIR/backup_notify.sh"
OUT="$DIR/atlas_$(date +%Y%m%d_%H%M%S).dump"
fail() { echo "$(date -Is) ERROR: $1" >&2; rm -f "$OUT.tmp"; notify "Atlas DB backup FAILED" "$1"; exit 1; }

docker exec atlas-postgres pg_dump -U atlas -Fc atlas > "$OUT.tmp" || fail "pg_dump failed"
[ -s "$OUT.tmp" ] || fail "pg_dump produced an empty file"
docker exec -i atlas-postgres pg_restore -f - < "$OUT.tmp" >/dev/null 2>&1 || fail "dump failed pg_restore validation"
mv "$OUT.tmp" "$OUT"
find "$DIR" -name 'atlas_*.dump' -type f | sort | head -n -14 | xargs -r rm -f
echo "$(date -Is) INFO: wrote $OUT ($(stat -c %s "$OUT") bytes)"
