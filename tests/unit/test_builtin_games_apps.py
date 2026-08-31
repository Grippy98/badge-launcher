"""Focused behavior tests for the portable first-party apps and games."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
import random

from PIL import Image as PILImage

from badge_sdk import Action, Canvas, Image, InputEvent, Keyboard, RefreshMode, TextInput
from badge_ui.renderer import Renderer
from builtin_apps.apps.badge_mode import BadgeModeApp
from builtin_apps.apps.badgebeam import BadgeBeamApp
from builtin_apps.apps.rgb_led import RGBLedApp
from builtin_apps.games.brick_breaker import BrickBreakerApp
from builtin_apps.games.snake import SnakeApp


class FakeScheduledCall:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeSettings:
    def __init__(self) -> None:
        self.values = {
            "badge_name": "Beagle Badge",
            "badge_info": "Portable apps",
            "badge_logo": 0,
            "badge_qr_link": "https://beagleboard.org",
            "sound_enabled": True,
        }

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value

    def update(self, **values) -> None:
        self.values.update(values)


class FakeLed:
    available = True

    def __init__(self) -> None:
        self.brightness = 13
        self.calls: list[tuple] = []

    def set(self, red: int, green: int, blue: int, brightness: int | None = None) -> bool:
        if brightness is not None:
            self.brightness = brightness
        self.calls.append(("set", red, green, blue, self.brightness))
        return True

    def rainbow(self, hue: float) -> tuple[int, int, int]:
        color = (int(hue) % 256, 200, 100)
        self.calls.append(("rainbow", hue, self.brightness))
        return color

    def off(self) -> None:
        self.calls.append(("off",))


class FakeSound:
    def __init__(self) -> None:
        self.calls: list[tuple[float, int]] = []

    def beep(self, duration: float, frequency: int) -> None:
        self.calls.append((duration, frequency))


class FakeServices:
    def __init__(self) -> None:
        self.settings = FakeSettings()
        self.led = FakeLed()
        self.sound = FakeSound()


class FakeContext:
    def __init__(self, root: Path) -> None:
        self.services = FakeServices()
        self.data_dir = root / "data"
        self.resources = root / "resources"
        self.data_dir.mkdir(parents=True)
        self.resources.mkdir(parents=True)
        self.invalidations: list[RefreshMode] = []
        self.scheduled: list[FakeScheduledCall] = []
        self.exited = False

    def invalidate(self, refresh: RefreshMode = RefreshMode.AUTO) -> None:
        self.invalidations.append(refresh)

    def exit(self) -> None:
        self.exited = True

    def call_every(self, interval: float, callback) -> FakeScheduledCall:
        call = FakeScheduledCall(interval)
        call.callback = callback
        self.scheduled.append(call)
        return call

    def run_background(self, function, *args, done=None) -> Future:
        future: Future = Future()
        try:
            future.set_result(function(*args))
        except Exception as exc:
            future.set_exception(exc)
        if done:
            done(future)
        return future


def attach(app, tmp_path: Path) -> FakeContext:
    context = FakeContext(tmp_path)
    app._attach(context)  # Exercise the same lifecycle boundary as ApplicationRuntime.
    return context


def test_badge_mode_uses_scoped_profiles_and_persists_edits(tmp_path: Path) -> None:
    app = BadgeModeApp(rng=random.Random(1))
    context = attach(app, tmp_path)
    profile_dir = context.data_dir / "profile_images"
    profile_dir.mkdir()
    (profile_dir / "one.bin").write_bytes(bytes(128 * 128))
    (profile_dir / "two.bin").write_bytes(bytes([255]) * (128 * 128))

    app.on_start()
    assert len(app.profile_images) == 2
    assert app.handle(InputEvent(Action.RIGHT))
    assert app.profile_index == 1
    assert app.handle(InputEvent(Action.SELECT))
    editor = app.view().body.children[1]
    assert isinstance(editor, TextInput)
    keyboard = app.view().body.children[3]
    assert isinstance(keyboard, Keyboard)
    app.edit_value = ""
    app._keyboard_key("SHIFT")
    app._keyboard_key("A")
    app._keyboard_key("SPACE")
    app._keyboard_key("b")
    assert app.edit_value == "A b"

    app.edit_value = "Ada"
    app._advance_edit()
    app.edit_value = "Badge developer"
    app._advance_edit()
    app.edit_value = "https://example.test/ada"
    app._advance_edit()
    assert app.edit_index is None
    assert context.services.settings.get("badge_name") == "Ada"
    assert context.services.settings.get("badge_qr_link") == "https://example.test/ada"


def test_rgb_led_uses_service_timer_and_turns_off_on_stop(tmp_path: Path) -> None:
    app = RGBLedApp()
    context = attach(app, tmp_path)
    app.on_start()
    original = app.brightness
    assert context.scheduled[0].interval == 0.1
    assert app.handle(InputEvent(Action.RIGHT))
    assert app.brightness == min(255, original + 13)

    app._set_static("Red")
    assert context.services.led.calls[-1][1:4] == (255, 0, 0)
    app._set_rainbow()
    app._rainbow_tick()
    assert context.services.led.calls[-1][0] == "rainbow"
    timer = app.timer
    app.on_stop()
    assert timer.cancelled
    assert context.services.led.calls[-1] == ("off",)


def test_rgb_led_unavailable_message_does_not_cover_controls(tmp_path: Path) -> None:
    app = RGBLedApp()
    context = attach(app, tmp_path)
    context.services.led.available = False

    screen = app.view()
    assert screen.status == ""
    assert screen.body.children[0].visible
    assert "unavailable" in screen.body.children[0].text.lower()
    assert Renderer().collect_focusables(screen)


def test_badgebeam_loads_raw_i1_payload_and_reports_missing_receiver(tmp_path: Path) -> None:
    app = BadgeBeamApp()
    context = attach(app, tmp_path)
    payload = bytes([0xAA]) * BadgeBeamApp.PAYLOAD_SIZE
    (context.data_dir / "latest.bin").write_bytes(payload)

    app.on_start()
    assert app.image == payload
    assert app.error == ""
    assert "unavailable" in app._receiver_status().lower()
    loaded_view = app.view()
    image_component = loaded_view.body
    assert isinstance(image_component, Image)
    assert image_component.source_size == (400, 300)
    assert image_component.source_mode == "1"
    assert loaded_view.title == loaded_view.footer == ""
    rendered = Renderer().render(loaded_view, 400, 300)
    expected = PILImage.frombytes("1", (400, 300), payload).convert("L")
    assert rendered.tobytes() == expected.tobytes()
    timer = app.timer
    app.on_stop()
    assert timer.cancelled


def test_snake_moves_grows_rejects_reverse_and_uses_canvas(tmp_path: Path) -> None:
    app = SnakeApp(rng=random.Random(2))
    context = attach(app, tmp_path)
    app.on_start()
    assert context.scheduled[0].interval == app.STEP_SECONDS
    assert isinstance(app.view().body, Canvas)

    old_head = app.snake[0]
    app.food = (old_head[0], old_head[1] - 1)
    old_length = len(app.snake)
    app.step()
    assert app.score == 10
    assert len(app.snake) == old_length + 1
    assert context.services.sound.calls[-1] == (0.05, 2000)
    assert Renderer().render(app.view(), 400, 300).size == (400, 300)

    app.next_direction = (0, -1)
    app.handle(InputEvent(Action.DOWN))
    assert app.next_direction == (0, -1)
    app.handle(InputEvent(Action.LEFT))
    assert app.next_direction == (-1, 0)


def test_snake_collision_sets_game_over(tmp_path: Path) -> None:
    app = SnakeApp(rng=random.Random(3))
    context = attach(app, tmp_path)
    app.snake = [(2, 2), (2, 3), (1, 3), (1, 2), (1, 1), (2, 1)]
    app.direction = (-1, 0)
    app.next_direction = (-1, 0)
    app.step()
    assert app.game_over
    assert context.services.sound.calls[-1] == (0.4, 300)


def test_brick_breaker_launches_hits_brick_and_restarts(tmp_path: Path) -> None:
    app = BrickBreakerApp(rng=random.Random(4))
    context = attach(app, tmp_path)
    app.on_start()
    assert context.scheduled[0].interval == app.STEP_SECONDS
    assert isinstance(app.view().body, Canvas)
    assert app.handle(InputEvent(Action.SELECT))
    assert not app.waiting

    app.ball_x, app.ball_y = 1, 6
    app.ball_dx, app.ball_dy = 0, -1
    assert (1, 5) in app.bricks
    app.step()
    assert (1, 5) not in app.bricks
    assert app.score == 10
    assert context.services.sound.calls[-1] == (0.03, 1800)
    assert Renderer().render(app.view(), 400, 300).size == (400, 300)

    app.game_over = True
    app.handle(InputEvent(Action.SELECT))
    assert not app.game_over
    assert app.waiting
    assert app.score == 0


def test_ports_do_not_import_lvgl() -> None:
    roots = (Path("builtin_apps/apps"), Path("builtin_apps/games"))
    sources = [path.read_text() for root in roots for path in root.glob("*.py")]
    assert sources
    assert all("import lvgl" not in source for source in sources)
