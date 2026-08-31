"""Application lifecycle and context exposed by the portable SDK."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from .actions import InputEvent, RefreshMode
from .components import Screen

if TYPE_CHECKING:
    from badge_ui.application_runtime import ApplicationRuntime, ScheduledCall
    from .services import Services


class AppContext:
    """Capabilities supplied to an application by the launcher runtime."""

    def __init__(self, runtime: "ApplicationRuntime", app: "App") -> None:
        self._runtime = runtime
        self._app = app
        self._alive = True
        self._scheduled: list[ScheduledCall] = []

    @property
    def services(self) -> "Services":
        return self._runtime.services

    @property
    def data_dir(self) -> Path:
        return self._runtime.data_dir_for(self._app.app_id)

    @property
    def resources(self) -> Path:
        return self._runtime.resources_for(self._app)

    def invalidate(self, refresh: RefreshMode = RefreshMode.AUTO) -> None:
        self._runtime.invalidate(refresh)

    def open(self, app: "App") -> None:
        self._runtime.push(app)

    def exit(self) -> None:
        self._runtime.pop()

    def replace(self, app: "App") -> None:
        self._runtime.replace(app)

    def call_later(self, delay: float, callback: Callable[[], Any]) -> "ScheduledCall":
        scheduled = self._runtime.call_later(delay, callback)
        self._scheduled.append(scheduled)
        return scheduled

    def call_every(self, interval: float, callback: Callable[[], Any]) -> "ScheduledCall":
        scheduled = self._runtime.call_every(interval, callback)
        self._scheduled.append(scheduled)
        return scheduled

    def run_background(
        self,
        function: Callable[..., Any],
        *args: Any,
        done: Callable[[Future[Any]], Any] | None = None,
    ) -> Future[Any]:
        if done is None:
            return self._runtime.run_background(function, *args)

        def deliver(future: Future[Any]) -> Any:
            if self._alive:
                return done(future)
            return None

        return self._runtime.run_background(function, *args, done=deliver)

    def _detach(self) -> None:
        self._alive = False
        for scheduled in self._scheduled:
            scheduled.cancel()
        self._scheduled.clear()


class App:
    """Base class for all Badge Launcher applications.

    A minimal application generally needs only metadata and ``view``::

        class Hello(App):
            app_id = "hello"
            name = "Hello"

            def view(self):
                return Screen(Column(Text("Hello, badge!")), title=self.name)
    """

    app_id = "app"
    name = "Application"
    category = "apps"
    description = ""

    def __init__(self) -> None:
        self.context: AppContext | None = None

    def _attach(self, context: AppContext) -> None:
        self.context = context

    def on_start(self) -> None:
        """Called after the app becomes active."""

    def on_stop(self) -> None:
        """Called before the app is removed from the stack."""

    def on_resume(self) -> None:
        """Called when a child app closes and this app becomes active again."""

    def handle(self, event: InputEvent) -> bool:
        """Handle an input before the default widget navigation.

        Return ``True`` to consume it.
        """

        return False

    def view(self) -> Screen:
        raise NotImplementedError

    def invalidate(self, refresh: RefreshMode = RefreshMode.AUTO) -> None:
        if self.context:
            self.context.invalidate(refresh)

    def close(self) -> None:
        if self.context:
            self.context.exit()
