"""Composition root for concrete Linux platform capabilities."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .bluetooth import BluetoothService
from .badgebeam import BadgeBeamService
from .command import CommandRunner
from .hardware import I2CService, LedService, SerialService, SoundService
from .input import InputService
from .network import NetworkService
from .settings import Settings
from .system import SystemService


class PlatformServices:
    def __init__(
        self,
        *,
        hardware: bool = True,
        data_root: str | Path | None = None,
        migrate_legacy_settings: bool = True,
    ) -> None:
        self.commands = CommandRunner()
        root = Path(data_root or os.environ.get("BADGE_DATA_DIR", Path.home() / ".local/share/beaglebadge"))
        legacy_path = Path.cwd() / "config.json" if migrate_legacy_settings else None
        self.settings = Settings(root / "settings.json", legacy_path=legacy_path)
        self.system = SystemService(self.commands)
        self.network = NetworkService(self.commands)
        self.bluetooth = BluetoothService(self.commands)
        self.badgebeam = BadgeBeamService(root)
        self.i2c = I2CService(self.commands)
        self.led = LedService()
        self.input = InputService() if hardware and sys.platform.startswith("linux") else None
        self.sound = SoundService(
            bool(self.settings.get("sound_enabled", True)) if hardware else False,
            open_device=hardware,
        )
        self.serial = SerialService() if hardware else None

    def close(self) -> None:
        if self.input:
            self.input.close()
        if self.serial:
            self.serial.close()
        self.sound.close()


class MockPlatformServices(PlatformServices):
    def __init__(self, *, data_root: str | Path) -> None:
        super().__init__(
            hardware=False,
            data_root=data_root,
            migrate_legacy_settings=False,
        )
