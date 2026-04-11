#!/usr/bin/env python3
"""
generate_atlas_dev_ref.py

Generates .claude/supportDocs/atlas_dev_ref.md from:
  - <layer>/<component>/00_architecture/architecture.json  (design truth)
  - <layer>/<component>/compose.yml                        (operational detail)

Run from the Atlas repo root:
    python3 .claude/tools/generate_atlas_dev_ref.py

Replaces the old generate_atlas_system_map.py + PLATFORM_SERVICES.md.
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_FILE  = REPO_ROOT / ".claude" / "supportDocs" / "atlas_dev_ref.md"

LAYER_ORDER = ["01_System", "02_Platform", "03_Application"]

# Components intentionally excluded (no HTTP API, no caller-facing contract,
# or not a deployable service component)
EXCLUDE = {
    "packages", "Postgres",           # 02_Platform infrastructure
    "Access", "AtlasPhone",           # 01_System non-service directories
    "AuditRuns", "SystemMonitoring",  # 01_System tooling/monitoring
    ".claude",                         # tooling root
}

# Manual stubs for components without 00_architecture/ yet.
# Keys match the directory name. Fill these in as sprints backfill 00_architecture.
STUBS = {
    "Atlas_Shell": {
        "summary": "Nginx-served SPA. Renders Atlas applications via ShellEntry.tsx modules. Not called by other services.",
        "container": "atlas-shell",
        "host_port": "80",
        "url_prefix": None,
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["UI runtime only — application backends do not call it."],
    },
    "CalendarConnector": {
        "summary": "Google Calendar read/write adapter. Handles OAuth, token management, event sync.",
        "container": "atlas-calendar-connector",
        "host_port": "${CALENDAR_CONNECTOR_PORT:-8021}",
        "url_prefix": "/api/calendar",
        "network": "atlas-net",
        "endpoints": [
            "GET  /api/calendar/events — Dataset of calendar events",
            "GET  /api/calendar/status — Dataset of connection health",
            "GET  /api/calendar/google/connect/start — initiate OAuth",
            "GET  /api/calendar/google/connect/callback — OAuth callback",
            "POST /api/calendar/events — idempotent create event",
            "PATCH /api/calendar/events/{atlas_event_id} — update event",
            "DELETE /api/calendar/events/{atlas_event_id} — delete event",
        ],
        "caller_notes": [
            "Write target calendar set via CALENDAR_TARGET_CALENDAR_ID env var.",
            "atlas_event_id is the stable cross-system key — supply on create.",
            "Token values are never included in responses.",
        ],
    },
    "LinkingEngine": {
        "summary": "Generic cross-object relationship store. Any two registered objects can be linked with a named relation.",
        "container": "atlas-linking-engine",
        "host_port": "8040",
        "url_prefix": "/linking",
        "network": "atlas-net",
        "endpoints": [
            "POST   /linking/objects — register or update an object",
            "GET    /linking/objects/search — fuzzy search by type and q",
            "POST   /linking/links — create a link between two objects",
            "DELETE /linking/links/{link_id} — soft-delete a link",
            "GET    /linking/links — raw link query",
            "GET    /linking/objects/{object_id}/links — grouped links for an object",
        ],
        "caller_notes": [
            "Objects must be registered before linking.",
            "GET /linking/objects/{id}/links returns grouped shape — not a Dataset. Backends must transform before serving the UI.",
            "Deletion is soft (archived_at). No hard-delete endpoint.",
        ],
    },
    "MCPGateway": {
        "summary": "MCP protocol gateway exposing Atlas tools to external AI clients (e.g. ChatGPT). Not consumed by Atlas applications.",
        "container": "atlas-mcp-server",
        "host_port": "8002",
        "url_prefix": None,
        "network": "host (network_mode: host)",
        "endpoints": [],
        "caller_notes": [
            "Not for inter-application calls within Atlas.",
            "Uses host network mode — reaches Postgres and other services via 127.0.0.1.",
        ],
    },
    "Notifications": {
        "summary": "Push notification scheduling and FCM dispatch. Application backends enqueue notifications here.",
        "container": "atlas-notifications",
        "host_port": "8020",
        "url_prefix": "/api/notifications",
        "network": "0.0.0.0 (LAN-accessible via Tailscale for Android)",
        "endpoints": [
            "POST   /api/notifications/ — enqueue a notification",
            "DELETE /api/notifications/{id} — cancel a pending notification",
            "POST   /api/notifications/{id}/replace — cancel + recreate atomically (best-effort)",
            "POST   /api/devices/token — register or update FCM token",
            "GET    /api/devices/token — retrieve current FCM token",
        ],
        "caller_notes": [
            "Notifications are enqueued, not dispatched synchronously (default 30s interval).",
            "replace is not atomic — old cancelled first, then new created.",
            "device_id = 'default' is the single-device MVP convention.",
        ],
    },
    "Chronicle": {
        "summary": "Append-only log / journal application. Stores timestamped entries.",
        "container": "atlas-chronicle",
        "host_port": "8013",
        "url_prefix": "/api",
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["No 00_architecture yet — stub only."],
    },
    "FoodTracker": {
        "summary": "Food and nutrition tracking application.",
        "container": "atlas-food-tracker",
        "host_port": "8012",
        "url_prefix": "/api",
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["No 00_architecture yet — stub only."],
    },
    "NumericSeries": {
        "summary": "Generic numeric time-series tracking application.",
        "container": "atlas-numeric-series",
        "host_port": "8014",
        "url_prefix": "/api",
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["No 00_architecture yet — stub only."],
    },
    "WorkoutTracker": {
        "summary": "Workout and exercise tracking application.",
        "container": "atlas-workout-tracker",
        "host_port": "8011",
        "url_prefix": "/api",
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["No 00_architecture yet — stub only."],
    },
    "Chronos": {
        "summary": "System-level AI gateway (01_System). Handles Telegram, task orchestration, and AI agent dispatch. Not a platform capability consumed by applications.",
        "container": "atlas-chronos",
        "host_port": None,
        "url_prefix": None,
        "network": "atlas-net",
        "endpoints": [],
        "caller_notes": ["Claude Code does not call Chronos. Separate agent world."],
    },
}


def parse_compose(compose_path: Path) -> dict:
    """Extract container_name and first port mapping from compose.yml."""
    result = {"container": None, "host_port": None, "network": "atlas-net"}
    if not compose_path.exists():
        return result
    text = compose_path.read_text()

    m = re.search(r"container_name:\s*(\S+)", text)
    if m:
        result["container"] = m.group(1)

    # host network mode
    if "network_mode: host" in text:
        result["network"] = "host (network_mode: host)"
        return result

    # 0.0.0.0 binding
    m = re.search(r'"(0\.0\.0\.0):(\d+):\d+"', text)
    if m:
        result["host_port"] = m.group(2)
        result["network"] = "0.0.0.0 (LAN-accessible)"
        return result

    # 127.0.0.1 binding
    m = re.search(r'"127\.0\.0\.1:(\S+):\d+"', text)
    if m:
        result["host_port"] = m.group(1)  # may be a var like ${PORT:-8021}

    return result


def parse_architecture(arch_path: Path) -> dict:
    """Extract summary, endpoints, and caller notes from architecture.json."""
    result = {"summary": None, "endpoints": [], "caller_notes": [], "url_prefix": "/api"}
    if not arch_path.exists():
        return result

    try:
        data = json.loads(arch_path.read_text())
    except Exception:
        return result

    result["summary"] = data.get("summary", "")

    # Extract provides (endpoints)
    contracts = data.get("contracts", {})
    provides = contracts.get("provides", [])
    for p in provides:
        if any(m in p for m in ["GET ", "POST ", "PUT ", "PATCH ", "DELETE ", "HTTP API"]):
            result["endpoints"].append(p.replace("HTTP API: ", ""))

    # Extract invariants as caller notes (concise)
    # Also pull caller_notes if explicitly present
    explicit_notes = data.get("caller_notes", [])
    if explicit_notes:
        result["caller_notes"] = explicit_notes

    return result


def collect_components() -> list[dict]:
    """Walk layer dirs and collect component info."""
    components = []

    for layer in LAYER_ORDER:
        layer_path = REPO_ROOT / layer
        if not layer_path.exists():
            continue

        for comp_dir in sorted(layer_path.iterdir()):
            if not comp_dir.is_dir():
                continue
            name = comp_dir.name
            if name in EXCLUDE:
                continue

            arch_path    = comp_dir / "00_architecture" / "architecture.json"
            compose_path = comp_dir / "compose.yml"

            has_arch = arch_path.exists()

            if has_arch:
                arch    = parse_architecture(arch_path)
                compose = parse_compose(compose_path)
                entry = {
                    "name":         name,
                    "layer":        layer,
                    "has_arch":     True,
                    "summary":      arch["summary"],
                    "container":    compose["container"],
                    "host_port":    compose["host_port"],
                    "network":      compose["network"],
                    "url_prefix":   arch.get("url_prefix", "/api"),
                    "endpoints":    arch["endpoints"],
                    "caller_notes": arch["caller_notes"],
                }
            elif name in STUBS:
                stub = STUBS[name]
                entry = {
                    "name":         name,
                    "layer":        layer,
                    "has_arch":     False,
                    "summary":      stub["summary"],
                    "container":    stub["container"],
                    "host_port":    stub["host_port"],
                    "network":      stub.get("network", "atlas-net"),
                    "url_prefix":   stub.get("url_prefix"),
                    "endpoints":    stub.get("endpoints", []),
                    "caller_notes": stub.get("caller_notes", []),
                }
            else:
                # Unknown component — minimal stub
                compose = parse_compose(compose_path)
                entry = {
                    "name":         name,
                    "layer":        layer,
                    "has_arch":     False,
                    "summary":      f"No 00_architecture yet.",
                    "container":    compose.get("container"),
                    "host_port":    compose.get("host_port"),
                    "network":      compose.get("network", "atlas-net"),
                    "url_prefix":   None,
                    "endpoints":    [],
                    "caller_notes": ["Stub — no architecture.json available."],
                }

            components.append(entry)

    return components


def render(components: list[dict]) -> str:
    lines = []
    lines.append("# Atlas Developer Reference")
    lines.append("")
    lines.append("> **Generated** — do not edit manually.")
    lines.append(f"> Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"> Source: `00_architecture/architecture.json` + `compose.yml` per component.")
    lines.append(f"> Regenerated automatically by `/sprint-close`.")
    lines.append("")
    lines.append("This is the primary development reference for Claude Code. Use it to find:")
    lines.append("- How to reach any service (host port, container name, URL prefix)")
    lines.append("- What endpoints each component exposes")
    lines.append("- Caller contracts and gotchas")
    lines.append("")
    lines.append("Components marked ⚠️ have no `00_architecture/` yet — entries are stubs.")
    lines.append("")

    current_layer = None
    for comp in components:
        if comp["layer"] != current_layer:
            current_layer = comp["layer"]
            layer_label = {
                "01_System":      "01 System",
                "02_Platform":    "02 Platform",
                "03_Application": "03 Application",
            }.get(current_layer, current_layer)
            lines.append(f"---")
            lines.append(f"")
            lines.append(f"## {layer_label}")
            lines.append("")

        stub_flag = " ⚠️" if not comp["has_arch"] else ""
        lines.append(f"### {comp['name']}{stub_flag}")
        lines.append("")
        lines.append(f"**Summary:** {comp['summary']}")
        lines.append("")

        # Operational details table
        port_str = f"`localhost:{comp['host_port']}`" if comp["host_port"] else "—"
        container_str = f"`{comp['container']}`" if comp["container"] else "—"
        prefix_str = f"`{comp['url_prefix']}`" if comp["url_prefix"] else "—"
        lines.append(f"| | |")
        lines.append(f"|---|---|")
        lines.append(f"| Container | {container_str} |")
        lines.append(f"| Host port | {port_str} |")
        lines.append(f"| Network | {comp['network']} |")
        lines.append(f"| URL prefix | {prefix_str} |")
        lines.append("")

        if comp["endpoints"]:
            lines.append("**Endpoints:**")
            lines.append("```")
            for ep in comp["endpoints"]:
                lines.append(ep)
            lines.append("```")
            lines.append("")

        if comp["caller_notes"]:
            lines.append("**Caller notes:**")
            for note in comp["caller_notes"]:
                lines.append(f"- {note}")
            lines.append("")

    return "\n".join(lines)


def main():
    components = collect_components()
    md = render(components)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(md)
    print(f"Wrote {OUT_FILE}")
    print(f"Components: {len(components)} ({sum(1 for c in components if c['has_arch'])} with 00_architecture, {sum(1 for c in components if not c['has_arch'])} stubs)")


if __name__ == "__main__":
    main()
