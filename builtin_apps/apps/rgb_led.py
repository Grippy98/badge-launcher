"""RGB LED controls implemented through the portable hardware service."""

from __future__ import annotations

from badge_sdk import Action, App, Column, InputEvent, Menu, MenuItem, Progress, RefreshMode, Screen, Text


class RGBLedApp(App):
    app_id = "rgb-led"
    name = "RGB LED"
    category = "apps"
    description = "Set the badge RGB LED color, brightness, or rainbow mode"

    STATIC_COLORS = {
        "Red": (255, 0, 0),
        "Green": (0, 255, 0),
        "Blue": (0, 0, 255),
    }

    def __init__(self) -> None:
        super().__init__()
        self.mode = "Off"
        self.color = (0, 0, 0)
        self.brightness = 13
        self.hue = 0.0
        self.selected = 0
        self.timer = None
        self._rainbow_frames = 0

    @property
    def led(self):
        return self.context.services.led if self.context else None

    def on_start(self) -> None:
        if self.led:
            self.brightness = max(0, min(255, int(getattr(self.led, "brightness", self.brightness))))
        if self.context:
            self.timer = self.context.call_every(0.1, self._rainbow_tick)

    def on_stop(self) -> None:
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.led:
            self.led.off()

    def _apply_color(self) -> None:
        if self.led:
            self.led.set(*self.color, brightness=self.brightness)

    def _set_static(self, name: str) -> None:
        self.mode = name
        self.color = self.STATIC_COLORS[name]
        self._apply_color()
        self.invalidate(RefreshMode.FULL)

    def _set_rainbow(self) -> None:
        self.mode = "Rainbow"
        self.invalidate(RefreshMode.FULL)

    def _set_off(self) -> None:
        self.mode = "Off"
        self.color = (0, 0, 0)
        if self.led:
            self.led.off()
        self.invalidate(RefreshMode.FULL)

    def _adjust_brightness(self, delta: int) -> None:
        self.brightness = max(0, min(255, self.brightness + delta))
        if self.mode in self.STATIC_COLORS:
            self._apply_color()
        elif self.led:
            self.led.brightness = self.brightness
        self.invalidate(RefreshMode.PARTIAL)

    def _rainbow_tick(self) -> None:
        if self.mode != "Rainbow" or not self.led:
            return
        self.led.brightness = self.brightness
        self.color = self.led.rainbow(self.hue)
        self.hue = (self.hue + 5.0) % 360.0
        # The LED may animate quickly, while the e-paper status only needs a
        # low-cadence update to avoid needless panel wear.
        self._rainbow_frames += 1
        if self._rainbow_frames % 10 == 0:
            self.invalidate(RefreshMode.PARTIAL)

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.LEFT:
            self._adjust_brightness(-13)
            return True
        if event.action == Action.RIGHT:
            self._adjust_brightness(13)
            return True
        return False

    def view(self) -> Screen:
        available = bool(self.led and getattr(self.led, "available", True))
        red, green, blue = self.color
        items = [
            MenuItem("Red", lambda: self._set_static("Red")),
            MenuItem("Green", lambda: self._set_static("Green")),
            MenuItem("Blue", lambda: self._set_static("Blue")),
            MenuItem("Rainbow", self._set_rainbow),
            MenuItem("Off", self._set_off),
        ]
        return Screen(
            Column(
                Text(
                    "RGB LED unavailable on this system",
                    size=11,
                    align="center",
                    bold=True,
                    height=22,
                    visible=not available,
                ),
                Text(
                    f"Mode: {self.mode}   RGB: {red}, {green}, {blue}",
                    size=12,
                    align="center",
                ),
                Progress(
                    self.brightness / 255.0,
                    label=f"Brightness {round(self.brightness * 100 / 255)}%",
                    height=22,
                ),
                Menu(
                    items,
                    selected=self.selected,
                    on_change=lambda value: setattr(self, "selected", value),
                    rows=5,
                    row_height=32,
                ),
                padding=8,
                gap=6,
            ),
            title=self.name,
            footer="UP/DOWN: color  LEFT/RIGHT: brightness  BACK: exit",
        )
