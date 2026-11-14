#!/usr/bin/env bash
# Sourced by the backup scripts. notify "<title>" "<body>" pushes to the phone via
# the Notifications service (localhost only). Never fails the caller.
NOTIFY_URL=http://127.0.0.1:8020/api/notifications/send
notify() {
  curl -fsS -m 15 -X POST "$NOTIFY_URL" -H 'Content-Type: application/json' \
    -d "$(printf '{"title":"%s","body":"%s","source":"backup"}' "$1" "$2")" >/dev/null \
    || echo "$(date -Is) WARN: notification failed: $1 — $2" >&2
  return 0
}
