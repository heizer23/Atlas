#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create folders and stub files from a component_scaffold.json file."
    )
    parser.add_argument(
        "scaffold",
        nargs="?",
        default=r"Atlas\02_Platform\Atlas_Shell\10_Design\component_scaffold.json",
        help="Path to the scaffold JSON file",
    )
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Base directory that all relative paths inside the scaffold are resolved against",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Scaffold file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def format_list(items: list[dict[str, Any]], indent: str = "") -> str:
    if not items:
        return f"{indent}- none"
    lines: list[str] = []
    for item in items:
        name = item.get("name", "<unnamed>")
        kind = item.get("kind", "object")
        purpose = item.get("purpose", "").strip()
        pattern = item.get("pattern")
        header = f"{indent}- {kind} `{name}`"
        if pattern:
            header += f" [{pattern}]"
        lines.append(header)
        if purpose:
            lines.append(f"{indent}  purpose: {purpose}")
        methods = item.get("methods", [])
        if methods:
            lines.append(f"{indent}  methods:")
            for method in methods:
                method_name = method.get("name", "<unnamed_method>")
                method_purpose = method.get("purpose", "").strip()
                lines.append(f"{indent}    - `{method_name}`")
                if method_purpose:
                    lines.append(f"{indent}      purpose: {method_purpose}")
    return "\n".join(lines)


