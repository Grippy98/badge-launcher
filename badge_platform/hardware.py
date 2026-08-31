"""Small standard-Python adapters for badge I2C, RGB LED, sound, and serial."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
import os
from pathlib import Path
import re
import struct
import time

from .command import CommandRunner


def _sound_device() -> str:
    configured = os.environ.get("BADGE_SOUND_DEVICE")
    if configured:
        return configured
    for path in sorted(Path("/dev/input").glob("event*")):
        capability = Path("/sys/class/input") / path.name / "device/capabilities/snd"
        try:
            if int(capability.read_text().strip(), 16):
                return str(path)
        except (OSError, ValueError):
            continue
    return "/dev/input/event6"


class SoundService:
    EV_SYN = 0x00
    EV_SND = 0x12
    SND_TONE = 0x02
    EVENT = struct.Struct("@llHHi")

    def __init__(
        self,
        enabled: bool = True,
        device: str | None = None,
        *,
        open_device: bool = True,
    ) -> None:
        self.enabled = enabled
        self.device = device or _sound_device()
        self.stream = None
        if open_device:
            try:
                self.stream = open(self.device, "wb", buffering=0)
            except OSError:
                pass

    def _event(self, event_type: int, code: int, value: int, *, force: bool = False) -> None:
        if (self.enabled or force) and self.stream:
            try:
                self.stream.write(self.EVENT.pack(0, 0, event_type, code, value))
            except OSError:
                # Input devices can disappear during driver reloads or USB
                # reprobes.  Sound is optional, so degrade quietly instead of
                # taking down the launcher on the next button press.
                try:
                    self.stream.close()
                except OSError:
                    pass
                self.stream = None

    def start(self, frequency: int) -> None:
        if not self.enabled:
            return
        self._event(self.EV_SND, self.SND_TONE, max(0, int(frequency)))
        self._event(self.EV_SYN, 0, 0)

    def stop(self) -> None:
        # A preference change can disable sound while a short tone is already
        # active. Stopping is a safety operation, not a new sound, so always
        # send SND_TONE=0 (and SYN) even after ``enabled`` becomes false.
        self._event(self.EV_SND, self.SND_TONE, 0, force=True)
        self._event(self.EV_SYN, 0, 0, force=True)

    def beep(self, duration: float = 0.02, frequency: int = 1000) -> None:
        if not self.enabled:
            return
        self.start(frequency)
        time.sleep(max(0.0, duration))
        self.stop()

    def close(self) -> None:
        self.stop()
        if self.stream:
            try:
                self.stream.close()
            except OSError:
                pass
            self.stream = None


@dataclass(frozen=True, slots=True)
class I2CDevice:
    address: int
    in_use: bool = False


class I2CService:
    def __init__(self, commands: CommandRunner) -> None:
        self.commands = commands

    def buses(self) -> list[int]:
        buses: list[int] = []
        for path in sorted(Path("/dev").glob("i2c-*")):
            try:
                buses.append(int(path.name.split("-", 1)[1]))
            except (IndexError, ValueError):
                pass
        return buses

    def scan(self, bus: int) -> tuple[list[I2CDevice], str]:
        if bus not in self.buses():
            return [], f"I2C bus {bus} is unavailable"
        result = self.commands.run(["i2cdetect", "-y", "-r", str(bus)], timeout=20)
        if not result.ok:
            return [], (result.stderr or result.stdout or "i2cdetect failed").strip()
        found: dict[int, I2CDevice] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^([0-9a-fA-F]{2}):\s+(.*)$", line.strip())
            if not match:
                continue
            base = int(match.group(1), 16)
            cells = match.group(2).split()
            start = 8 if base == 0 and len(cells) == 8 else 0
            for index, cell in enumerate(cells):
                address = base + start + index
                if cell == "UU":
                    found[address] = I2CDevice(address, True)
                elif re.fullmatch(r"[0-9a-fA-F]{2}", cell):
                    parsed = int(cell, 16)
                    found[parsed] = I2CDevice(parsed, False)
        return sorted(found.values(), key=lambda item: item.address), ""


class LedService:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get("BADGE_RGB_LED")
        candidates = [Path(configured)] if configured else sorted(Path("/sys/class/leds").glob("rgb:*"))
        self.path = candidates[0] if candidates else None
        self.brightness = 13

    @property
    def available(self) -> bool:
        return bool(self.path and (self.path / "multi_intensity").exists())

    def set(self, red: int, green: int, blue: int, brightness: int | None = None) -> bool:
        if not self.available:
            return False
        if brightness is not None:
            self.brightness = max(0, min(255, int(brightness)))
        try:
            (self.path / "multi_intensity").write_text(
                f"{max(0, min(255, red))} {max(0, min(255, green))} {max(0, min(255, blue))}"
            )
            (self.path / "brightness").write_text(str(self.brightness))
            return True
        except OSError:
            return False

    def rainbow(self, hue: float) -> tuple[int, int, int]:
        red, green, blue = colorsys.hsv_to_rgb((hue % 360) / 360, 1.0, 1.0)
        color = int(red * 255), int(green * 255), int(blue * 255)
        self.set(*color)
        return color

    def off(self) -> None:
        self.set(0, 0, 0)


class SerialService:
    def __init__(self, device: str | None = None, max_buffer: int = 8192) -> None:
        self.device = device or os.environ.get("BADGE_SERIAL_DEVICE", "/dev/ttyS0")
        self.max_buffer = max_buffer
        self.fd: int | None = None
        try:
            self.fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
        except OSError:
            pass

    @property
    def available(self) -> bool:
        return self.fd is not None

    def read(self) -> str:
        if self.fd is None:
            return ""
        chunks: list[bytes] = []
        size = 0
        while size < self.max_buffer:
            try:
                chunk = os.read(self.fd, min(1024, self.max_buffer - size))
            except BlockingIOError:
                break
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
