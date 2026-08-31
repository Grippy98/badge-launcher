"""Atomic launcher settings with migration from the original config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


DEFAULTS: dict[str, Any] = {
    "sound_enabled": True,
    "badge_name": "Beagle\nBadge",
    "badge_info": "Badge Launcher\nCPython experimental",
    "badge_logo": 0,
    "badge_qr_link": "https://beagleboard.org",
}


class Settings:
    def __init__(self, path: str | Path, legacy_path: str | Path | None = None) -> None:
        self.path = Path(path)
        self.legacy_path = Path(legacy_path) if legacy_path else None
        self.values = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        source = self.path
        if not source.exists() and self.legacy_path and self.legacy_path.exists():
            source = self.legacy_path
        try:
            loaded = json.loads(source.read_text())
            if isinstance(loaded, dict):
                self.values.update({key: loaded[key] for key in DEFAULTS if key in loaded})
        except (OSError, ValueError, TypeError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="settings-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.values, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        self.values[key] = value
        self.save()
    def update(self, **values: Any) -> None:
        unknown = set(values) - DEFAULTS.keys()
        if unknown:
            raise KeyError(", ".join(sorted(unknown)))
        self.values.update(values)
        self.save()
