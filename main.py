#!/usr/bin/env python3
"""Standard-CPython entry point for the experimental BeagleBadge launcher."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from badge_platform.app_store import AppStore
from badge_platform.services import PlatformServices
from badge_platform.tty import ConsoleSession
from badge_ui import ApplicationRuntime
from badge_ui.backends import FramebufferBackend, HeadlessBackend, PygameBackend
from builtin_apps.catalog import builtin_entries
from builtin_apps.system import ArmbianOnboardingApp, LauncherApp


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="badge-launcher",
        description="Portable CPython launcher for the BeagleBadge",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "framebuffer", "desktop", "headless"),
        default=os.environ.get("BADGE_BACKEND", "auto"),
        help="display backend (default: auto)",
    )
    parser.add_argument(
        "--framebuffer",
        default=os.environ.get("BADGE_FRAMEBUFFER", "/dev/fb0"),
        help="Linux framebuffer device",
    )
    parser.add_argument("--width", type=int, default=None, help="override detected width")
    parser.add_argument("--height", type=int, default=None, help="override detected height")
    parser.add_argument("--scale", type=int, default=2, help="desktop simulator scale")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="persistent launcher state (or BADGE_DATA_DIR)",
    )
    parser.add_argument("--frames", type=int, default=None, help="stop after N loop iterations")
    parser.add_argument("--screenshot", type=Path, default=None, help="save the last headless frame")
    parser.add_argument(
        "--no-hardware",
        action="store_true",
        help="do not open evdev, serial, LEDs, or sound devices",
    )
    parser.add_argument(
        "--skip-onboarding",
        action="store_true",
        help="skip Armbian first-login detection (development only)",
    )
    return parser


def _backend_name(requested: str, framebuffer: str, screenshot: Path | None) -> str:
    if requested != "auto":
        return requested
    if screenshot is not None:
        return "headless"
    if sys.platform.startswith("linux") and Path(framebuffer).exists():
        return "framebuffer"
    if sys.platform == "darwin" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return "desktop"
    return "headless"


def _make_backend(args: argparse.Namespace) -> tuple[str, Any]:
    name = _backend_name(args.backend, args.framebuffer, args.screenshot)
    if name == "framebuffer":
        return name, FramebufferBackend(args.framebuffer, width=args.width, height=args.height)
    if name == "desktop":
        return name, PygameBackend(args.width or 400, args.height or 300, args.scale)
    return name, HeadlessBackend(args.width or 400, args.height or 300, args.screenshot)


def _data_root(value: Path | None) -> Path:
    configured = value or (Path(os.environ["BADGE_DATA_DIR"]) if os.environ.get("BADGE_DATA_DIR") else None)
    return (configured or Path.home() / ".local" / "share" / "beaglebadge").expanduser().resolve()


def _launcher(store: AppStore) -> LauncherApp:
    def catalog():
        return builtin_entries(store)

    return LauncherApp(catalog)


def run(args: argparse.Namespace) -> int:
    if (args.width is not None and args.width <= 0) or (args.height is not None and args.height <= 0) or args.scale <= 0:
        raise ValueError("width, height, and scale must be positive")
    if args.frames is not None and args.frames <= 0:
        raise ValueError("--frames must be positive")

    root = _data_root(args.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    backend_name, backend = _make_backend(args)
    hardware = backend_name == "framebuffer" and not args.no_hardware
    services = PlatformServices(hardware=hardware, data_root=root)
    store = AppStore(
        cache_dir=root / "store-cache",
        install_root=root / "installed-apps",
        runner=services.commands,
    )
    launcher = _launcher(store)
    initial = launcher
    if not args.skip_onboarding and ArmbianOnboardingApp.should_start():
        initial = ArmbianOnboardingApp(on_complete=lambda: launcher)

    runtime = ApplicationRuntime(backend, services, data_root=root)
    frames = args.frames
    if backend_name == "headless" and frames is None:
        frames = 1
    console = ConsoleSession() if backend_name == "framebuffer" else nullcontext()
    with console:
        runtime.run(initial, frames=frames)
    return 0


def cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"badge-launcher: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
