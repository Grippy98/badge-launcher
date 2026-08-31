"""NetworkManager command adapter without shell interpolation."""

from __future__ import annotations

from dataclasses import dataclass

from .command import CommandRunner


@dataclass(frozen=True, slots=True)
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    in_use: bool = False


def _split_escaped(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    fields.append("".join(current))
    return fields


class NetworkService:
    def __init__(self, commands: CommandRunner) -> None:
        self.commands = commands

    def wifi_devices(self) -> list[str]:
        result = self.commands.run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], timeout=5)
        devices: list[str] = []
        if result.ok:
            for line in result.stdout.splitlines():
                fields = _split_escaped(line)
                if len(fields) >= 2 and fields[1] == "wifi":
                    devices.append(fields[0])
        return devices

    def scan(self) -> list[WifiNetwork]:
        result = self.commands.run(
            ["nmcli", "--escape", "yes", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
            timeout=20,
        )
        networks: dict[str, WifiNetwork] = {}
        if result.ok:
            for line in result.stdout.splitlines():
                fields = _split_escaped(line)
                if len(fields) < 4 or not fields[1]:
                    continue
                try:
                    signal = int(fields[2])
                except ValueError:
                    signal = 0
                candidate = WifiNetwork(fields[1], signal, fields[3], fields[0] == "*")
                previous = networks.get(candidate.ssid)
                if previous is None or candidate.signal > previous.signal:
                    networks[candidate.ssid] = candidate
        return sorted(networks.values(), key=lambda item: (not item.in_use, -item.signal, item.ssid.lower()))

    def connect(self, ssid: str, password: str = "", interface: str | None = None) -> tuple[bool, str]:
        # Supplying a password as an nmcli argument exposes it through /proc and
        # process listings.  --ask reads the secret from this process's private
        # stdin pipe instead, while the recorded CommandResult remains safe to
        # log or display.
        args = ["nmcli"]
        if password:
            args.append("--ask")
        args += ["device", "wifi", "connect", ssid]
        if interface:
            args += ["ifname", interface]
        result = self.commands.run(
            args,
            timeout=35,
            input_text=f"{password}\n" if password else None,
        )
        return result.ok, (result.stdout or result.stderr).strip()

    def disconnect(self, interface: str | None = None) -> tuple[bool, str]:
        device = interface or (self.wifi_devices()[0] if self.wifi_devices() else "")
        if not device:
            return False, "No Wi-Fi interface found"
        result = self.commands.run(["nmcli", "device", "disconnect", device], timeout=15)
        return result.ok, (result.stdout or result.stderr).strip()
