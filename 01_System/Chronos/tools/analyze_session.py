#!/usr/bin/env python3
"""
Chronos Session Analyzer
Analyzes openclaw session JSONL to surface token waste patterns:
- High tool-call counts per interaction
- HTTP errors and retries (404, 5xx)
- Repeated calls to the same endpoint
- Cost breakdown per interaction

Usage (ad-hoc):
  python3 analyze_session.py <session.jsonl>
  python3 analyze_session.py <session.jsonl> --verbose
  python3 analyze_session.py <session.jsonl> --min-tools 3

Usage (incremental / automated):
  python3 analyze_session.py <session.jsonl> \\
      --incremental \\
      --state-file /path/to/analysis_state.json \\
      --audit-log  /path/to/audit_log.jsonl

  --incremental   Only process interactions newer than the last run cursor.
                  Writes new flagged interactions to --audit-log.
                  Updates the cursor in --state-file after each run.

To pull current session from Chronos:
  docker cp atlas-chronos:/home/node/.openclaw/agents/main/sessions/<id>.jsonl /tmp/session.jsonl
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MIN_TOOLS = 2   # flag interactions with >= this many tool calls
WARN_TOOL_COUNT   = 5   # highlight in red above this threshold

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    name: str
    args: dict
    result_status: Optional[str] = None   # "completed", "error", "timeout"
    result_exit_code: Optional[int] = None
    result_text: Optional[str] = None     # first 300 chars
    http_status: Optional[int] = None     # extracted from result if HTTP tool

@dataclass
class Interaction:
    index: int
    timestamp: str
    user_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    model: Optional[str] = None
    has_error: bool = False
    error_summary: list[str] = field(default_factory=list)

# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_session(path: str) -> list[Interaction]:
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    messages = [e for e in events if e["type"] == "message"]

    # Build lookup: toolCallId → toolResult message
    tool_results: dict[str, dict] = {}
    for m in messages:
        msg = m["message"]
        if msg["role"] == "toolResult":
            for c in msg.get("content", []):
                pass  # content is in msg directly
            tc_id = msg.get("toolCallId")
            if tc_id:
                tool_results[tc_id] = msg

    # Group into interactions by user messages
    interactions = []
    current_user: Optional[dict] = None
    current_msgs: list[dict] = []
    idx = 0

    for m in messages:
        msg = m["message"]
        role = msg["role"]

        if role == "user":
            # Check if it's a real user message (not an injected tool result)
            has_real_text = any(
                c.get("type") == "text" and c.get("text", "").strip()
                for c in msg.get("content", [])
                if isinstance(c, dict)
            )
            if has_real_text:
                # Save previous interaction
                if current_user is not None and current_msgs:
                    interactions.append(_build_interaction(idx, current_user, current_msgs, tool_results))
                    idx += 1
                current_user = m
                current_msgs = []
                continue

        if current_user is not None:
            current_msgs.append(m)

    # Last interaction
    if current_user is not None and current_msgs:
        interactions.append(_build_interaction(idx, current_user, current_msgs, tool_results))

    return interactions


def _build_interaction(idx: int, user_event: dict, msgs: list[dict], tool_results: dict) -> Interaction:
    user_msg = user_event["message"]
    user_text = " ".join(
        c.get("text", "")
        for c in user_msg.get("content", [])
        if isinstance(c, dict) and c.get("type") == "text"
    ).strip()[:200]

    ts = user_event.get("timestamp", "")

    inter = Interaction(
        index=idx,
        timestamp=ts,
        user_text=user_text,
    )

    # Track tool call IDs to match with results
    pending_tool_calls: dict[str, ToolCall] = {}

    for m in msgs:
        msg = m["message"]
        role = msg["role"]

        # Accumulate usage/cost from assistant messages
        if role == "assistant":
            usage = msg.get("usage", {})
            cost_obj = usage.get("cost", {})
            inter.cost_usd += cost_obj.get("total", 0) or 0
            inter.input_tokens += usage.get("input", 0) or 0
            inter.output_tokens += usage.get("output", 0) or 0
            inter.cache_read_tokens += usage.get("cacheRead", 0) or 0

            # Collect tool calls
            for c in msg.get("content", []):
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "toolCall":
                    tc = ToolCall(
                        name=c.get("name", "?"),
                        args=c.get("arguments", {}),
                    )
                    tc_id = c.get("id")
                    if tc_id:
                        pending_tool_calls[tc_id] = tc
                    inter.tool_calls.append(tc)

        # Match tool results
        elif role == "toolResult":
            tc_id = msg.get("toolCallId")
            if tc_id and tc_id in pending_tool_calls:
                tc = pending_tool_calls[tc_id]
                details = msg.get("details", {})
                tc.result_status = details.get("status", "unknown")
                tc.result_exit_code = details.get("exitCode")
                result_text = " ".join(
                    c.get("text", "")
                    for c in msg.get("content", [])
                    if isinstance(c, dict) and c.get("type") == "text"
                )[:500]
                tc.result_text = result_text
                tc.http_status = _extract_http_status(result_text)

                # Flag errors
                if tc.result_exit_code not in (None, 0) or tc.result_status == "error":
                    inter.has_error = True
                    inter.error_summary.append(
                        f"{tc.name}: exit={tc.result_exit_code} status={tc.result_status}"
                    )
                if tc.http_status and tc.http_status >= 400:
                    inter.has_error = True
                    inter.error_summary.append(
                        f"{tc.name}: HTTP {tc.http_status}"
                    )

    return inter


def _extract_http_status(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'"statusCode"\s*:\s*(\d+)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'HTTP[/ ]+\d+\.\d+\s+(\d{3})', text)
    if m:
        return int(m.group(1))
    m = re.search(r'"status"\s*:\s*(\d{3})', text)
    if m:
        return int(m.group(1))
    return None


# ── Patterns ──────────────────────────────────────────────────────────────────

def detect_patterns(interaction: Interaction) -> list[str]:
    patterns = []
    tool_names = [tc.name for tc in interaction.tool_calls]

    # Repeated tool calls (same name ≥ 2 times)
    name_counts = defaultdict(int)
    for n in tool_names:
        name_counts[n] += 1
    for name, count in name_counts.items():
        if count >= 2:
            patterns.append(f"REPEATED: '{name}' called {count}x")

    # HTTP tool called multiple times (URL guessing pattern)
    http_calls = [tc for tc in interaction.tool_calls if tc.name in ("fetch", "http", "curl", "web_fetch")]
    if len(http_calls) >= 3:
        patterns.append(f"URL_CHASING: {len(http_calls)} HTTP calls in one interaction")

    # exec calls (usually reading files or running commands — check for redundancy)
    exec_calls = [tc for tc in interaction.tool_calls if tc.name == "exec"]
    if len(exec_calls) >= 4:
        patterns.append(f"EXEC_HEAVY: {len(exec_calls)} exec calls")

    # Errors followed by retry
    errors = [tc for tc in interaction.tool_calls if tc.result_exit_code not in (None, 0)]
    if errors:
        patterns.append(f"ERRORS: {len(errors)} failed tool call(s)")

    # HTTP 404 pattern (wrong URL, then retry)
    http_404s = [tc for tc in interaction.tool_calls if tc.http_status == 404]
    if http_404s:
        patterns.append(f"HTTP_404: {len(http_404s)} not-found response(s)")

    http_5xx = [tc for tc in interaction.tool_calls if tc.http_status and tc.http_status >= 500]
    if http_5xx:
        patterns.append(f"HTTP_5XX: {len(http_5xx)} server error(s)")

    return patterns


# ── Rendering ─────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

def color_cost(cost: float) -> str:
    if cost >= 0.10:
        return f"{RED}{cost:.4f}{RESET}"
    elif cost >= 0.03:
        return f"{YELLOW}{cost:.4f}{RESET}"
    else:
        return f"{GREEN}{cost:.4f}{RESET}"

def color_tool_count(n: int) -> str:
    if n >= WARN_TOOL_COUNT:
        return f"{RED}{n}{RESET}"
    elif n >= DEFAULT_MIN_TOOLS:
        return f"{YELLOW}{n}{RESET}"
    else:
        return str(n)


def fmt_tokens(n: int) -> str:
    """Format token count as e.g. 72.3K or 1.2M."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def print_interaction(inter: Interaction, verbose: bool = False):
    ts = inter.timestamp[:19].replace("T", " ") if inter.timestamp else "?"
    patterns = detect_patterns(inter)
    flag = f" {RED}⚠{RESET}" if (patterns or inter.has_error) else ""

    # Total context seen by the model = new input + cache hits
    total_ctx = inter.input_tokens + inter.cache_read_tokens

    print(f"\n{BOLD}[{inter.index:03d}] {ts}{RESET}{flag}")
    print(f"  User: {DIM}{inter.user_text[:120]}{RESET}")
    print(f"  Tools: {color_tool_count(len(inter.tool_calls))}  "
          f"Cost: ${color_cost(inter.cost_usd)}  "
          f"Ctx: {fmt_tokens(total_ctx)}  "
          f"(new {fmt_tokens(inter.input_tokens)} + cached {fmt_tokens(inter.cache_read_tokens)})  "
          f"Out: {fmt_tokens(inter.output_tokens)}")

    if patterns:
        for p in patterns:
            print(f"  {YELLOW}⚡ {p}{RESET}")

    if inter.error_summary:
        for e in inter.error_summary:
            print(f"  {RED}✗ {e}{RESET}")

    if verbose and inter.tool_calls:
        print(f"  {DIM}Tool calls:{RESET}")
        for i, tc in enumerate(inter.tool_calls):
            arg_preview = _args_preview(tc)
            status_icon = "✓" if tc.result_exit_code in (None, 0) and (not tc.http_status or tc.http_status < 400) else "✗"
            http_note = f" HTTP={tc.http_status}" if tc.http_status else ""
            print(f"    {i+1}. {status_icon} {CYAN}{tc.name}{RESET} {arg_preview}{http_note}")


