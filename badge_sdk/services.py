"""Structural types for optional launcher capabilities.

Applications do not need to import Linux adapters to get useful editor and
type-checker help.  These protocols describe the stable surface exposed by
``AppContext.services`` while allowing the badge, desktop preview, and tests to
provide different implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WifiNetworkInfo(Protocol):
    ssid: str
    signal: int
    security: str
    in_use: bool


class BluetoothDeviceInfo(Protocol):
    address: str
    name: str


class I2CDeviceInfo(Protocol):
    address: int
    in_use: bool


class SettingsService(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def update(self, **values: Any) -> None: ...


class SystemService(Protocol):
    def status(self) -> Any: ...
    def about(self) -> dict[str, str]: ...
    def reboot(self) -> bool: ...
    def poweroff(self) -> bool: ...


class NetworkService(Protocol):
    def wifi_devices(self) -> list[str]: ...
    def scan(self) -> list[WifiNetworkInfo]: ...
    def connect(
        self,
        ssid: str,
        password: str = "",
        interface: str | None = None,
    ) -> tuple[bool, str]: ...
    def disconnect(self, interface: str | None = None) -> tuple[bool, str]: ...


class BluetoothService(Protocol):
    def scan(self, seconds: int = 8) -> list[BluetoothDeviceInfo]: ...
    def connect(self, address: str) -> tuple[bool, str]: ...


class I2CService(Protocol):
    def buses(self) -> list[int]: ...
    def scan(self, bus: int) -> tuple[list[I2CDeviceInfo], str]: ...


class LedService(Protocol):
    available: bool

    def set(self, red: int, green: int, blue: int, brightness: int | None = None) -> bool: ...
    def rainbow(self, hue: float) -> tuple[int, int, int]: ...
    def off(self) -> None: ...


class SoundService(Protocol):
    enabled: bool

    def start(self, frequency: int) -> None: ...
    def stop(self) -> None: ...
    def beep(self, duration: float = 0.02, frequency: int = 1000) -> None: ...


class SerialService(Protocol):
    available: bool

    def read(self) -> str: ...


class BadgeBeamService(Protocol):
    data_dir: Path
    available: bool
    running: bool

    def status(self) -> str: ...


class Services(Protocol):
    """Capability registry available as ``self.context.services``."""

    settings: SettingsService
    system: SystemService
    network: NetworkService
    bluetooth: BluetoothService
    badgebeam: BadgeBeamService
    i2c: I2CService
    led: LedService
    sound: SoundService
    serial: SerialService | None


__all__ = [
    "BadgeBeamService",
    "BluetoothDeviceInfo",
    "BluetoothService",
    "I2CDeviceInfo",
    "I2CService",
    "LedService",
    "NetworkService",
    "SerialService",
    "Services",
    "SettingsService",
    "SoundService",
    "SystemService",
    "WifiNetworkInfo",
]
