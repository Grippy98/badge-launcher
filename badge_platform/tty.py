"""Small, shell-free Linux console guard used by the framebuffer launcher."""

from __future__ import annotations

import termios
from pathlib import Path
from typing import BinaryIO


class ConsoleSession:
    """Hide console text while the launcher owns the framebuffer.

    Device state is restored on close when termios is available.  Failure to
    access a console is deliberately non-fatal so development and headless
    operation need no special privileges.
    """

    def __init__(self, devices: tuple[str, ...] = ("/dev/tty0", "/dev/tty1", "/dev/console")) -> None:
        self.devices = devices
        self._streams: list[tuple[BinaryIO, list[int] | None]] = []

    def open(self) -> "ConsoleSession":
        if self._streams:
            return self
        for name in self.devices:
            try:
                stream = Path(name).open("r+b", buffering=0)
            except OSError:
                continue
            attributes: list[int] | None = None
            try:
                attributes = termios.tcgetattr(stream.fileno())
                raw = list(attributes)
                raw[3] &= ~(termios.ECHO | termios.ICANON)
                termios.tcsetattr(stream.fileno(), termios.TCSANOW, raw)
            except (OSError, termios.error):
                attributes = None
            try:
                stream.write(b"\x1b[?25l\x1b[2J\x1b[H")
            except OSError:
                pass
            self._streams.append((stream, attributes))
        return self

    def close(self) -> None:
        for stream, attributes in reversed(self._streams):
            if attributes is not None:
                try:
                    termios.tcsetattr(stream.fileno(), termios.TCSANOW, attributes)
                except (OSError, termios.error):
                    pass
            try:
                stream.write(b"\x1b[?25h")
            except OSError:
                pass
            stream.close()
        self._streams.clear()

    def __enter__(self) -> "ConsoleSession":
        return self.open()

    def __exit__(self, *_: object) -> None:
        self.close()
