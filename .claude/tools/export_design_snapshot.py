from pathlib import Path
import sys
import json

OUTPUT_PATH = Path(r"C:\Users\premm\Programming\Atlas\Atlas\.claude\supportDocs\current_design.json")

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".json",
    ".jsonc",
    ".yaml",
    ".yml",
    ".env",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".sh",
    ".bat",
    ".ps1",
    ".sql",
    ".graphql",
}

TEXT_FILENAMES = {
    "Dockerfile",
    ".env",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    ".prettierrc",
    ".prettierignore",
    ".eslintrc",
    ".eslintignore",
    "Makefile",
}

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

MAX_FILE_SIZE_BYTES = 500_000  # skip very large files


def is_text_file(path: Path) -> bool:
    if path.name in TEXT_FILENAMES:
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return False


def should_ignore(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in IGNORE_DIRS for part in rel_parts)


def read_text_file(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def build_tree_summary(root: Path) -> list[str]:
    lines = []

    def walk(folder: Path, prefix: str = ""):
        children = sorted(
            [p for p in folder.iterdir() if not should_ignore(p, root)],
            key=lambda p: (p.is_file(), p.name.lower())
        )

        for i, child in enumerate(children):
            connector = "└── " if i == len(children) - 1 else "├── "
            lines.append(f"{prefix}{connector}{child.name}")

            if child.is_dir():
                extension = "    " if i == len(children) - 1 else "│   "
                walk(child, prefix + extension)

    lines.append(root.name)
    walk(root)
    return lines


def build_snapshot(root: Path) -> dict:
    snapshot = {
        "root": str(root.resolve()),
        "tree_summary": "\n".join(build_tree_summary(root)),
        "stats": {
            "included_files": 0,
            "skipped_non_text": 0,
            "skipped_ignored": 0,
            "skipped_too_large": 0,
            "read_errors": 0,
        },
        "files": {}
    }

    for file in sorted(root.rglob("*")):
        if should_ignore(file, root):
            if file.is_file():
                snapshot["stats"]["skipped_ignored"] += 1
            continue

        if not file.is_file():
            continue

        if not is_text_file(file):
            snapshot["stats"]["skipped_non_text"] += 1
            continue

        try:
            size = file.stat().st_size
        except Exception:
            size = None

        if size is not None and size > MAX_FILE_SIZE_BYTES:
            snapshot["stats"]["skipped_too_large"] += 1
            continue

        rel = str(file.relative_to(root))

        try:
            content = read_text_file(file)
        except Exception as e:
            snapshot["stats"]["read_errors"] += 1
            snapshot["files"][rel] = {
                "path": str(file),
                "relative_path": rel,
                "extension": file.suffix.lower(),
                "error": f"Could not read file as text: {e}"
            }
            continue

        snapshot["files"][rel] = {
            "path": str(file),
            "relative_path": rel,
            "extension": file.suffix.lower(),
            "size_bytes": size,
            "content": content
        }
        snapshot["stats"]["included_files"] += 1

    return snapshot


def main():
    if len(sys.argv) < 2:
        print("Usage: python export_design_snapshot.py <folder>")
        return

    source_path = Path(sys.argv[1])

    if not source_path.exists():
        raise FileNotFoundError(f"Path does not exist: {source_path}")
    if not source_path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {source_path}")

    snapshot = build_snapshot(source_path)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Snapshot written to: {OUTPUT_PATH}")
    print("Stats:")
    for key, value in snapshot["stats"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()