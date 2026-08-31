from pathlib import Path
import threading
import time

from badge_sdk import Action, App, Button, Column, Screen, Text, TextInput
from badge_sdk.testing import AppHarness


class HarnessDemo(App):
    app_id = "harness-demo"

    def __init__(self) -> None:
        super().__init__()
        self.message = "ready"
        self.value = ""

    def view(self) -> Screen:
        return Screen(
            Column(
                Button("Change", lambda: setattr(self, "message", "changed"), key="change"),
                TextInput(self.value, on_change=lambda value: setattr(self, "value", value), key="value"),
                Text(self.message),
            )
        )


def test_harness_drives_real_focus_and_saves_screenshot(tmp_path: Path) -> None:
    with AppHarness(HarnessDemo(), data_root=tmp_path / "state") as badge:
        assert badge.image.size == (400, 300)
        badge.press(Action.SELECT).press(Action.RIGHT).type("hi")
        assert badge.app.message == "changed"
        assert badge.app.value == "hi"
        output = badge.screenshot(tmp_path / "screen.png")

    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_harness_rejects_invalid_values() -> None:
    try:
        AppHarness(object())  # type: ignore[arg-type]
    except TypeError as error:
        assert "badge_sdk.App" in str(error)
    else:  # pragma: no cover - regression guard
        raise AssertionError("invalid app was accepted")


def test_harness_waits_for_started_background_work_on_close(tmp_path: Path) -> None:
    started = threading.Event()
    marker = tmp_path / "background-finished"

    class BackgroundDemo(App):
        def on_start(self) -> None:
            def work() -> None:
                started.set()
                time.sleep(0.02)
                marker.write_text("done", encoding="utf-8")

            self.context.run_background(work)

        def view(self) -> Screen:
            return Screen(Text("working"))

    badge = AppHarness(BackgroundDemo(), data_root=tmp_path / "state")
    assert started.wait(1)
    badge.close()
    assert marker.read_text(encoding="utf-8") == "done"


def test_harness_settings_do_not_migrate_checkout_config(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "config.json").write_text('{"badge_name":"leaked"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with AppHarness(HarnessDemo(), data_root=tmp_path / "state") as badge:
        assert badge.services.settings.get("badge_name") != "leaked"
