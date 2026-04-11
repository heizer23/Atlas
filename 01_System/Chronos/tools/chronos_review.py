#!/usr/bin/env python3
"""
Chronos Audit Log Reviewer
Reads the audit_log.jsonl and groups unreviewed flagged interactions
by pattern type, ready for a Claude Code review session.

Usage:
  python3 chronos_review.py                         # show unreviewed items
  python3 chronos_review.py --all                   # include already-reviewed items
  python3 chronos_review.py --mark-reviewed <ts>    # mark interaction as reviewed by timestamp
  python3 chronos_review.py --mark-all-reviewed     # mark everything currently shown as reviewed
  python3 chronos_review.py --pattern URL_CHASING   # filter to one pattern type
  python3 chronos_review.py --since 2026-04-09      # only interactions from this date onward

The audit log is at: 01_System/Chronos/tools/data/audit_log.jsonl
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
DEFAULT_AUDIT_LOG = SCRIPT_DIR / "data" / "audit_log.jsonl"

# ── ANSI ──────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

# ── Load ──────────────────────────────────────────────────────────────────────

def load_records(audit_log: Path, include_reviewed: bool = False,
                 pattern_filter: Optional[str] = None,
                 since: Optional[str] = None) -> list[dict]:
    if not audit_log.exists():
        print(f"Audit log not found: {audit_log}")
        print("Run chronos_audit_run.sh first to populate it.")
        sys.exit(1)

    records = []
    with audit_log.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not include_reviewed and r.get("reviewed"):
                continue
            if pattern_filter and not any(pattern_filter in p for p in r.get("patterns", [])):
                continue
            if since and r.get("interaction_ts", "") < since:
                continue
            records.append(r)

    return records


# ── Grouping ──────────────────────────────────────────────────────────────────

PATTERN_LABELS = {
    "URL_CHASING":  ("URL chasing — agent tried multiple HTTP endpoints", RED),
    "HTTP_404":     ("HTTP 404 — wrong URL on first attempt", RED),
    "HTTP_5XX":     ("HTTP 5xx — server errors", RED),
    "REPEATED":     ("Repeated tool calls — same tool called multiple times", YELLOW),
    "EXEC_HEAVY":   ("Exec-heavy — many shell calls, may indicate missing context", YELLOW),
    "ERRORS":       ("Tool errors — non-zero exit or error status", YELLOW),
}

def group_by_pattern(records: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        for p in r.get("patterns", []):
            # Normalize to pattern key (prefix before colon)
            key = p.split(":")[0].strip()
            groups[key].append(r)
        if r.get("errors") and not r.get("patterns"):
            groups["ERRORS"].append(r)
    return groups


# ── Rendering ─────────────────────────────────────────────────────────────────

def fmt_ts(ts: str) -> str:
    return ts[:19].replace("T", " ") if ts else "?"

def print_record(r: dict, idx: int):
    ts = fmt_ts(r.get("interaction_ts", ""))
    cost = r.get("cost_usd", 0)
    tools = r.get("tool_count", 0)
    ctx = r.get("input_tokens", 0) + r.get("cache_read_tokens", 0)
    ctx_k = f"{ctx/1000:.1f}K"

    cost_color = RED if cost >= 0.10 else (YELLOW if cost >= 0.03 else GREEN)
    reviewed_tag = f" {DIM}[reviewed]{RESET}" if r.get("reviewed") else ""

    print(f"  {BOLD}#{idx}{RESET}  {ts}  ${cost_color}{cost:.4f}{RESET}  tools={tools}  ctx={ctx_k}{reviewed_tag}")
    print(f"      {DIM}{r.get('user_text', '')[:120]}{RESET}")

    for p in r.get("patterns", []):
        print(f"      {YELLOW}⚡ {p}{RESET}")
    for e in r.get("errors", []):
        print(f"      {RED}✗ {e}{RESET}")

    # Tool call sequence
    calls = r.get("tool_calls", [])
    if calls:
        steps = []
        for tc in calls:
            icon = "✗" if (tc.get("exit_code") not in (None, 0)) or (tc.get("http_status") and tc["http_status"] >= 400) else "✓"
            http = f" HTTP={tc['http_status']}" if tc.get("http_status") else ""
            steps.append(f"{icon}{tc['name']}{http}")
        print(f"      {DIM}calls: {' → '.join(steps)}{RESET}")
    print()


def print_review(records: list[dict], groups: dict[str, list[dict]]):
    total_cost = sum(r.get("cost_usd", 0) for r in records)

    print(f"\n{BOLD}═══════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}CHRONOS AUDIT REVIEW{RESET}")
    print(f"  Unreviewed flagged interactions : {len(records)}")
    print(f"  Total cost of flagged set       : ${total_cost:.4f}")
    print(f"{BOLD}═══════════════════════════════════════════════════{RESET}\n")

    if not records:
        print(f"{GREEN}Nothing to review — audit log is clean.{RESET}\n")
        return

    # Per-pattern groups
    for key, color in [(k, PATTERN_LABELS.get(k, (k, YELLOW))[1]) for k in PATTERN_LABELS]:
        group = groups.get(key, [])
        if not group:
            continue
        label, _ = PATTERN_LABELS.get(key, (key, YELLOW))
        print(f"{BOLD}{color}── {key} ({len(group)} interaction(s)){RESET}")
        print(f"   {DIM}{label}{RESET}")
        print()
        for idx, r in enumerate(group, 1):
            print_record(r, idx)

    # Any groups not in the known pattern list
    for key, group in groups.items():
        if key not in PATTERN_LABELS:
            print(f"{BOLD}{YELLOW}── {key} ({len(group)} interaction(s)){RESET}\n")
            for idx, r in enumerate(group, 1):
                print_record(r, idx)

    print(f"{BOLD}Suggested next steps:{RESET}")
    if "URL_CHASING" in groups or "HTTP_404" in groups:
        print(f"  • Check skill SKILL.md descriptions — add base URL and 'read before every call' instruction")
    if "EXEC_HEAVY" in groups or "REPEATED" in groups:
        print(f"  • Review skill bodies — agent may be exploring due to missing context in description")
    if "ERRORS" in groups:
        print(f"  • Check tool commands in skills — non-zero exits may indicate wrong syntax or missing binaries")
    print()
    print(f"To mark all shown items as reviewed after fixing:")
    print(f"  python3 {Path(__file__).name} --mark-all-reviewed\n")


# ── Mutation ──────────────────────────────────────────────────────────────────

def rewrite_log(audit_log: Path, predicate, field: str, value):
    """Rewrite the JSONL, setting field=value on records matching predicate."""
    lines = audit_log.read_text().splitlines()
    updated = 0
    new_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if predicate(r):
            r[field] = value
            updated += 1
        new_lines.append(json.dumps(r))
    audit_log.write_text("\n".join(new_lines) + "\n")
    return updated


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chronos audit log reviewer")
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG), help="Path to audit_log.jsonl")
    parser.add_argument("--all", action="store_true", help="Include already-reviewed items")
    parser.add_argument("--pattern", help="Filter to one pattern type (e.g. URL_CHASING)")
    parser.add_argument("--since", help="Only show interactions from this date onward (YYYY-MM-DD)")
    parser.add_argument("--mark-reviewed", metavar="TS",
                        help="Mark interaction with this timestamp prefix as reviewed")
    parser.add_argument("--mark-all-reviewed", action="store_true",
                        help="Mark all currently shown interactions as reviewed")
    args = parser.parse_args()

    audit_log = Path(args.audit_log)

    # ── Mutation modes ─────────────────────────────────────────────────────────
    if args.mark_reviewed:
        ts_prefix = args.mark_reviewed
        n = rewrite_log(audit_log,
                        lambda r: r.get("interaction_ts", "").startswith(ts_prefix),
                        "reviewed", True)
        print(f"Marked {n} record(s) as reviewed (ts prefix: {ts_prefix})")
        return

    # ── Load and display ───────────────────────────────────────────────────────
    records = load_records(
        audit_log,
        include_reviewed=args.all,
        pattern_filter=args.pattern,
        since=args.since,
    )
    groups = group_by_pattern(records)
    print_review(records, groups)

    if args.mark_all_reviewed:
        shown_ts = {r["interaction_ts"] for r in records}
        n = rewrite_log(audit_log,
                        lambda r: r.get("interaction_ts") in shown_ts,
                        "reviewed", True)
        print(f"Marked {n} interaction(s) as reviewed.")


if __name__ == "__main__":
    main()
