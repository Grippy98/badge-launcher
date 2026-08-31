"""BadgeBeam image viewer, decoupled from the platform BLE receiver."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

from badge_sdk import Action, App, Column, Image, InputEvent, RefreshMode, Screen, Text


class BadgeBeamApp(App):
    app_id = "badgebeam"
    name = "BadgeBeam"
    category = "apps"
    description = "Display a monochrome image received from BadgeBeam"

    WIDTH = 400
    HEIGHT = 300
    PAYLOAD_SIZE = WIDTH * HEIGHT // 8

    def __init__(self) -> None:
        super().__init__()
        self.payload_path: Path | None = None
        self.image = None
        self.error = ""
        self.last_mtime_ns: int | None = None
        self.timer = None
        self.pending = False

    def on_start(self) -> None:
        if not self.context:
            return
        self.payload_path = self.context.data_dir / "latest.bin"
        self.timer = self.context.call_every(1.0, self._poll)
        self._poll()

    def on_stop(self) -> None:
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _receiver_status(self) -> str:
        if not self.context:
            return "Receiver unavailable"
        receiver = getattr(self.context.services, "badgebeam", None)
        if receiver is None:
            return "Receiver unavailable; watching local payload file"
        status = getattr(receiver, "status", None)
        if callable(status):
            try:
                return str(status())
            except Exception as exc:
                return f"Receiver error: {exc}"
        if getattr(receiver, "running", False):
            return "Receiver running"
        if getattr(receiver, "available", False):
            return "Receiver ready"
        return "Receiver unavailable"

    @classmethod
    def _read_payload(cls, path: Path) -> bytes:
        payload = path.read_bytes()
        if len(payload) != cls.PAYLOAD_SIZE:
            raise ValueError(f"payload is {len(payload)} bytes; expected {cls.PAYLOAD_SIZE}")
        # Keep the wire-format bytes intact. The SDK's Image component owns
        # decoding so apps remain independent of the renderer implementation.
        return payload

    def _poll(self) -> None:
        if self.pending or self.payload_path is None:
            return
        try:
            mtime_ns = self.payload_path.stat().st_mtime_ns
        except OSError:
            return
        if mtime_ns == self.last_mtime_ns:
            return
        self.pending = True
        if self.context:
            self.context.run_background(
                self._read_payload,
                self.payload_path,
                done=lambda future, stamp=mtime_ns: self._loaded(stamp, future),
            )

    def _loaded(self, mtime_ns: int, future: Future) -> None:
        self.pending = False
        try:
            self.image = future.result()
            self.error = ""
            self.last_mtime_ns = mtime_ns
            self.invalidate(RefreshMode.FULL)
        except Exception as exc:
            self.last_mtime_ns = None
            self.error = str(exc)
            self.invalidate(RefreshMode.PARTIAL)

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.SELECT:
            self.last_mtime_ns = None
            self._poll()
            return True
        return False

    def view(self) -> Screen:
        if self.image is not None:
            # BadgeBeam owns every one of the panel's 400 x 300 pixels. A
            # title or footer would shrink and resample the incoming frame.
            return Screen(
                Image(
                    self.image,
                    source_size=(self.WIDTH, self.HEIGHT),
                    source_mode="1",
                    width=self.WIDTH,
                    height=self.HEIGHT,
                    fit="stretch",
                )
            )
        receiver = self._receiver_status()
        message = self.error or "Waiting for a 400 x 300 BadgeBeam image..."
        body = Column(
            Text(message, size=17, bold=True, align="center", flex=1),
            Text(receiver, size=11, align="center"),
            padding=12,
            gap=8,
        )
        return Screen(body, title=self.name, footer="SELECT: reload  BACK: exit")
