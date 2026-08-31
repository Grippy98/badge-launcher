from pathlib import Path
from types import SimpleNamespace
import heapq

from PIL import Image
import pytest

from badge_platform import MockPlatformServices
from badge_sdk import (
    Action,
    App,
    Button,
    Column,
    InputEvent,
    Keyboard,
    Menu,
    MenuItem,
    RefreshMode,
    Screen,
    Text,
    TextInput,
)
from badge_ui.application_runtime import ApplicationRuntime
from badge_ui.backends.framebuffer import FramebufferBackend
from badge_ui.backends.headless import HeadlessBackend
from badge_ui.backends.pygame import PygameBackend
from badge_ui.renderer import Renderer


class DemoApp(App):
    app_id = "demo"
    name = "Demo"

    def __init__(self):
        super().__init__()
        self.selected = 0
        self.activated = []

    def view(self):
        return Screen(
            Column(
                Text("Hello", align="center"),
                Menu(
                    [
                        MenuItem("One", lambda: self.activated.append("one")),
                        MenuItem("Two", lambda: self.activated.append("two")),
                    ],
                    selected=self.selected,
                    on_change=lambda value: setattr(self, "selected", value),
                ),
            ),
            title=self.name,
        )


def test_renderer_produces_monochrome_frame():
    app = DemoApp()
    image = Renderer().render(app.view(), 400, 300, "menu")
    assert image.mode == "L"
    assert image.size == (400, 300)
    assert image.getextrema() == (0, 255)


def test_runtime_menu_navigation_and_activation(tmp_path):
    backend = HeadlessBackend()
    services = MockPlatformServices(data_root=tmp_path)
    runtime = ApplicationRuntime(backend, services, data_root=tmp_path)
    app = DemoApp()
    runtime.push(app)
    runtime.running = True
    runtime.step()
    runtime.dispatch(InputEvent(Action.DOWN))
    runtime.dispatch(InputEvent(Action.SELECT))
    assert app.selected == 1
    assert app.activated == ["two"]
    runtime.running = False
    runtime.close()


def test_menu_and_keyboard_can_yield_focus_to_sibling_controls(tmp_path):
    class FocusApp(App):
        def __init__(self):
            super().__init__()
            self.value = ""
            self.keyboard_row = 0
            self.pressed = False

        def view(self):
            return Screen(
                Column(
                    Menu([MenuItem("One", lambda: None), MenuItem("Two", lambda: None)]),
                    TextInput(self.value, on_change=lambda value: setattr(self, "value", value)),
                    Keyboard(
                        [["a"], ["OK"]],
                        lambda _key: None,
                        selected_row=self.keyboard_row,
                        on_move=lambda row, _column: setattr(self, "keyboard_row", row),
                    ),
                    Button("Refresh", lambda: setattr(self, "pressed", True), key="refresh"),
                )
            )

    backend = HeadlessBackend()
    runtime = ApplicationRuntime(backend, MockPlatformServices(data_root=tmp_path), data_root=tmp_path)
    app = FocusApp()
    runtime.push(app)
    runtime.step()
    assert runtime.current.focus_key == "menu"

    runtime.dispatch(InputEvent(Action.RIGHT))
    assert runtime.current.focus_key == "input"
    runtime.dispatch(InputEvent(Action.DOWN))
    assert runtime.current.focus_key == "keyboard"
    runtime.dispatch(InputEvent(Action.TEXT, "x"))
    assert app.value == "x", "physical typing should still target the text field"
    runtime.dispatch(InputEvent(Action.UP))
    assert runtime.current.focus_key == "input"

    runtime.dispatch(InputEvent(Action.DOWN))
    runtime.dispatch(InputEvent(Action.DOWN))
    assert app.keyboard_row == 1
    runtime.dispatch(InputEvent(Action.DOWN))
    assert runtime.current.focus_key == "refresh"
    runtime.dispatch(InputEvent(Action.SELECT))
    assert app.pressed
    runtime.close()


