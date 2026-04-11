#!/usr/bin/env bash
# Chronos session analyzer — pull and analyze the live session from atlas-chronos.
#
# Usage:
#   ./chronos_analyze.sh                    # summary only
#   ./chronos_analyze.sh --verbose          # with per-tool-call detail
#   ./chronos_analyze.sh --all              # show all interactions (not just flagged)
#   ./chronos_analyze.sh --min-tools 3     # lower/raise flagging threshold
#   ./chronos_analyze.sh --checkpoint      # analyze the checkpoint (historical) session
#   ./chronos_analyze.sh --list            # list available sessions and exit

set -euo pipefail

CONTAINER="atlas-chronos"
SESSION_DIR="/home/node/.openclaw/agents/main/sessions"
TMP_DIR="/tmp/chronos_sessions"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER="$SCRIPT_DIR/analyze_session.py"

mkdir -p "$TMP_DIR"

# ── List mode ────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--list" ]]; then
    echo "Sessions in atlas-chronos:"
    docker exec "$CONTAINER" ls -lh "$SESSION_DIR"
    exit 0
fi

# ── Find sessions ─────────────────────────────────────────────────────────────

USE_CHECKPOINT=false
for arg in "$@"; do
    if [[ "$arg" == "--checkpoint" ]]; then
        USE_CHECKPOINT=true
    fi
done

# Get list of session files
SESSION_FILES=$(docker exec "$CONTAINER" ls "$SESSION_DIR" | grep '\.jsonl$' || true)

if [[ -z "$SESSION_FILES" ]]; then
    echo "No session files found in $CONTAINER:$SESSION_DIR"
    exit 1
fi

if $USE_CHECKPOINT; then
    # Find checkpoint files (they contain ".checkpoint.")
    CHECKPOINT=$(echo "$SESSION_FILES" | grep '\.checkpoint\.' | tail -1 || true)
    if [[ -z "$CHECKPOINT" ]]; then
        echo "No checkpoint session found. Available sessions:"
        echo "$SESSION_FILES"
        exit 1
    fi
    TARGET="$CHECKPOINT"
    LABEL="checkpoint"
else
    # Find the active (non-checkpoint) session — shortest name = no checkpoint suffix
    ACTIVE=$(echo "$SESSION_FILES" | grep -v '\.checkpoint\.' | tail -1 || true)
    if [[ -z "$ACTIVE" ]]; then
        # Fall back to checkpoint if no active session
        ACTIVE=$(echo "$SESSION_FILES" | tail -1)
    fi
    TARGET="$ACTIVE"
    LABEL="active"
fi

# ── Pull and analyze ──────────────────────────────────────────────────────────

LOCAL_PATH="$TMP_DIR/${TARGET}"
echo "Pulling $LABEL session: $TARGET"
docker cp "$CONTAINER:$SESSION_DIR/$TARGET" "$LOCAL_PATH" 2>/dev/null

echo "Analyzing..."

# Pass remaining args (minus --checkpoint) to the Python script
PASS_ARGS=()
for arg in "$@"; do
    if [[ "$arg" != "--checkpoint" ]]; then
        PASS_ARGS+=("$arg")
    fi
done

# Default: summary only unless --verbose or --all passed
HAS_OUTPUT_FLAG=false
for arg in "$@"; do
    if [[ "$arg" == "--verbose" || "$arg" == "--all" || "$arg" == "--summary-only" ]]; then
        HAS_OUTPUT_FLAG=true
    fi
done

if ! $HAS_OUTPUT_FLAG; then
    PASS_ARGS+=("--summary-only")
fi

python3 "$ANALYZER" "$LOCAL_PATH" "${PASS_ARGS[@]}"
