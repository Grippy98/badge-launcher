"""Read-only system telemetry and narrow power operations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import socket

from .command import CommandRunner


@dataclass(frozen=True, slots=True)
class BatteryStatus:
    percent: int | None
    state: str = "Unknown"
    name: str = ""


@dataclass(frozen=True, slots=True)
class SystemStatus:
    cpu_percent: int
    memory_percent: int
    battery: BatteryStatus
    interface: str = ""
    ip_address: str = ""
    bluetooth_connected: bool = False
    usb_devices: int = 0


class SystemService:
    def __init__(
        self,
        commands: CommandRunner,
        *,
        power_supply_root: str | Path | None = None,
        battery_name: str | None = None,
    ) -> None:
        self.commands = commands
        self._last_cpu: tuple[int, int] | None = None
        self.power_supply_root = Path(
            power_supply_root or os.environ.get("BADGE_POWER_SUPPLY_ROOT", "/sys/class/power_supply")
        )
        self.battery_name = battery_name or os.environ.get("BADGE_BATTERY_SUPPLY", "bq27541-0")

    def cpu_percent(self) -> int:
        try:
            fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
            values = [int(value) for value in fields]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            previous = self._last_cpu
            self._last_cpu = (idle, total)
            if previous is None or total == previous[1]:
                return 0
            return max(0, min(100, round(100 * (1 - (idle - previous[0]) / (total - previous[1])))))
        except (OSError, ValueError, IndexError):
            return 0

    def memory_percent(self) -> int:
        values: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0])
            total = values.get("MemTotal", 0)
            available = values.get("MemAvailable", 0)
            return round(100 * (total - available) / total) if total else 0
        except (OSError, ValueError):
            return 0

    def battery(self) -> BatteryStatus:
        candidates = sorted(self.power_supply_root.glob("*"))
        # The badge's fuel gauge is exposed as bq27541-0.  Prefer it over USB
        # power/charger supplies, while retaining a type-based fallback for
        # kernels that choose a different instance name.
        candidates.sort(key=lambda candidate: (candidate.name != self.battery_name, candidate.name))
        for candidate in candidates:
            try:
                kind = (candidate / "type").read_text().strip().lower()
            except OSError:
                continue
            if kind != "battery":
                continue
            try:
                if (candidate / "present").read_text().strip() == "0":
                    continue
            except OSError:
                pass
            if not (candidate / "capacity").is_file():
                continue
            try:
                percent = int((candidate / "capacity").read_text().strip())
            except (OSError, ValueError):
                percent = None
            try:
                state = (candidate / "status").read_text().strip()
            except OSError:
                state = "Unknown"
            return BatteryStatus(percent, state, candidate.name)
        return BatteryStatus(None)

    def _interfaces(self) -> list[str]:
        root = Path("/sys/class/net")
        result: list[str] = []
        try:
            for candidate in root.iterdir():
                if candidate.name == "lo":
                    continue
                try:
                    if (candidate / "operstate").read_text().strip() == "up":
                        result.append(candidate.name)
                except OSError:
                    continue
        except OSError:
            pass
        return sorted(result, key=lambda name: (name.startswith("wl"), name))

    def network(self) -> tuple[str, str]:
        interfaces = self._interfaces()
        if not interfaces:
            return "", ""
        interface = interfaces[0]
        result = self.commands.run(["ip", "-4", "-o", "addr", "show", "dev", interface], timeout=2)
        if result.ok:
            parts = result.stdout.split()
            if "inet" in parts:
                index = parts.index("inet")
                if index + 1 < len(parts):
                    return interface, parts[index + 1].split("/", 1)[0]
        return interface, ""

    def bluetooth_connected(self) -> bool:
        base = Path("/sys/class/bluetooth/hci0")
        try:
            return any(path.name.startswith("conn") for path in base.iterdir())
        except OSError:
            return False

    def usb_count(self) -> int:
        root = Path("/sys/bus/usb/devices")
        try:
            return sum(1 for path in root.iterdir() if not path.name.startswith("usb") and ":" not in path.name)
        except OSError:
            return 0

    def status(self) -> SystemStatus:
        interface, address = self.network()
        return SystemStatus(
            self.cpu_percent(),
            self.memory_percent(),
            self.battery(),
            interface,
            address,
            self.bluetooth_connected(),
            self.usb_count(),
        )

    def about(self) -> dict[str, str]:
        disk = shutil.disk_usage("/")
        try:
            os_name = platform.freedesktop_os_release().get("PRETTY_NAME", platform.platform())
        except OSError:
            os_name = platform.platform()
        return {
            "OS": os_name,
            "Kernel": platform.release(),
            "Machine": platform.machine(),
            "Python": platform.python_version(),
            "Hostname": socket.gethostname(),
            "Disk": f"{disk.used // (1024**3)} / {disk.total // (1024**3)} GiB",
        }

    def reboot(self) -> bool:
        return self.commands.run(["systemctl", "reboot"], timeout=10).ok

    def poweroff(self) -> bool:
        return self.commands.run(["systemctl", "poweroff"], timeout=10).ok
