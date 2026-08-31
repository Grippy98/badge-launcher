"""Behavior tests for the CPython launcher shell and Armbian wizard."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

from badge_sdk import Action, App, Box, Column, InputEvent, Keyboard, Menu, Row
from badge_ui.renderer import Renderer
from builtin_apps.system.armbian_backend import ArmbianOnboarding, CompletionResult
from builtin_apps.system.launcher import LauncherApp
from builtin_apps.system.onboarding import ArmbianOnboardingApp


class _Scheduled:
    def __init__(self, interval: float, callback) -> None:
        self.interval = interval
        self.callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _Context:
    def __init__(self, services=None) -> None:
        self.services = services or SimpleNamespace()
        self.invalidations = []
        self.opened = []
        self.replaced = []
        self.scheduled: list[_Scheduled] = []
        self.background: list[tuple[Future, object]] = []

    def invalidate(self, refresh) -> None:
        self.invalidations.append(refresh)

    def open(self, app: App) -> None:
        self.opened.append(app)

    def replace(self, app: App) -> None:
        self.replaced.append(app)

    def exit(self) -> None:
        pass

    def call_every(self, interval: float, callback) -> _Scheduled:
        scheduled = _Scheduled(interval, callback)
        self.scheduled.append(scheduled)
        return scheduled

    def run_background(self, function, *args, done=None) -> Future:
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as error:
            future.set_exception(error)
        self.background.append((future, done))
        return future

    def flush_background(self) -> None:
        pending, self.background = self.background, []
        for future, callback in pending:
            if callback:
                callback(future)


class BadgeMode(App):
    app_id = "badge-mode"
    name = "Badge Mode"
    category = "apps"
    description = "Show profile and QR code"

    def view(self):  # pragma: no cover - launcher only instantiates it
        raise NotImplementedError


class Notes(App):
    app_id = "notes"
    name = "Notes"
    category = "apps"
    description = "Portable notes"

    def view(self):  # pragma: no cover - launcher only instantiates it
        raise NotImplementedError


class I2CTool(App):
    app_id = "i2c"
    name = "I2C Scanner"
    category = "tools"

    def view(self):  # pragma: no cover - launcher only instantiates it
        raise NotImplementedError


class Wifi(App):
    app_id = "wifi"
    name = "Wi-Fi"
    category = "settings"

    def view(self):  # pragma: no cover - launcher only instantiates it
        raise NotImplementedError


def _find(component, wanted):
    if isinstance(component, wanted):
        return component
    if isinstance(component, (Column, Row)):
        for child in component.children:
            result = _find(child, wanted)
            if result is not None:
                return result
    if isinstance(component, Box) and component.child is not None:
        return _find(component.child, wanted)
    return None


def test_launcher_orders_categories_navigates_and_updates_telemetry():
    status = SimpleNamespace(
        cpu_percent=17,
        memory_percent=42,
        battery=SimpleNamespace(percent=81, state="Discharging"),
        interface="wlan0",
        ip_address="192.0.2.7",
        bluetooth_connected=True,
        usb_devices=3,
    )
    services = SimpleNamespace(system=SimpleNamespace(status=lambda: status))
    context = _Context(services)
    app = LauncherApp(
        [Wifi, I2CTool, Notes],
        badge_mode=BadgeMode,
        version="test",
        telemetry_interval=7,
    )
    app._attach(context)
    app.on_start()
    context.flush_background()

    screen = app.view()
    menu = _find(screen.body, Menu)
    assert menu is not None
    assert [item.label for item in menu.items] == ["Badge Mode", "Apps", "Tools", "Settings"]
    assert app.categories[-1] == "Settings"
    assert "wlan0 192.0.2.7" in screen.footer
    assert "BT+" in screen.footer
    assert context.scheduled[0].interval == 7

    app.handle(InputEvent(Action.DOWN))
    app.handle(InputEvent(Action.RIGHT))
    assert app._state == "apps"
    assert app._category == "apps"
    submenu = _find(app.view().body, Menu)
    assert [item.label for item in submenu.items] == ["Notes"]

    app.handle(InputEvent(Action.SELECT))
    assert isinstance(context.opened[-1], Notes)
    app.handle(InputEvent(Action.BACK))
    assert app._state == "root"

    app.on_stop()
    assert context.scheduled[0].cancelled


class _FakeOnboardingBackend:
    def __init__(self, result: CompletionResult | None = None) -> None:
        self.result = result or CompletionResult(True, 0, "Setup complete")
        self.received = None

    def is_pending(self) -> bool:
        return True

    def system_version(self) -> str:
        return "Armbian 26.8"

    def complete(self, answers):
        self.received = dict(answers)
        return self.result


class NextApp(App):
    app_id = "next"

    def view(self):  # pragma: no cover - replacement identity is enough
        raise NotImplementedError


def test_onboarding_uses_sdk_keyboard_validates_and_completes_asynchronously():
    backend = _FakeOnboardingBackend()
    context = _Context()
    app = ArmbianOnboardingApp(lambda: NextApp(), backend=backend)
    app._attach(context)

    assert app.should_start(backend)
    assert app.handle(InputEvent(Action.SELECT))
    assert app.mode == "field"
    assert isinstance(_find(app.view().body, Keyboard), Keyboard)

    # Blank passwords are rejected before advancing.
    app._keyboard_key("OK")
    assert app.field_index == 0
    assert app.error == "Enter a password"

    for character in "root secret":
        app.handle(InputEvent(Action.TEXT, character))
    app._keyboard_key("OK")
    assert app.field_index == 1
    for character in "Ada7":
        app.handle(InputEvent(Action.TEXT, character))
    app._keyboard_key("OK")
    assert app.answers["username"] == "ada7"
    assert app.answers["real_name"] == "Ada7"
    app._keyboard_key("ROOT")
    assert app.mode == "review"

    app.handle(InputEvent(Action.SELECT))
    assert app.mode == "applying"
    context.flush_background()
    assert app.mode == "success"
    assert backend.received == {
        "root_password": "root secret",
        "username": "ada7",
        "user_password": "root secret",
        "real_name": "Ada7",
    }
    assert app.answers["root_password"] == ""
    assert app.answers["user_password"] == ""

    rendered = Renderer().render(app.view(), 400, 300, "finish")
    assert rendered.size == (400, 300)
    assert rendered.getextrema() == (0, 255)
    app.handle(InputEvent(Action.SELECT))
    assert isinstance(context.replaced[-1], NextApp)


def _create_armbian_root(root: Path) -> None:
    for directory in ("etc/default", "usr/lib/armbian", "root", "proc", "etc"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "etc/armbian-release").write_text('VERSION="26.8"\n')
    (root / "usr/lib/armbian/armbian-firstlogin").write_text("#!/bin/sh\n")
    (root / "etc/passwd").write_text("root:x:0:0:root:/root:/bin/bash\n")
    (root / "etc/default/locale").write_text("LANG=en_US.UTF-8\n")
    (root / "etc/timezone").write_text("America/Chicago\n")
    (root / "root/.not_logged_in_yet").write_text(
        "KEEP_THIS=yes\nPRESET_USER_NAME='stale'\n"
    )


def test_packaged_armbian_backend_writes_private_presets_and_uses_marker(tmp_path):
    _create_armbian_root(tmp_path)
    observed = {}

    def runner(command: str) -> int:
        marker = tmp_path / "root/.not_logged_in_yet"
        observed["command"] = command
        observed["content"] = marker.read_text()
        observed["mode"] = marker.stat().st_mode & 0o777
        marker.unlink()
        return 0

    backend = ArmbianOnboarding(root=tmp_path, runner=runner, proc_root=tmp_path / "proc")
    result = backend.complete(
        {
            "root_password": "r'oot",
            "username": "Ada7",
            "real_name": "Ada Lovelace",
            "user_password": "user secret",
        }
    )

    assert result.complete
    assert observed["mode"] == 0o600
    assert observed["command"].endswith("/usr/lib/armbian/armbian-firstlogin")
    assert "KEEP_THIS=yes" in observed["content"]
    assert "stale" not in observed["content"]
    assert "PRESET_USER_NAME='ada7'" in observed["content"]
    assert "PRESET_ROOT_PASSWORD='r'\"'\"'oot'" in observed["content"]
    assert "user secret" not in observed["command"]