def test_quit_is_distinct_from_back_and_pygame_maps_window_close(tmp_path):
    runtime = ApplicationRuntime(
        HeadlessBackend(), MockPlatformServices(data_root=tmp_path), data_root=tmp_path
    )
    runtime.push(DemoApp())
    runtime.running = True
    runtime.dispatch(InputEvent(Action.QUIT))
    assert not runtime.running
    runtime.close()

    pygame = SimpleNamespace(
        QUIT=1,
        KEYDOWN=2,
        K_UP=10,
        K_DOWN=11,
        K_LEFT=12,
        K_RIGHT=13,
        K_RETURN=14,
        K_KP_ENTER=15,
        K_ESCAPE=16,
        K_BACKSPACE=17,
        event=SimpleNamespace(get=lambda: [SimpleNamespace(type=1)]),
    )
    desktop = PygameBackend.__new__(PygameBackend)
    desktop.pygame = pygame
    assert desktop.poll() == [InputEvent(Action.QUIT)]


def test_main_sdl_forwards_user_arguments(monkeypatch):
    import importlib.util

    module_path = Path(__file__).parents[2] / "main_sdl.py"
    spec = importlib.util.spec_from_file_location("main_sdl_test", module_path)
    assert spec and spec.loader
    main_sdl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_sdl)

    received = []
    monkeypatch.setattr(main_sdl, "cli", lambda args: received.append(args) or 0)
    assert main_sdl.main(["--scale", "3", "--frames", "2"]) == 0
    assert received == [
        ["--backend", "desktop", "--no-hardware", "--scale", "3", "--frames", "2"]
    ]


