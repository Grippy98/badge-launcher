"""Linux evdev reader translated into stable Badge SDK actions."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import selectors
import struct

from badge_sdk import Action, InputEvent

EV_KEY = 0x01
EVIOCGRAB = 0x40044590
INPUT_EVENT = struct.Struct("@llHHi")

ACTION_KEYS = {
    103: Action.UP,
    108: Action.DOWN,
    105: Action.LEFT,
    106: Action.RIGHT,
    28: Action.SELECT,
    96: Action.SELECT,
    353: Action.SELECT,
    1: Action.BACK,
    158: Action.BACK,
    14: Action.DELETE,
}

PLAIN = {
    **{code: value for code, value in zip(range(2, 12), "1234567890")},
    **{code: value for code, value in zip(range(16, 26), "qwertyuiop")},
    **{code: value for code, value in zip(range(30, 39), "asdfghjkl")},
    **{code: value for code, value in zip(range(44, 51), "zxcvbnm")},
    12: "-",
    13: "=",
    26: "[",
    27: "]",
    39: ";",
    40: "'",
    41: "`",
    43: "\\",
    51: ",",
    52: ".",
    53: "/",
    57: " ",
}
SHIFTED = {
    **{code: value for code, value in zip(range(2, 12), "!@#$%^&*()")},
    **{code: value.upper() for code, value in PLAIN.items() if value.isalpha()},
    12: "_",
    13: "+",
    26: "{",
    27: "}",
    39: ":",
    40: '"',
    41: "~",
    43: "|",
    51: "<",
    52: ">",
    53: "?",
    57: " ",
}


class InputService:
    def __init__(self, devices: list[str] | None = None, *, grab: bool = True) -> None:
        self.selector = selectors.DefaultSelector()
        self.files: dict[int, object] = {}
        self.shift = False
        requested = devices or self._discover()
        for device in requested:
            self._open(device, grab)

    def _discover(self) -> list[str]:
        configured = os.environ.get("BADGE_INPUT_DEVICES", "")
        if configured:
            return [entry for entry in configured.split(":") if entry]
        devices: list[str] = []
        for path in sorted(Path("/dev/input").glob("event*")):
            capabilities = Path("/sys/class/input") / path.name / "device/capabilities/ev"
            try:
                event_mask = int(capabilities.read_text().strip(), 16)
                if not event_mask & (1 << EV_KEY):
                    continue
            except (OSError, ValueError):
                # Some minimal kernels omit this sysfs attribute; attempting the
                # open is still safer than silently losing all badge buttons.
                pass
            devices.append(str(path))
        return devices

    def _open(self, path: str, grab: bool) -> None:
        try:
            stream = open(path, "rb", buffering=0)
            os.set_blocking(stream.fileno(), False)
            if grab:
                try:
                    fcntl.ioctl(stream.fileno(), EVIOCGRAB, 1)
                except OSError:
                    pass
            self.selector.register(stream, selectors.EVENT_READ)
            self.files[stream.fileno()] = stream
        except OSError:
            pass

    def poll(self) -> list[InputEvent]:
        result: list[InputEvent] = []
        for key, _ in self.selector.select(timeout=0):
            stream = key.fileobj
            try:
                raw = stream.read(INPUT_EVENT.size * 16)
            except (BlockingIOError, OSError):
                continue
            for offset in range(0, len(raw) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
                _, _, event_type, code, value = INPUT_EVENT.unpack_from(raw, offset)
                if event_type != EV_KEY:
                    continue
                if code in (42, 54):
                    self.shift = value != 0
                    continue
                if value not in (1, 2):
                    continue
                repeat = value == 2
                action = ACTION_KEYS.get(code)
                if action:
                    result.append(InputEvent(action, repeat=repeat))
                    continue
                text = (SHIFTED if self.shift else PLAIN).get(code)
                if text:
                    result.append(InputEvent(Action.TEXT, text=text, repeat=repeat))
        return result

    def close(self) -> None:
        for stream in tuple(self.files.values()):
            try:
                fcntl.ioctl(stream.fileno(), EVIOCGRAB, 0)
            except OSError:
                pass
            try:
                self.selector.unregister(stream)
            except Exception:
                pass
            stream.close()
        self.files.clear()
        self.selector.close()
