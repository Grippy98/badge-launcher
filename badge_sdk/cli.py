"""Developer commands for creating and previewing portable badge apps."""

from __future__ import annotations

import argparse
import json
import keyword
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Sequence

from badge_platform.app_manifest import load_app_entrypoint, load_manifest, validate_app_id
from badge_platform.services import MockPlatformServices
from badge_ui.application_runtime import ApplicationRuntime
from badge_ui.backends import HeadlessBackend, PygameBackend


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result or not result[0].isalnum():
        raise ValueError("app id must contain letters or numbers")
    return result


def _class_name(app_id: str) -> str:
    base = "".join(part.capitalize() for part in app_id.split("-"))
    candidate = base if base.endswith("App") else base + "App"
    if not candidate.isidentifier() or keyword.iskeyword(candidate):
        candidate = "Badge" + candidate
    if not candidate.isidentifier() or keyword.iskeyword(candidate):  # pragma: no cover
        raise ValueError(f"could not derive a Python class name from app id {app_id!r}")
    return candidate


def _module_name(app_id: str) -> str:
    candidate = app_id.replace("-", "_")
    if not candidate.isidentifier() or keyword.iskeyword(candidate):
        candidate = "badge_" + candidate
    if not candidate.isidentifier() or keyword.iskeyword(candidate):  # pragma: no cover
        raise ValueError(f"could not derive a Python module name from app id {app_id!r}")
    return candidate


def _manifest_path(value: Path) -> Path:
    if value.is_file():
        return value.resolve()
    for name in ("pyproject.toml", "badge-app.json", "app.json"):
        candidate = value / name
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"no badge app manifest in {value}")


def _load(value: Path):
    manifest_path = _manifest_path(value)
    manifest = load_manifest(manifest_path)
    if manifest.legacy:
        raise ValueError("legacy MicroPython/LVGL apps must be ported to manifest schema 2")
    return manifest, load_app_entrypoint(manifest, manifest_path.parent)


def _new(args: argparse.Namespace) -> int:
    destination = args.path.resolve()
    app_id = validate_app_id(_slug(args.app_id or destination.name))
    name = args.name or " ".join(part.capitalize() for part in app_id.split("-"))
    module = _module_name(app_id)
    app_class = _class_name(app_id)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 2,
        "id": app_id,
        "name": name,
        "version": "0.1.0",
        "category": args.category,
        "entry_point": f"{module}:{app_class}",
        "description": f"{name} for BeagleBadge",
        "requires_python": ">=3.11",
        "requires_sdk": ">=1,<2",
        "dependencies": [],
        "permissions": [],
    }
    (destination / "badge-app.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (destination / f"{module}.py").write_text(
        f'''from badge_sdk import App, Button, Column, Screen, Text\n\n\n'''
        f'''class {app_class}(App):\n'''
        f'''    def __init__(self):\n'''
        f'''        super().__init__()\n'''
        f'''        self.message = {f"Hello from {name}!"!r}\n\n'''
        f'''    def say_hello(self):\n'''
        f'''        self.message = "You pressed the button."\n'''
        f'''        self.invalidate()\n\n'''
        f'''    def view(self):\n'''
        f'''        return Screen(\n'''
        f'''            Column(\n'''
        f'''                Text(self.message, size=22, align="center", flex=1),\n'''
        f'''                Button("Say hello", self.say_hello),\n'''
        f'''                padding=12,\n'''
        f'''            ),\n'''
        f'''            title={name!r},\n'''
        f'''            footer="BACK: exit",\n'''
        f'''        )\n''',
        encoding="utf-8",
    )
    print(f"Created {name} in {destination}")
    print(f"Preview: badge-app run {destination}")
    return 0


def _exercise(path: Path, *, desktop: bool, screenshot: Path | None = None) -> int:
    manifest, app = _load(path)
    with TemporaryDirectory(prefix="badge-app-preview-") as temporary:
        services = MockPlatformServices(data_root=temporary)
        backend = PygameBackend() if desktop else HeadlessBackend(screenshot=screenshot)
        runtime = ApplicationRuntime(backend, services, data_root=temporary)
        runtime.run(app, frames=None if desktop else 1)
    print(f"{manifest.name} ({manifest.app_id}) is valid")
    if screenshot:
        print(f"Screenshot: {screenshot.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="badge-app", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("new", help="create a minimal portable app")
    create.add_argument("path", type=Path)
    create.add_argument("--id", dest="app_id")
    create.add_argument("--name")
    create.add_argument("--category", default="apps", choices=("apps", "games", "tools", "settings"))
    create.set_defaults(handler=_new)

    validate = subcommands.add_parser("validate", help="load and render an app once")
    validate.add_argument("path", type=Path)
    validate.set_defaults(handler=lambda args: _exercise(args.path, desktop=False))

    preview = subcommands.add_parser("run", help="open an app in the desktop simulator")
    preview.add_argument("path", type=Path)
    preview.set_defaults(handler=lambda args: _exercise(args.path, desktop=True))

    screenshot = subcommands.add_parser("screenshot", help="render an app to a 400x300 PNG")
    screenshot.add_argument("path", type=Path)
    screenshot.add_argument("output", type=Path)
    screenshot.set_defaults(
        handler=lambda args: _exercise(args.path, desktop=False, screenshot=args.output)
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except Exception as error:
        print(f"badge-app: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