def to_pascal_case(value: str) -> str:
    parts = value.replace("-", "_").split("_")
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def render_typescript_module(file_spec: dict[str, Any], component_name: str) -> str:
    role = file_spec.get("role", "").strip()
    public_objects = file_spec.get("public_objects", [])
    private_objects = file_spec.get("private_objects", [])
    stem = Path(file_spec["path"]).stem
    fallback_name = to_pascal_case(stem)

    lines: list[str] = [
        "/**",
        f" * File: {file_spec['path']}",
        f" * Component: {component_name}",
        " *",
        f" * Role: {role or 'Stub module'}",
        " *",
        " * Public objects:",
        *[f" * {line}" for line in format_list(public_objects, indent="").splitlines()],
        " *",
        " * Private objects:",
        *[f" * {line}" for line in format_list(private_objects, indent="").splitlines()],
        " */",
        "",
    ]

    if any(obj.get("kind") == "interface" for obj in public_objects):
        for obj in public_objects:
            if obj.get("kind") == "interface":
                lines.extend(
                    [
                        f"export interface {obj['name']} {{",
                        "  // TODO: define fields",
                        "}",
                        "",
                    ]
                )

    if any(obj.get("kind") == "type" for obj in public_objects):
        for obj in public_objects:
            if obj.get("kind") == "type":
                lines.extend(
                    [
                        f"export type {obj['name']} = unknown;",
                        "",
                    ]
                )

    exported_anything = False

    for obj in public_objects:
        kind = obj.get("kind")
        name = obj.get("name", fallback_name)

        if kind == "constant":
            lines.extend(
                [
                    f"export const {name} = undefined;",
                    "",
                ]
            )
            exported_anything = True

        elif kind == "function":
            lines.extend(
                [
                    f"export function {name}(): void {{",
                    f"  throw new Error('TODO: implement {name}');",
                    "}",
                    "",
                ]
            )
            exported_anything = True

        elif kind == "class":
            lines.extend(
                [
                    f"export function {name}() {{",
                    "  return null;",
                    "}",
                    "",
                ]
            )
            exported_anything = True

    for obj in private_objects:
        kind = obj.get("kind")
        name = obj.get("name", f"_{fallback_name}")

        if kind == "constant":
            lines.extend(
                [
                    f"const {name} = undefined;",
                    "",
                ]
            )
        elif kind == "function":
            lines.extend(
                [
                    f"function {name}(): void {{",
                    f"  throw new Error('TODO: implement {name}');",
                    "}",
                    "",
                ]
            )

    if not public_objects and not private_objects and not exported_anything:
        lines.extend(
            [
                f"export function {fallback_name}Stub(): void {{",
                "  // TODO: implement",
                "}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def render_css_module(file_spec: dict[str, Any], component_name: str) -> str:
    role = file_spec.get("role", "").strip()
    return (
        f"/*\n"
        f" * File: {file_spec['path']}\n"
        f" * Component: {component_name}\n"
        f" * Role: {role or 'CSS stub'}\n"
        f" */\n\n"
        f":root {{\n"
        f"  /* TODO: add shell tokens/hooks if needed */\n"
        f"}}\n\n"
        f"/* TODO: add styles */\n"
    )


def render_env_file(file_spec: dict[str, Any]) -> str:
    role = file_spec.get("role", "").strip()
    return (
        f"# {file_spec['path']}\n"
        f"# {role or 'Environment stub'}\n\n"
        f"VITE_TASKS_URL=\n"
    )


def render_json_config(file_spec: dict[str, Any]) -> str:
    file_name = Path(file_spec["path"]).name.lower()

    if file_name == "package.json":
        data = {
            "name": "atlas-shell",
            "private": True,
            "version": "0.0.1",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "tsc -b && vite build",
                "preview": "vite preview",
                "test": "vitest",
            },
            "dependencies": {
                "react": "^18.3.1",
                "react-dom": "^18.3.1",
                "react-router-dom": "^6.30.1",
            },
            "devDependencies": {
                "@testing-library/react": "^16.3.0",
                "@types/react": "^18.3.12",
                "@types/react-dom": "^18.3.1",
                "@vitejs/plugin-react": "^4.3.4",
                "typescript": "^5.6.3",
                "vite": "^5.4.10",
                "vitest": "^2.1.4",
            },
        }
        return json.dumps(data, indent=2) + "\n"

    if file_name == "tsconfig.json":
        data = {
            "compilerOptions": {
                "target": "ES2020",
                "useDefineForClassFields": True,
                "lib": ["ES2020", "DOM", "DOM.Iterable"],
                "module": "ESNext",
                "skipLibCheck": True,
                "moduleResolution": "Bundler",
                "allowImportingTsExtensions": False,
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": True,
                "jsx": "react-jsx",
                "strict": True,
                "baseUrl": ".",
                "paths": {
                    "@workout/*": ["../../../03_Application/WorkoutTracker/src/*"],
                    "@platform-ui/*": ["../../UI/react/src/*"],
                },
            },
            "include": ["src", "tests"],
            "references": [{"path": "./tsconfig.node.json"}],
        }
        return json.dumps(data, indent=2) + "\n"

    if file_name == "tsconfig.node.json":
        data = {
            "compilerOptions": {
                "composite": True,
                "skipLibCheck": True,
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "allowSyntheticDefaultImports": True,
            },
            "include": ["vite.config.ts"],
        }
        return json.dumps(data, indent=2) + "\n"

    data = {
        "_file": file_spec["path"],
        "_role": file_spec.get("role", ""),
        "TODO": "fill this config",
    }
    return json.dumps(data, indent=2) + "\n"


def render_html_entrypoint(file_spec: dict[str, Any]) -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Atlas</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""


def render_test_stub(file_spec: dict[str, Any], component_name: str) -> str:
    role = file_spec.get("role", "").strip()
    stem = Path(file_spec["path"]).stem
    test_name = stem.replace(".", "_")
    return (
        f"/**\n"
        f" * File: {file_spec['path']}\n"
        f" * Component: {component_name}\n"
        f" * Role: {role or 'Test stub'}\n"
        f" */\n\n"
        f"import {{ describe, it, expect }} from 'vitest';\n\n"
        f"describe('{test_name}', () => {{\n"
        f"  it('TODO: implement tests', () => {{\n"
        f"    expect(true).toBe(true);\n"
        f"  }});\n"
        f"}});\n"
    )


def render_file(file_spec: dict[str, Any], component_name: str) -> str:
    stub_kind = file_spec.get("stub_kind", "text")

    if stub_kind == "typescript_module":
        return render_typescript_module(file_spec, component_name)
    if stub_kind == "css_module":
        return render_css_module(file_spec, component_name)
    if stub_kind == "env_file":
        return render_env_file(file_spec)
    if stub_kind == "json_config":
        return render_json_config(file_spec)
    if stub_kind == "html_entrypoint":
        return render_html_entrypoint(file_spec)
    if stub_kind == "test_stub":
        return render_test_stub(file_spec, component_name)

    role = file_spec.get("role", "").strip()
    return (
        f"# File: {file_spec['path']}\n"
        f"# Component: {component_name}\n"
        f"# Role: {role or 'Generic stub'}\n"
    )


def write_file(path: Path, content: str, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        return "skipped"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "written"


def main() -> None:
    args = parse_args()

    scaffold_path = Path(args.scaffold).resolve()
    base_dir = Path(args.base_dir).resolve()

    data = load_json(scaffold_path)

    component_name = data.get("component_name", "unknown_component")
    directories = data.get("directories", [])
    files = data.get("files", [])

    print(f"[INFO] Scaffold file : {scaffold_path}")
    print(f"[INFO] Base directory : {base_dir}")
    print(f"[INFO] Component      : {component_name}")
    print()

    for directory in directories:
        dir_path = base_dir / Path(directory)
        ensure_directory(dir_path)
        print(f"[DIR ] {dir_path}")

    print()

    for file_spec in files:
        rel_path = Path(file_spec["path"])
        abs_path = base_dir / rel_path
        content = render_file(file_spec, component_name)
        result = write_file(abs_path, content, overwrite=args.overwrite)
        print(f"[FILE] {abs_path} -> {result}")


if __name__ == "__main__":
    main()