def _args_preview(tc: ToolCall) -> str:
    args = tc.args
    if not args:
        return ""
    # Common patterns
    if "command" in args:
        return f"$ {str(args['command'])[:80]}"
    if "url" in args:
        return f"→ {str(args['url'])[:80]}"
    if "path" in args:
        return f"📄 {str(args['path'])[:80]}"
    # Generic
    preview = json.dumps(args)[:80]
    return f"{DIM}{preview}{RESET}"


def print_summary(interactions: list[Interaction], min_tools: int):
    total_cost  = sum(i.cost_usd for i in interactions)
    total_tools = sum(len(i.tool_calls) for i in interactions)
    total_in    = sum(i.input_tokens for i in interactions)
    total_cache = sum(i.cache_read_tokens for i in interactions)
    total_out   = sum(i.output_tokens for i in interactions)
    total_ctx   = total_in + total_cache
    flagged = [i for i in interactions if detect_patterns(i) or i.has_error]

    # Cost breakdown estimate (Haiku pricing: $0.80/MTok in, $0.30/MTok cache, $4/MTok out)
    est_in_cost    = total_in    / 1_000_000 * 0.80
    est_cache_cost = total_cache / 1_000_000 * 0.30
    est_out_cost   = total_out   / 1_000_000 * 4.00

    print(f"\n{BOLD}═══════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}SESSION SUMMARY{RESET}")
    print(f"  Interactions : {len(interactions)}")
    print(f"  Total cost   : ${total_cost:.4f}")
    print(f"  Total tools  : {total_tools}")
    print(f"  Flagged      : {len(flagged)} interaction(s) with patterns/errors")
    print()
    print(f"{BOLD}Token totals:{RESET}")
    print(f"  Context (new input) : {fmt_tokens(total_in):>8}  (~${est_in_cost:.4f} at Haiku rates)")
    print(f"  Context (cached)    : {fmt_tokens(total_cache):>8}  (~${est_cache_cost:.4f} at Haiku rates)")
    print(f"  Output              : {fmt_tokens(total_out):>8}  (~${est_out_cost:.4f} at Haiku rates)")
    print(f"  Total context seen  : {fmt_tokens(total_ctx):>8}")
    if len(interactions) > 0:
        avg_ctx = total_ctx // len(interactions)
        print(f"  Avg context/turn    : {fmt_tokens(avg_ctx):>8}")
    print()

    # Top cost interactions
    top = sorted(interactions, key=lambda i: i.cost_usd, reverse=True)[:5]
    print(f"{BOLD}Top 5 by cost:{RESET}")
    for i in top:
        ctx = i.input_tokens + i.cache_read_tokens
        print(f"  [{i.index:03d}] ${i.cost_usd:.4f}  tools={len(i.tool_calls):2d}  ctx={fmt_tokens(ctx):>6}  {i.user_text[:55]}")

    # Top token-heavy interactions
    print()
    tok_heavy = sorted(interactions, key=lambda i: i.input_tokens + i.cache_read_tokens, reverse=True)[:5]
    print(f"{BOLD}Top 5 by context size:{RESET}")
    for i in tok_heavy:
        ctx = i.input_tokens + i.cache_read_tokens
        print(f"  [{i.index:03d}] ctx={fmt_tokens(ctx):>6}  (new {fmt_tokens(i.input_tokens):>6} + cached {fmt_tokens(i.cache_read_tokens):>6})  out={fmt_tokens(i.output_tokens):>5}  ${i.cost_usd:.4f}")

    # Top tool-heavy interactions
    print()
    heavy = sorted(interactions, key=lambda i: len(i.tool_calls), reverse=True)[:5]
    print(f"{BOLD}Top 5 by tool count:{RESET}")
    for i in heavy:
        patterns = detect_patterns(i)
        p_str = f"  [{', '.join(patterns[:2])}]" if patterns else ""
        print(f"  [{i.index:03d}] {len(i.tool_calls):2d} tools  ${i.cost_usd:.4f}  ctx={fmt_tokens(i.input_tokens + i.cache_read_tokens):>6}  {i.user_text[:45]}{p_str}")

    # Errors
    errored = [i for i in interactions if i.has_error]
    if errored:
        print()
        print(f"{BOLD}Interactions with errors ({len(errored)}):{RESET}")
        for i in errored:
            print(f"  [{i.index:03d}] {'; '.join(i.error_summary[:2])}")

    print(f"{BOLD}═══════════════════════════════════════════════════{RESET}\n")


