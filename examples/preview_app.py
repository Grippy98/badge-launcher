#!/usr/bin/env python3
"""Preview one schema-v2 app without installing it."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

# Keep the helper runnable directly from a source checkout. Installed apps do
# not need or use this path adjustment.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from badge_platform.app_manifest import load_app_entrypoint, load_manifest
from badge_platform.services import MockPlatformServices
from badge_ui import ApplicationRuntime
from badge_ui.backends import HeadlessBackend, PygameBackend


def find_manifest(app_root: Path) -> Path:
    for name in ("pyproject.toml", "badge-app.json", "app.json"):
        candidate = app_root / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no schema-v2 manifest found in {app_root}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path, help="directory containing the app manifest")
    parser.add_argument("--screenshot", type=Path, help="render one headless frame to this path")
    args = parser.parse_args()

    app_root = args.app.expanduser().resolve()
    manifest = load_manifest(find_manifest(app_root))
    app = load_app_entrypoint(manifest, app_root)

    with TemporaryDirectory(prefix=f"badge-preview-{manifest.app_id}-") as data_dir:
        services = MockPlatformServices(data_root=data_dir)
        backend = (
            HeadlessBackend(screenshot=args.screenshot)
            if args.screenshot
            else PygameBackend()
        )
        runtime = ApplicationRuntime(backend, services, data_root=data_dir)
        runtime.run(app, frames=1 if args.screenshot else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
