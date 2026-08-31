"""Small headless harness for application tests and tutorials.

The harness intentionally uses the real application runtime and renderer.  It
lets app authors exercise five-way input and inspect a 400 x 300 Pillow image
without knowing about launcher backends or constructing platform mocks.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

from .actions import Action, InputEvent
from .app import App


class AppHarness:
    """Run one :class:`badge_sdk.App` against the in-memory badge backend.

    Use it as a context manager so worker threads and temporary state are
    released deterministically::

        with AppHarness(MyApp()) as badge:
            badge.press(Action.SELECT)
            badge.type("hello")
            badge.image.save("screen.png")
    """

    def __init__(
        self,
        app: App,
        *,
        width: int = 400,
        height: int = 300,
        data_root: str | Path | None = None,
    ) -> None:
        if not isinstance(app, App):
            raise TypeError("AppHarness expects a badge_sdk.App instance")
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")

        # Imports stay local so importing badge_sdk.testing remains cheap and
        # does not pull Pillow into applications that never use the harness.
        from badge_platform.services import MockPlatformServices
        from badge_ui.application_runtime import ApplicationRuntime
        from badge_ui.backends.headless import HeadlessBackend

        self._temporary = TemporaryDirectory(prefix="badge-app-test-") if data_root is None else None
        root = Path(data_root or self._temporary.name).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.backend = HeadlessBackend(width, height)
        self.services = MockPlatformServices(data_root=root)
        self.runtime = ApplicationRuntime(self.backend, self.services, data_root=root)
        self._closed = False
        try:
            self.runtime.push(app)
            self.runtime.running = True
            self.runtime.step()
        except BaseException:
            self.close()
            raise

    @property
    def app(self) -> App:
        """The currently visible app (which may be a child app)."""

        current = self.runtime.current
        if current is None:
            raise RuntimeError("the harness is closed")
        return current.app

    @property
    def image(self):
        """A copy of the latest Pillow frame."""

        if self.backend.last_frame is None:
            raise RuntimeError("the app has not rendered a frame")
        return self.backend.last_frame.copy()

    def press(self, action: Action | str, *, repeat: bool = False) -> "AppHarness":
        """Dispatch one logical badge action and render the resulting state."""

        logical = action if isinstance(action, Action) else Action(str(action).lower())
        self.runtime.dispatch(InputEvent(logical, repeat=repeat))
        self.runtime.render()
        return self

    def type(self, value: str) -> "AppHarness":
        """Enter text through the same events used by a desktop keyboard."""

        for character in str(value):
            self.runtime.dispatch(InputEvent(Action.TEXT, text=character))
        self.runtime.render()
        return self

    def events(self, events: Iterable[InputEvent]) -> "AppHarness":
        """Dispatch an explicit event sequence, then render once."""

        for event in events:
            if not isinstance(event, InputEvent):
                raise TypeError("events must contain InputEvent values")
            self.runtime.dispatch(event)
        self.runtime.render()
        return self

    def step(self, count: int = 1) -> "AppHarness":
        """Advance the runtime loop for timer/background-work tests."""

        if count < 1:
            raise ValueError("count must be positive")
        for _ in range(count):
            self.runtime.step()
        return self

    def screenshot(self, path: str | Path) -> Path:
        """Save the current 400 x 300 frame and return its resolved path."""

        output = Path(path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(output)
        return output

    def close(self) -> None:
        """Release the runtime and any temporary state."""

        if not self._closed:
            self.runtime.running = False
            # Tests commonly use a temporary data root. Wait for work that has
            # already started before deleting it; queued work is cancelled by
            # the runtime so harness cleanup has a deterministic boundary.
            self.runtime.close(wait_for_workers=True)
            self._closed = True
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self) -> "AppHarness":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


__all__ = ["AppHarness"]
