"""Bounded bluetoothctl operations for the Bluetooth settings app."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .command import CommandRunner

ADDRESS = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")


@dataclass(frozen=True, slots=True)
class BluetoothDevice:
    address: str
    name: str


class BluetoothService:
    def __init__(self, commands: CommandRunner) -> None:
        self.commands = commands

    def scan(self, seconds: int = 8) -> list[BluetoothDevice]:
        self.commands.run(["bluetoothctl", "--timeout", str(max(1, min(seconds, 30))), "scan", "on"], timeout=seconds + 3)
        result = self.commands.run(["bluetoothctl", "devices"], timeout=5)
        devices: list[BluetoothDevice] = []
        if result.ok:
            for line in result.stdout.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) >= 2 and ADDRESS.fullmatch(parts[1]):
                    devices.append(BluetoothDevice(parts[1].upper(), parts[2] if len(parts) > 2 else parts[1]))
        return devices

    def connect(self, address: str) -> tuple[bool, str]:
        if not ADDRESS.fullmatch(address):
            return False, "Invalid Bluetooth address"
        messages: list[str] = []
        for action in ("trust", "pair", "connect"):
            result = self.commands.run(["bluetoothctl", action, address], timeout=30)
            messages.append((result.stdout or result.stderr).strip())
            if action == "connect" and not result.ok:
                return False, "\n".join(message for message in messages if message)
        return True, "\n".join(message for message in messages if message)