# ── State / audit log ─────────────────────────────────────────────────────────

def load_state(state_file: str) -> dict:
    p = Path(state_file)
    if p.exists():
        return json.loads(p.read_text())
    return {"last_session_id": None, "last_interaction_ts": None}


def save_state(state_file: str, session_id: str, last_ts: str):
    Path(state_file).write_text(json.dumps({
        "last_session_id": session_id,
        "last_interaction_ts": last_ts,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def append_audit_log(audit_log: str, session_id: str, interactions: list[Interaction]):
    """Append flagged interactions to the audit JSONL log."""
    p = Path(audit_log)
    with p.open("a") as f:
        for inter in interactions:
            patterns = detect_patterns(inter)
            if not (patterns or inter.has_error):
                continue
            record = {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "interaction_ts": inter.timestamp,
                "user_text": inter.user_text[:300],
                "tool_count": len(inter.tool_calls),
                "cost_usd": round(inter.cost_usd, 6),
                "input_tokens": inter.input_tokens,
                "cache_read_tokens": inter.cache_read_tokens,
                "output_tokens": inter.output_tokens,
                "patterns": patterns,
                "errors": inter.error_summary,
                "tool_calls": [
                    {
                        "name": tc.name,
                        "args_preview": _args_preview(tc).replace("\033[2m", "").replace("\033[0m", ""),
                        "http_status": tc.http_status,
                        "exit_code": tc.result_exit_code,
                        "result_status": tc.result_status,
                    }
                    for tc in inter.tool_calls
                ],
                "reviewed": False,
            }
            f.write(json.dumps(record) + "\n")


def extract_session_id(session_path: str) -> str:
    """Extract the base session UUID from the filename."""
    name = Path(session_path).name
    # e.g. 531cfad2-....checkpoint.....jsonl → 531cfad2-...
    return name.split(".")[0]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chronos session analyzer")
    parser.add_argument("session", help="Path to session .jsonl file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show individual tool calls")
    parser.add_argument("--min-tools", type=int, default=DEFAULT_MIN_TOOLS,
                        help=f"Only show interactions with >= N tool calls (default {DEFAULT_MIN_TOOLS})")
    parser.add_argument("--all", action="store_true", help="Show all interactions, not just flagged ones")
    parser.add_argument("--summary-only", action="store_true", help="Only print summary, no per-interaction output")
    # Incremental mode
    parser.add_argument("--incremental", action="store_true",
                        help="Only process interactions newer than last run cursor")
    parser.add_argument("--state-file", default=None,
                        help="Path to state JSON file (cursor tracking). Required with --incremental.")
    parser.add_argument("--audit-log", default=None,
                        help="Path to audit JSONL log. Flagged interactions are appended here.")
    args = parser.parse_args()

    interactions = parse_session(args.session)
    session_id = extract_session_id(args.session)

    # ── Incremental filtering ──────────────────────────────────────────────────
    if args.incremental:
        if not args.state_file:
            print("ERROR: --incremental requires --state-file", file=sys.stderr)
            sys.exit(1)
        state = load_state(args.state_file)
        last_ts = state.get("last_interaction_ts")

        if last_ts:
            before = len(interactions)
            interactions = [i for i in interactions if i.timestamp > last_ts]
            print(f"Incremental: {before} total interactions, {len(interactions)} new since {last_ts[:19]}")
        else:
            print(f"Incremental: first run, processing all {len(interactions)} interactions")

    # ── Display ────────────────────────────────────────────────────────────────
    if not args.summary_only:
        for inter in interactions:
            n_tools = len(inter.tool_calls)
            patterns = detect_patterns(inter)
            if args.all or n_tools >= args.min_tools or patterns or inter.has_error:
                print_interaction(inter, verbose=args.verbose)

    if interactions:
        print_summary(interactions, args.min_tools)
    else:
        print("No new interactions to analyze.")

    # ── Persist ────────────────────────────────────────────────────────────────
    if interactions and args.audit_log:
        append_audit_log(args.audit_log, session_id, interactions)
        flagged_count = sum(1 for i in interactions if detect_patterns(i) or i.has_error)
        print(f"Audit log: appended {flagged_count} flagged interaction(s) → {args.audit_log}")

    if interactions and args.incremental and args.state_file:
        last_ts = max(i.timestamp for i in interactions if i.timestamp)
        save_state(args.state_file, session_id, last_ts)
        print(f"State: cursor updated to {last_ts[:19]} → {args.state_file}")


if __name__ == "__main__":
    main()
