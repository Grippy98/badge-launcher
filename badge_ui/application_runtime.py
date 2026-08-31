"""Single-loop application host for portable Badge SDK apps."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import heapq
import inspect
import os
from pathlib import Path
from queue import SimpleQueue
import sys
import time
import traceback
from typing import Any, Callable

from badge_sdk import (
    Action,
    App,
    AppContext,
    Button,
    InputEvent,
    Keyboard,
    Menu,
    RefreshMode,
    TextInput,
    Column,
    Screen,
    Text,
)
from .renderer import Renderer


@dataclass(order=True)
class ScheduledCall:
    due: float
    sequence: int
    callback: Callable[[], Any] = field(compare=False)
    interval: float = field(default=0.0, compare=False)
    cancelled: bool = field(default=False, compare=False)
    paused: bool = field(default=False, compare=False)
    remaining: float = field(default=0.0, compare=False)
    queued: bool = field(default=True, compare=False)
    owner: Any = field(default=None, compare=False, repr=False)

    def cancel(self) -> None:
        self.cancelled = True
        self.queued = False


@dataclass
class _AppFrame:
    app: App
    context: AppContext
    focus_key: str | None = None
    tree: Any = None


class _CrashApp(App):
    app_id = "system.app-error"
    name = "Application Error"
    category = "system"

    def __init__(self, failed_name: str, error: BaseException) -> None:
        super().__init__()
        self.failed_name = failed_name
        self.message = f"{type(error).__name__}: {error}"[:500]

    def view(self) -> Screen:
        return Screen(
            Column(
                Text(f"{self.failed_name} stopped unexpectedly.", size=18, bold=True, align="center"),
                Text(self.message, size=12, align="center", flex=1),
                padding=14,
                gap=12,
            ),
            title=self.name,
            footer="BACK: return to the launcher",
            full_refresh=True,
        )


class ApplicationRuntime:
    def __init__(
        self,
        backend: Any,
        services: Any,
        *,
        data_root: str | Path | None = None,
        workers: int = 4,
        partial_limit: int = 12,
    ) -> None:
        self.backend = backend
        self.services = services
        self.renderer = Renderer()
        self.stack: list[_AppFrame] = []
        self.dirty = True
        self.requested_refresh = RefreshMode.FULL
        self.previous_frame = None
        self.partial_count = 0
        self.partial_limit = partial_limit
        self.running = False
        self._schedule: list[ScheduledCall] = []
        self._sequence = 0
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="badge-app")
        self._closed = False
        self._completed: SimpleQueue[
            tuple[Any, Callable[[Future[Any]], Any], Future[Any]]
        ] = SimpleQueue()
        self._sound_stop: ScheduledCall | None = None
        default_data = os.environ.get("BADGE_DATA_DIR")
        if data_root is not None:
            self.data_root = Path(data_root)
        elif default_data:
            self.data_root = Path(default_data)
        else:
            self.data_root = Path.home() / ".local" / "share" / "beaglebadge"

    @property
    def current(self) -> _AppFrame | None:
        return self.stack[-1] if self.stack else None

    def data_dir_for(self, app_id: str) -> Path:
        safe = "".join(ch for ch in app_id.lower() if ch.isalnum() or ch in "-_").strip("-_") or "app"
        path = self.data_root / "app-data" / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resources_for(self, app: App) -> Path:
        try:
            source = inspect.getfile(type(app))
            return Path(source).resolve().parent
        except (OSError, TypeError):
            return Path.cwd()

    def _make_frame(self, app: App) -> _AppFrame:
        context = AppContext(self, app)
        app._attach(context)
        return _AppFrame(app=app, context=context)

    def push(self, app: App) -> None:
        parent = self.current
        original_depth = len(self.stack)
        if parent is not None:
            self._pause_frame(parent)
        try:
            frame = self._make_frame(app)
            self.stack.append(frame)
            app.on_start()
        except BaseException as error:
            # on_start may have allocated timers, workers, hardware state, or
            # even opened another child. Unwind everything created above the
            # original stack boundary before returning control to the parent.
            while len(self.stack) > original_depth:
                self._stop_frame(self.stack.pop())
            if parent is not None and self.current is parent:
                self._resume_frame(parent)
                try:
                    parent.app.on_resume()
                except Exception:
                    traceback.print_exc(file=sys.stderr)
                self.invalidate(RefreshMode.FULL)
            # If the main loop catches this later, identify the app that
            # actually failed rather than incorrectly blaming its parent.
            try:
                setattr(error, "_badge_failed_app_name", app.name)
            except Exception:
                pass
            raise
        self.invalidate(RefreshMode.FULL)

    def replace(self, app: App) -> None:
        if self.stack:
            old = self.stack.pop()
            self._stop_frame(old)
        self.push(app)

    def pop(self) -> None:
        if len(self.stack) <= 1:
            self.running = False
            return
        old = self.stack.pop()
        self._stop_frame(old)
        resumed = self.stack[-1]
        self._resume_frame(resumed)
        resumed.app.on_resume()
        self.invalidate(RefreshMode.FULL)

    def _pause_frame(self, frame: _AppFrame) -> None:
        """Pause callbacks owned by an app while a child is on screen."""

        now = time.monotonic()
        changed = False
        for scheduled in frame.context._scheduled:
            if scheduled.cancelled or scheduled.paused or not scheduled.queued:
                continue
            scheduled.remaining = max(0.0, scheduled.due - now)
            scheduled.paused = True
            scheduled.queued = False
            changed = True
        if changed:
            self._schedule = [
                scheduled
                for scheduled in self._schedule
                if scheduled.queued and not scheduled.cancelled
            ]
            heapq.heapify(self._schedule)

    def _resume_frame(self, frame: _AppFrame) -> None:
        now = time.monotonic()
        for scheduled in frame.context._scheduled:
            if scheduled.cancelled or not scheduled.paused:
                continue
            scheduled.paused = False
            scheduled.due = now + scheduled.remaining
            scheduled.remaining = 0.0
            scheduled.queued = True
            heapq.heappush(self._schedule, scheduled)

    def _stop_frame(self, frame: _AppFrame) -> None:
        try:
            frame.app.on_stop()
        except Exception:
            traceback.print_exc(file=sys.stderr)
        finally:
            frame.context._detach()

    def _handle_crash(self, error: BaseException) -> None:
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        current = self.current
        failed_start_name = getattr(error, "_badge_failed_app_name", "")
        if failed_start_name and current is not None:
            self.push(_CrashApp(str(failed_start_name), error))
            return
        if current is None or isinstance(current.app, _CrashApp):
            self.running = False
            return
        failed_name = current.app.name
        self.stack.pop()
        self._stop_frame(current)
        self.push(_CrashApp(failed_name, error))

    def invalidate(self, refresh: RefreshMode = RefreshMode.AUTO) -> None:
        self.dirty = True
        priority = {RefreshMode.AUTO: 0, RefreshMode.PARTIAL: 1, RefreshMode.FULL: 2}
        if priority[refresh] > priority[self.requested_refresh]:
            self.requested_refresh = refresh

    def _schedule_call(
        self,
        delay: float,
        callback: Callable[[], Any],
        *,
        interval: float = 0.0,
        owner: Any = None,
    ) -> ScheduledCall:
        self._sequence += 1
        scheduled = ScheduledCall(
            time.monotonic() + max(0.0, delay),
            self._sequence,
            callback,
            interval=interval,
            owner=owner,
        )
        heapq.heappush(self._schedule, scheduled)
        return scheduled

    def call_later(self, delay: float, callback: Callable[[], Any]) -> ScheduledCall:
        owner = self.current.context if self.current is not None else None
        return self._schedule_call(delay, callback, owner=owner)

    def call_every(self, interval: float, callback: Callable[[], Any]) -> ScheduledCall:
        safe_interval = max(0.01, interval)
        owner = self.current.context if self.current is not None else None
        return self._schedule_call(
            safe_interval,
            callback,
            interval=safe_interval,
            owner=owner,
        )

    def run_background(
        self,
        function: Callable[..., Any],
        *args: Any,
        done: Callable[[Future[Any]], Any] | None = None,
    ) -> Future[Any]:
        owner = self.current.context if self.current is not None else None
        future = self._executor.submit(function, *args)
        if done:
            future.add_done_callback(
                lambda result: self._completed.put((owner, done, result))
            )
        return future

    def _run_scheduled(self) -> None:
        now = time.monotonic()
        while self._schedule and self._schedule[0].due <= now:
            scheduled = heapq.heappop(self._schedule)
            scheduled.queued = False
            if scheduled.cancelled:
                continue
            if scheduled.owner is not None and (
                self.current is None or self.current.context is not scheduled.owner
            ):
                scheduled.paused = True
                scheduled.remaining = scheduled.interval
                continue
            scheduled.callback()
            if scheduled.interval and not scheduled.cancelled:
                if scheduled.owner is not None and (
                    self.current is None or self.current.context is not scheduled.owner
                ):
                    scheduled.paused = True
                    scheduled.remaining = scheduled.interval
                else:
                    scheduled.due = now + scheduled.interval
                    scheduled.queued = True
                    heapq.heappush(self._schedule, scheduled)
        completed = []
        while not self._completed.empty():
            completed.append(self._completed.get())
        for owner, callback, future in completed:
            if owner is not None and (self.current is None or self.current.context is not owner):
                if getattr(owner, "_alive", False):
                    self._completed.put((owner, callback, future))
                continue
            callback(future)

    def _focusables(self) -> list[tuple[str, Any]]:
        current = self.current
        if current is None or current.tree is None:
            return []
        return self.renderer.collect_focusables(current.tree)

    def _ensure_focus(self) -> None:
        current = self.current
        if current is None:
            return
        focusables = self._focusables()
        keys = [key for key, _ in focusables]
        if current.focus_key not in keys:
            current.focus_key = keys[0] if keys else None

    def _focused_component(self) -> Any | None:
        current = self.current
        if current is None:
            return None
        for key, component in self._focusables():
            if key == current.focus_key:
                return component
        return None

    def _text_input(self) -> TextInput | None:
        focused = self._focused_component()
        if isinstance(focused, TextInput):
            return focused
        for _key, component in self._focusables():
            if isinstance(component, TextInput):
                return component
        return None

    def _move_focus(self, delta: int) -> None:
        current = self.current
        if current is None:
            return
        focusables = self._focusables()
        if not focusables:
            return
        keys = [key for key, _ in focusables]
        try:
            index = keys.index(current.focus_key)
        except ValueError:
            index = 0
        current.focus_key = keys[(index + delta) % len(keys)]
        self.invalidate(RefreshMode.PARTIAL)

    def dispatch(self, event: InputEvent) -> None:
        if event.action == Action.QUIT:
            self.running = False
            return
        current = self.current
        if current is None:
            return
        self._button_sound(event)
        if current.app.handle(event):
            self.invalidate(RefreshMode.PARTIAL)
            return
        focused = self._focused_component()

        if event.action in (Action.TEXT, Action.DELETE):
            text_input = self._text_input()
            if text_input is not None:
                if event.action == Action.TEXT and event.text:
                    text_input.replace(text_input.value + event.text)
                elif event.action == Action.DELETE:
                    text_input.replace(text_input.value[:-1])
                self.invalidate(RefreshMode.PARTIAL)
                return

        if isinstance(focused, Menu):
            if event.action == Action.UP:
                focused.move(-1)
                self.invalidate(RefreshMode.PARTIAL)
                return
            if event.action == Action.DOWN:
                focused.move(1)
                self.invalidate(RefreshMode.PARTIAL)
                return
            if event.action == Action.LEFT:
                self._move_focus(-1)
                return
            if event.action == Action.RIGHT:
                self._move_focus(1)
                return
            if event.action == Action.SELECT:
                focused.activate()
                self.invalidate(RefreshMode.FULL)
                return
        elif isinstance(focused, Keyboard):
            if event.action == Action.UP:
                if focused.selected_row == 0:
                    self._move_focus(-1)
                    return
                focused.move(-1, 0)
            elif event.action == Action.DOWN:
                if focused.selected_row == len(focused.rows) - 1:
                    self._move_focus(1)
                    return
                focused.move(1, 0)
            elif event.action == Action.LEFT:
                focused.move(0, -1)
            elif event.action == Action.RIGHT:
                focused.move(0, 1)
            elif event.action == Action.SELECT:
                focused.activate()
            else:
                focused = None
            if focused is not None:
                self.invalidate(RefreshMode.PARTIAL)
                return
        elif isinstance(focused, TextInput):
            if event.action == Action.TEXT and event.text:
                focused.replace(focused.value + event.text)
                self.invalidate(RefreshMode.PARTIAL)
                return
            if event.action == Action.DELETE:
                focused.replace(focused.value[:-1])
                self.invalidate(RefreshMode.PARTIAL)
                return
            if event.action == Action.SELECT and focused.on_submit:
                focused.on_submit()
                self.invalidate(RefreshMode.FULL)
                return
        elif isinstance(focused, Button) and event.action == Action.SELECT:
            if focused.enabled and focused.on_press:
                focused.on_press()
            self.invalidate(RefreshMode.FULL)
            return

        if event.action in (Action.UP, Action.LEFT):
            self._move_focus(-1)
        elif event.action in (Action.DOWN, Action.RIGHT):
            self._move_focus(1)
        elif event.action == Action.BACK:
            self.pop()

    def _button_sound(self, event: InputEvent) -> None:
        if event.repeat:
            return
        sound = getattr(self.services, "sound", None)
        start = getattr(sound, "start", None)
        stop = getattr(sound, "stop", None)
        if not callable(start) or not callable(stop):
            return
        try:
            start(800)
        except OSError:
            return
        if self._sound_stop is not None:
            self._sound_stop.cancel()

        def stop_safely() -> None:
            try:
                stop()
            except OSError:
                pass

        # This is runtime-owned rather than app-owned so opening a child does
        # not pause the stop callback and leave the tone sounding.
        self._sound_stop = self._schedule_call(0.01, stop_safely, owner=None)

    def _damage(self, previous, current):
        if previous is None:
            return (0, 0, current.width, current.height)
        from PIL import ImageChops

        return ImageChops.difference(previous, current).getbbox()

    def _select_refresh(self, requested: RefreshMode, damage, frame) -> RefreshMode:
        if requested == RefreshMode.FULL:
            return RefreshMode.FULL
        if damage is None:
            return RefreshMode.AUTO
        area = (damage[2] - damage[0]) * (damage[3] - damage[1])
        ratio = area / max(1, frame.width * frame.height)
        if self.partial_count >= self.partial_limit or ratio > 0.45:
            return RefreshMode.FULL
        return RefreshMode.PARTIAL

    def render(self) -> None:
        current = self.current
        if current is None or not self.dirty:
            return
        current.tree = current.app.view()
        self._ensure_focus()
        frame = self.renderer.render(current.tree, self.backend.width, self.backend.height, current.focus_key)
        damage = self._damage(self.previous_frame, frame)
        requested = RefreshMode.FULL if current.tree.full_refresh else self.requested_refresh
        refresh = self._select_refresh(requested, damage, frame)
        present_damage = (
            (0, 0, frame.width, frame.height)
            if refresh == RefreshMode.FULL
            else damage
        )
        if present_damage is not None:
            self.backend.present(frame, refresh=refresh, damage=present_damage)
            self.previous_frame = frame.copy()
            if refresh == RefreshMode.FULL:
                self.partial_count = 0
            elif refresh == RefreshMode.PARTIAL:
                self.partial_count += 1
        self.dirty = False
        self.requested_refresh = RefreshMode.AUTO

    def _poll_events(self) -> list[InputEvent]:
        events = list(self.backend.poll())
        input_service = getattr(self.services, "input", None)
        if input_service is not None:
            events.extend(input_service.poll())
        return events

    def step(self) -> None:
        try:
            self._run_scheduled()
            for event in self._poll_events():
                self.dispatch(event)
            self.render()
        except Exception as error:
            self._handle_crash(error)
            self.render()

    def run(self, initial: App, *, frames: int | None = None, idle_sleep: float = 0.02) -> None:
        """Run until exit, propagating an initial app startup failure after cleanup."""

        iterations = 0
        try:
            self.push(initial)
            self.running = True
            while self.running:
                self.step()
                iterations += 1
                if frames is not None and iterations >= frames:
                    break
                time.sleep(idle_sleep)
        finally:
            self.close()

    def close(self, *, wait_for_workers: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        while self.stack:
            self._stop_frame(self.stack.pop())
        self._executor.shutdown(wait=wait_for_workers, cancel_futures=True)
        self.backend.close()
        close = getattr(self.services, "close", None)
        if close:
            close()
