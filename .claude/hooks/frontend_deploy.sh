#!/usr/bin/env bash
# Frontend deploy hook. Modes:
#   mark   (PostToolUse Edit|Write) — flag the session when a shell/app frontend source file changed
#   deploy (Stop)                   — if flagged: vite build + docker cp into atlas-shell, then clear the flag
# Deploy steps per memory "Frontend deploy after every change". A full image rebuild is needed
# (not done here) when nginx.conf or Atlas_Shell/Dockerfile changed; the hook only warns.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-/home/linse/Prod/Atlas}"
FLAG="$ROOT/.claude/.frontend_dirty"
SHELL_DIR="$ROOT/02_Platform/Atlas_Shell"
IN="$(cat)"

case "${1:-}" in
mark)
  f="$(printf '%s' "$IN" | jq -r '.tool_input.file_path // empty')"
  [ -n "$f" ] || exit 0
  case "$f" in
    */node_modules/*|*/dist/*|*/tests/*) exit 0 ;;
    */02_Platform/Atlas_Shell/nginx.conf|*/02_Platform/Atlas_Shell/Dockerfile) echo "$f needs full rebuild" >> "$FLAG.rebuild"; exit 0 ;;
    */02_Platform/Atlas_Shell/*.tsx|*/02_Platform/Atlas_Shell/*.ts|*/02_Platform/Atlas_Shell/*.css|\
    */03_Application/*/src/*.tsx|*/03_Application/*/src/*.ts|*/03_Application/*/src/*.css) : > "$FLAG" ;;
  esac
  exit 0 ;;
deploy)
  if [ -f "$FLAG.rebuild" ]; then
    echo "NOTE: $(cat "$FLAG.rebuild") — run: cd 02_Platform/Atlas_Shell && docker compose up -d --build (docker cp does not pick this up)." >&2
    rm -f "$FLAG.rebuild"
  fi
  [ -f "$FLAG" ] || exit 0
  stop_active="$(printf '%s' "$IN" | jq -r '.stop_hook_active // false')"
  # Node 24 segfaults in ~1 of 10 vite builds (0/40 on Node 22), so retry the build up to 3 times.
  for attempt in 1 2 3; do
    out="$(cd "$SHELL_DIR" && npx vite build 2>&1 && docker cp dist/. atlas-shell:/usr/share/nginx/html/ 2>&1)"
    rc=$?
    [ $rc -eq 0 ] && break
  done
  if [ $rc -eq 0 ]; then
    rm -f "$FLAG"
    exit 0
  fi
  # On failure keep the flag so the next Stop retries; exit 2 once so Claude sees the error, never loop.
  if [ "$stop_active" = "true" ]; then exit 0; fi
  printf 'Frontend deploy failed:\n%s\n' "$(printf '%s' "$out" | tail -30)" >&2
  exit 2 ;;
esac
exit 0
