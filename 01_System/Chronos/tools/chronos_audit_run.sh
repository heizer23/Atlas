#!/usr/bin/env bash
# Chronos audit runner — pull all sessions from atlas-chronos and run incremental analysis.
# Designed to be run on a cron schedule (e.g. every 4 hours).
#
# Writes to:
#   $DATA_DIR/analysis_state.json   — cursor per session (last analyzed timestamp)
#   $DATA_DIR/audit_log.jsonl       — append-only log of flagged interactions
#   $DATA_DIR/runs/YYYY-MM-DD_HH.log — stdout from each run
#
# Usage:
#   ./chronos_audit_run.sh               # normal run
#   ./chronos_audit_run.sh --reprocess   # ignore cursor, reanalyze all interactions

set -euo pipefail

CONTAINER="atlas-chronos"
SESSION_DIR="/home/node/.openclaw/agents/main/sessions"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER="$SCRIPT_DIR/analyze_session.py"

DATA_DIR="$SCRIPT_DIR/data"
STATE_FILE="$DATA_DIR/analysis_state.json"
AUDIT_LOG="$DATA_DIR/audit_log.jsonl"
RUN_LOG_DIR="$DATA_DIR/runs"

mkdir -p "$DATA_DIR" "$RUN_LOG_DIR"

REPROCESS=false
for arg in "$@"; do
    [[ "$arg" == "--reprocess" ]] && REPROCESS=true
done

RUN_TS="$(date -u '+%Y-%m-%d_%H')"
RUN_LOG="$RUN_LOG_DIR/${RUN_TS}.log"

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RUN_LOG"; }

log "=== Chronos audit run started ==="
log "Container: $CONTAINER"
log "Audit log: $AUDIT_LOG"
log "State file: $STATE_FILE"

# ── List sessions in container ────────────────────────────────────────────────

SESSION_FILES=$(docker exec "$CONTAINER" ls "$SESSION_DIR" 2>/dev/null | grep '\.jsonl$' || true)

if [[ -z "$SESSION_FILES" ]]; then
    log "No session files found. Exiting."
    exit 0
fi

log "Found sessions: $(echo "$SESSION_FILES" | wc -l | tr -d ' ')"

# ── Process each session ──────────────────────────────────────────────────────

TMP_DIR="$DATA_DIR/tmp"
mkdir -p "$TMP_DIR"

TOTAL_NEW=0
TOTAL_FLAGGED=0

while IFS= read -r SESSION_FILE; do
    [[ -z "$SESSION_FILE" ]] && continue

    SESSION_ID="${SESSION_FILE%%.*}"
    LOCAL_PATH="$TMP_DIR/$SESSION_FILE"

    log "Pulling: $SESSION_FILE"
    if ! docker cp "$CONTAINER:$SESSION_DIR/$SESSION_FILE" "$LOCAL_PATH" 2>>"$RUN_LOG"; then
        log "  WARN: failed to copy $SESSION_FILE, skipping"
        continue
    fi

    INCREMENTAL_ARGS="--incremental --state-file $STATE_FILE --audit-log $AUDIT_LOG"
    if $REPROCESS; then
        INCREMENTAL_ARGS=""
        log "  Reprocess mode: ignoring cursor"
    fi

    # Run analyzer, capture output
    ANALYZER_OUT=$(python3 "$ANALYZER" "$LOCAL_PATH" \
        --summary-only \
        $INCREMENTAL_ARGS \
        2>>"$RUN_LOG" || true)

    echo "$ANALYZER_OUT" >> "$RUN_LOG"

    # Parse counts from output
    NEW=$(echo "$ANALYZER_OUT" | grep -oP '\d+(?= new since)' || echo "?")
    FLAGGED=$(echo "$ANALYZER_OUT" | grep -oP '\d+(?= flagged interaction)' || echo "0")

    log "  → new=$NEW  flagged=$FLAGGED"

    [[ "$NEW" =~ ^[0-9]+$ ]] && TOTAL_NEW=$((TOTAL_NEW + NEW)) || true
    [[ "$FLAGGED" =~ ^[0-9]+$ ]] && TOTAL_FLAGGED=$((TOTAL_FLAGGED + FLAGGED)) || true

done <<< "$SESSION_FILES"

# ── Summary ───────────────────────────────────────────────────────────────────

log ""
log "=== Run complete ==="
log "  New interactions analyzed : $TOTAL_NEW"
log "  Flagged (appended)        : $TOTAL_FLAGGED"
log "  Audit log                 : $AUDIT_LOG"
log "  Run log                   : $RUN_LOG"

# Trim tmp dir (keep last 3 pulls to save space)
ls -t "$TMP_DIR"/*.jsonl 2>/dev/null | tail -n +4 | xargs rm -f || true
