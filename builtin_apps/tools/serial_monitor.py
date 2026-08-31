"""Nonblocking serial monitor (the legacy app called a nonexistent tty.read)."""

from __future__ import annotations

from badge_sdk import App, Column, Screen, Text


class SerialMonitorApp(App):
    app_id = "serial-monitor"
    name = "Serial Monitor"
    category = "tools"
    description = "View incoming data from a configured serial port"

    def __init__(self) -> None:
        super().__init__()
        self.buffer = ""
        self.timer = None

    def on_start(self) -> None:
        self.timer = self.context.call_every(0.2, self._poll)

    def on_stop(self) -> None:
        if self.timer:
            self.timer.cancel()

    def _poll(self) -> None:
        serial = self.context.services.serial
        if serial:
            incoming = serial.read()
            if incoming:
                self.buffer = (self.buffer + incoming)[-6000:]
                self.invalidate()

    def view(self) -> Screen:
        serial = self.context.services.serial
        if not serial or not serial.available:
            text = "Serial device unavailable.\n\nSet BADGE_SERIAL_DEVICE to choose a port."
        else:
            visible = "\n".join(self.buffer.splitlines()[-18:])
            text = visible or f"Listening on {serial.device}..."
        return Screen(Column(Text(text, size=11, flex=1, wrap=True), padding=6), title=self.name, footer="BACK: exit")
