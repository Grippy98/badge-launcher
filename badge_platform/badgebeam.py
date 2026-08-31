"""Read-only status for the separately supervised BadgeBeam receiver."""

from __future__ import annotations

import json
import os
from pathlib import Path


class BadgeBeamService:
    def __init__(self, data_root: str | Path) -> None:
        self.data_dir = Path(data_root) / "app-data" / "badgebeam"
        self.marker = self.data_dir / "receiver.json"
        self.payload = self.data_dir / "latest.bin"

    def _marker_data(self) -> dict[str, object]:
        try:
            value = json.loads(self.marker.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @property
    def running(self) -> bool:
        try:
            value = self._marker_data()
            pid = int(value["pid"])
            if pid <= 1:
                return False
            os.kill(pid, 0)
            return True
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False

    @property
    def available(self) -> bool:
        return self.running or self.payload.is_file()

    def status(self) -> str:
        if self.running:
            marker = self._marker_data()
            if marker.get("advertising") == "external":
                return "Receiver running; external BLE advertising required"
            if marker.get("advertising") == "legacy-mgmt":
                return "Receiver running; legacy MGMT advertising is experimental"
            return "BadgeBeam receiver running"
        if self.payload.is_file():
            return "Receiver stopped; showing last image"
        return "BadgeBeam receiver unavailable"


__all__ = ["BadgeBeamService"]
