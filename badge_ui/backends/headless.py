"""In-memory backend used by tests, CI, and screenshot generation."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from badge_sdk import InputEvent, RefreshMode


class HeadlessBackend:
    def __init__(self, width: int = 400, height: int = 300, screenshot: str | Path | None = None) -> None:
        self.width = width
        self.height = height
        self.screenshot = Path(screenshot) if screenshot else None
        self.last_frame = None
        self.frames = 0
        self.last_refresh = RefreshMode.AUTO
        self._events: deque[InputEvent] = deque()

    def present(self, image, refresh: RefreshMode = RefreshMode.AUTO, damage=None) -> None:
        self.last_frame = image.copy()
        self.frames += 1
        self.last_refresh = refresh
        if self.screenshot:
            self.screenshot.parent.mkdir(parents=True, exist_ok=True)
            self.last_frame.save(self.screenshot)

    def poll(self) -> list[InputEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def inject(self, event: InputEvent) -> None:
        self._events.append(event)

    def close(self) -> None:
        pass