def test_explicit_data_root_beats_environment(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("BADGE_DATA_DIR", str(tmp_path / "environment"))
    runtime = ApplicationRuntime(
        HeadlessBackend(), MockPlatformServices(data_root=tmp_path), data_root=explicit
    )
    assert runtime.data_root == explicit
    runtime.close()


def test_button_sound_is_nonblocking_and_repeat_safe(tmp_path):
    class Sound:
        def __init__(self):
            self.calls = []

        def start(self, frequency):
            self.calls.append(("start", frequency))

        def stop(self):
            self.calls.append(("stop",))

        def close(self):
            pass

    services = MockPlatformServices(data_root=tmp_path)
    services.sound = Sound()
    runtime = ApplicationRuntime(HeadlessBackend(), services, data_root=tmp_path)
    runtime.push(DemoApp())
    runtime.step()

    runtime.dispatch(InputEvent(Action.DOWN))
    assert services.sound.calls == [("start", 800)]
    runtime._schedule[0].due = 0
    heapq.heapify(runtime._schedule)
    runtime._run_scheduled()
    assert services.sound.calls[-1] == ("stop",)
    runtime.dispatch(InputEvent(Action.DOWN, repeat=True))
    assert services.sound.calls[-1] == ("stop",)
    runtime.close()


def test_parent_timer_is_paused_while_child_is_active(tmp_path):
    class TimerApp(App):
        def __init__(self):
            super().__init__()
            self.ticks = 0

        def on_start(self):
            self.timer = self.context.call_every(0.01, self._tick)

        def _tick(self):
            self.ticks += 1
            self.invalidate()

        def view(self):
            return Screen(Text(str(self.ticks)))

    runtime = ApplicationRuntime(
        HeadlessBackend(), MockPlatformServices(data_root=tmp_path), data_root=tmp_path
    )
    parent = TimerApp()
    runtime.push(parent)
    runtime.push(DemoApp())
    assert parent.timer.paused
    assert not parent.timer.queued

    parent.timer.due = 0
    runtime._run_scheduled()
    assert parent.ticks == 0

    runtime.pop()
    assert not parent.timer.paused
    assert parent.timer.queued
    parent.timer.due = 0
    heapq.heapify(runtime._schedule)
    runtime._run_scheduled()
    assert parent.ticks == 1
    runtime.close()


def test_failed_child_start_restores_parent_and_cleans_child(tmp_path):
    class Parent(App):
        def __init__(self):
            super().__init__()
            self.resumes = 0

        def on_start(self):
            self.timer = self.context.call_every(1.0, lambda: None)

        def on_resume(self):
            self.resumes += 1

        def view(self):
            return Screen(Text("parent"))

    class BrokenChild(App):
        name = "Broken child"

        def __init__(self):
            super().__init__()
            self.stops = 0

        def on_start(self):
            self.timer = self.context.call_every(1.0, lambda: None)
            raise RuntimeError("startup failed")

        def on_stop(self):
            self.stops += 1

        def view(self):
            return Screen(Text("child"))

    runtime = ApplicationRuntime(
        HeadlessBackend(), MockPlatformServices(data_root=tmp_path), data_root=tmp_path
    )
    parent = Parent()
    child = BrokenChild()
    runtime.push(parent)

    with pytest.raises(RuntimeError, match="startup failed"):
        runtime.push(child)

    assert len(runtime.stack) == 1
    assert runtime.current.app is parent
    assert parent.resumes == 1
    assert parent.timer.queued and not parent.timer.paused
    assert child.stops == 1
    assert child.timer.cancelled
    assert not child.context._alive
    runtime.close()


def test_initial_start_failure_propagates_after_runtime_cleanup(tmp_path):
    class BrokenInitial(App):
        def __init__(self):
            super().__init__()
            self.stops = 0

        def on_start(self):
            raise RuntimeError("initial startup failed")

        def on_stop(self):
            self.stops += 1

        def view(self):
            return Screen(Text("never rendered"))

    runtime = ApplicationRuntime(
        HeadlessBackend(), MockPlatformServices(data_root=tmp_path), data_root=tmp_path
    )
    app = BrokenInitial()

    with pytest.raises(RuntimeError, match="initial startup failed"):
        runtime.run(app, frames=1, idle_sleep=0)

    assert runtime._closed
    assert runtime.stack == []
    assert app.stops == 1
    assert not app.context._alive


def test_explicit_full_refresh_presents_full_bounds_when_frame_is_unchanged(tmp_path):
    class RecordingBackend(HeadlessBackend):
        def __init__(self):
            super().__init__()
            self.damages = []

        def present(self, image, refresh=RefreshMode.AUTO, damage=None):
            self.damages.append(damage)
            super().present(image, refresh=refresh, damage=damage)

    backend = RecordingBackend()
    runtime = ApplicationRuntime(
        backend, MockPlatformServices(data_root=tmp_path), data_root=tmp_path
    )
    runtime.push(DemoApp())
    runtime.render()
    assert backend.damages == [(0, 0, 400, 300)]

    runtime.invalidate(RefreshMode.FULL)
    runtime.render()
    assert backend.frames == 2
    assert backend.last_refresh == RefreshMode.FULL
    assert backend.damages[-1] == (0, 0, 400, 300)

    runtime.invalidate(RefreshMode.PARTIAL)
    runtime.render()
    assert backend.frames == 2, "unchanged partial frames should remain suppressed"
    runtime.close()


def test_text_input_and_keyboard_are_backend_independent(tmp_path):
    values = []
    field = TextInput("a", on_change=values.append)
    pressed = []
    keyboard = Keyboard([["b", "OK"]], pressed.append)
    screen = Screen(Column(field, keyboard))
    renderer = Renderer()
    focusables = renderer.collect_focusables(screen)
    assert [key for key, _ in focusables] == ["input", "keyboard"]
    field.replace("ab")
    keyboard.move(0, 1)
    keyboard.activate()
    assert values == ["ab"]
    assert pressed == ["OK"]


def _fake_framebuffer(bpp: int, width: int, height: int, stride: int):
    backend = FramebufferBackend.__new__(FramebufferBackend)
    backend.bits_per_pixel = bpp
    backend.width = width
    backend.height = height
    backend.stride = stride
    return backend


def test_framebuffer_pack_respects_stride_and_depth():
    image = Image.new("L", (4, 2), 255)
    image.putpixel((0, 0), 0)
    one_bit = _fake_framebuffer(1, 4, 2, 2)._pack(image)
    eight_bit = _fake_framebuffer(8, 4, 2, 6)._pack(image)
    rgb565 = _fake_framebuffer(16, 4, 2, 8)._pack(image)
    assert len(one_bit) == 4
    assert len(eight_bit) == 12
    assert len(rgb565) == 16


def test_app_failure_is_contained_and_timers_are_cancelled(tmp_path):
    class BrokenApp(App):
        name = "Broken"

        def on_start(self):
            self.timer = self.context.call_every(10, lambda: None)

        def view(self):
            raise RuntimeError("bad app")

    backend = HeadlessBackend()
    services = MockPlatformServices(data_root=tmp_path)
    runtime = ApplicationRuntime(backend, services, data_root=tmp_path)
    broken = BrokenApp()
    runtime.push(broken)
    runtime.running = True
    runtime.step()

    assert runtime.current is not None
    assert runtime.current.app.name == "Application Error"
    assert broken.timer.cancelled
    runtime.close()
