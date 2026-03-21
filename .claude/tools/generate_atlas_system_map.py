#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LAYER_PREFIXES = (
    "00_Blueprint",
    "01_System",
    "02_Platform",
    "03_Application",
)

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css", ".scss",
    ".html", ".sql", ".sh", ".ps1", ".env", ".dockerfile",
}

IGNORE_DIRS = {
    ".git", ".idea", ".vscode", ".venv", "venv", "node_modules", "dist", "build",
    ".next", ".nuxt", "coverage", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".turbo", ".cache", ".claude",
}

NODE_BUILTINS = {
    "assert", "buffer", "child_process", "crypto", "events", "fs", "http", "https", "net",
    "os", "path", "stream", "timers", "tls", "tty", "url", "util", "zlib", "process",
}

PY_BUILTINS = {
    "abc", "argparse", "asyncio", "collections", "contextlib", "csv", "dataclasses",
    "datetime", "functools", "glob", "hashlib", "importlib", "io", "itertools", "json",
    "logging", "math", "os", "pathlib", "queue", "random", "re", "shutil", "sqlite3",
    "statistics", "subprocess", "sys", "tempfile", "threading", "time", "typing", "uuid",
    "unittest", "urllib", "xml", "zipfile",
}

IMPORT_RE_TS = re.compile(
    r"(?:import\s+(?:type\s+)?(?:[^\n;]+?\s+from\s+)?|export\s+[^\n;]+?\s+from\s+|require\s*\()"
    r"[\"']([^\"']+)[\"']"
)
IMPORT_RE_PY = re.compile(r"^(?:from\s+([\w\.]+)\s+import|import\s+([\w\.,\s]+))", re.MULTILINE)
PATH_REF_RE = re.compile(r"(?:^|[\s\"'`(])((?:00_Blueprint|01_System|02_Platform|03_Application)[/\\][^\s\"'`:)]+)")


@dataclass
class Component:
    name: str
    layer: str
    path: str
    atlas_dependencies: list[str]
    external_libraries: list[str]
    internal_aliases: list[str]
    detected_entry_files: list[str]


def is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name.lower() in {"dockerfile", "package.json", "pyproject.toml", "requirements.txt"}


def iter_files(root: Path, max_bytes: int) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        base = Path(dirpath)

        for filename in filenames:
            p = base / filename
            try:
                if not p.is_file():
                    continue
                if p.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue

            if is_text_candidate(p):
                yield p


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return ""
    except Exception:
        return ""


def discover_components(repo_root: Path) -> list[tuple[Path, str]]:
    components: list[tuple[Path, str]] = []

    for layer_name in LAYER_PREFIXES:
        layer_path = repo_root / layer_name
        if not layer_path.is_dir():
            continue

        for child in sorted(layer_path.iterdir()):
            if child.is_dir() and child.name not in IGNORE_DIRS:
                components.append((child, layer_name))

    return components


def relative_posix(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def load_declared_node_libs(component_root: Path) -> set[str]:
    libs: set[str] = set()

    for pkg in component_root.rglob("package.json"):
        if any(part in IGNORE_DIRS for part in pkg.parts):
            continue

        data = safe_read(pkg)
        if not data:
            continue

        try:
            obj = json.loads(data)
        except Exception:
            continue

        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps = obj.get(section, {})
            if isinstance(deps, dict):
                libs.update(str(k) for k in deps.keys())

    return libs


def load_declared_python_libs(component_root: Path) -> set[str]:
    libs: set[str] = set()

    pyproject = component_root / "pyproject.toml"
    if pyproject.exists():
        text = safe_read(pyproject)
        for match in re.findall(r'"([A-Za-z0-9_.\-]+)(?:[<>=~!].*?)?"', text):
            if match.lower() not in {"python"}:
                libs.add(match.split("[")[0])

    requirements = component_root / "requirements.txt"
    if requirements.exists():
        for line in safe_read(requirements).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = re.split(r"[<>=~!\[]", line, maxsplit=1)[0].strip()
            if name:
                libs.add(name)

    return libs


def extract_imports_from_text(text: str) -> tuple[set[str], set[str], set[str]]:
    external: set[str] = set()
    internal_aliases: set[str] = set()
    raw_imports: set[str] = set()

    for match in IMPORT_RE_TS.findall(text):
        raw_imports.add(match)

    for m1, m2 in IMPORT_RE_PY.findall(text):
        if m1:
            raw_imports.add(m1)
        if m2:
            for part in m2.split(","):
                cleaned = part.strip()
                if cleaned:
                    raw_imports.add(cleaned)

    for imp in raw_imports:
        if not imp or imp.startswith((".", "/")):
            continue

        if imp.startswith("@atlas/"):
            internal_aliases.add(imp)
            continue

        root = imp.split("/")[0]
        if root.startswith("@") and "/" in imp:
            root = "/".join(imp.split("/")[:2])

        if root in NODE_BUILTINS or root in PY_BUILTINS:
            continue

        if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", imp) and "." in imp:
            py_root = imp.split(".")[0]
            if py_root in PY_BUILTINS:
                continue
            external.add(py_root)
        else:
            external.add(root)

    return external, internal_aliases, raw_imports


def detect_entry_files(component_root: Path, repo_root: Path) -> list[str]:
    candidates: list[str] = []
    preferred_names = {
        "readme.md", "claude.md", "docker-compose.yml", "docker-compose.yaml",
        "compose.yml", "compose.yaml", "package.json", "pyproject.toml",
        "requirements.txt", "main.py", "app.py", "index.ts", "index.tsx",
        "router.tsx",
    }

    for path in component_root.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue

        if path.name.lower() in preferred_names:
            candidates.append(relative_posix(path, repo_root))

    return sorted(candidates)[:20]


def build_map(repo_root: Path, max_bytes_per_file: int) -> dict:
    components = discover_components(repo_root)
    component_paths = {relative_posix(path, repo_root): (path, layer) for path, layer in components}

    result_components: list[Component] = []

    for component_root, layer in components:
        component_rel_path = relative_posix(component_root, repo_root)
        text_blob_parts: list[str] = []
        external_libs: set[str] = set()
        internal_aliases: set[str] = set()

        external_libs.update(load_declared_node_libs(component_root))
        external_libs.update(load_declared_python_libs(component_root))

        for file_path in iter_files(component_root, max_bytes_per_file):
            text = safe_read(file_path)
            if not text:
                continue

            text_blob_parts.append(text)
            libs, aliases, _raw = extract_imports_from_text(text)
            external_libs.update(libs)
            internal_aliases.update(aliases)

        blob = "\n".join(text_blob_parts)

        atlas_dependencies: set[str] = set()

        for rel_path in component_paths:
            if rel_path == component_rel_path:
                continue

            rel_path_backslash = rel_path.replace("/", "\\")
            if rel_path in blob or rel_path_backslash in blob:
                atlas_dependencies.add(rel_path)

        for path_ref in PATH_REF_RE.findall(blob):
            normalized = path_ref.replace("\\", "/")
            parts = normalized.split("/")
            if len(parts) >= 2:
                candidate = "/".join(parts[:2])
                if candidate in component_paths and candidate != component_rel_path:
                    atlas_dependencies.add(candidate)

        result_components.append(
            Component(
                name=component_root.name,
                layer=layer,
                path=component_rel_path,
                atlas_dependencies=sorted(atlas_dependencies),
                external_libraries=sorted(external_libs),
                internal_aliases=sorted(internal_aliases),
                detected_entry_files=detect_entry_files(component_root, repo_root),
            )
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(repo_root),
        "component_count": len(result_components),
        "components": [asdict(c) for c in sorted(result_components, key=lambda x: x.path)],
    }


def main() -> None:
    default_repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(
        description="Generate a compact ATLAS system map JSON."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=str(default_repo_root),
        help="Atlas repository root (defaults to repo root inferred from script location)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: <repo_root>/.claude/supportDocs/atlas_system_map.generated.json)",
    )
    parser.add_argument(
        "--max-bytes-per-file",
        type=int,
        default=250_000,
        help="Skip text files larger than this many bytes when scanning (default: 250000)",
    )

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = repo_root / ".claude" / "supportDocs" / "atlas_system_map.generated.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    system_map = build_map(repo_root, args.max_bytes_per_file)

    output_path.write_text(
        json.dumps(system_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote system map: {output_path}")
    print(f"Components: {system_map['component_count']}")


if __name__ == "__main__":
    main()