"""Built-in and installed application catalog for the launcher shell."""

from __future__ import annotations

from collections.abc import Callable

from badge_platform.app_store import AppStore
from builtin_apps.apps import BadgeBeamApp, BadgeModeApp, RGBLedApp
from builtin_apps.games import BrickBreakerApp, SnakeApp
from builtin_apps.settings.about import AboutSystemApp
from builtin_apps.settings.bluetooth import BluetoothApp
from builtin_apps.settings.power import RebootApp, ShutdownApp
from builtin_apps.settings.sound import SoundSettingsApp
from builtin_apps.settings.wifi import WifiApp
from builtin_apps.system import LauncherEntry
from builtin_apps.tools.file_manager import FileManagerApp
from builtin_apps.tools.i2c_scanner import I2CScannerApp
from builtin_apps.tools.serial_monitor import SerialMonitorApp
from builtin_apps.tools.app_store import AppStoreApp


BUILTIN_APP_TYPES = (
    BadgeModeApp,
    BadgeBeamApp,
    RGBLedApp,
    SnakeApp,
    BrickBreakerApp,
    FileManagerApp,
    I2CScannerApp,
    SerialMonitorApp,
    WifiApp,
    BluetoothApp,
    SoundSettingsApp,
    AboutSystemApp,
    RebootApp,
    ShutdownApp,
)


def builtin_entries(store: AppStore | None = None) -> list[LauncherEntry]:
    """Return trusted first-party apps followed by installed portable apps.

    Installed packages are discovered from validated manifest metadata only;
    their Python is imported lazily when the user launches one.  Legacy LVGL
    packages remain visible in the store but are intentionally not runnable in
    this CPython branch.
    """

    entries = [LauncherEntry.from_type(app_type) for app_type in BUILTIN_APP_TYPES]
    if store is not None:
        entries.append(
            LauncherEntry(
                AppStoreApp.app_id,
                AppStoreApp.name,
                AppStoreApp.category,
                lambda: AppStoreApp(store),
                AppStoreApp.description,
            )
        )
    known = {entry.app_id for entry in entries}
    if store is None:
        return entries
    try:
        installed = store.installed()
    except Exception:
        return entries
    for item in installed:
        manifest = item.manifest
        if manifest.legacy or manifest.app_id in known:
            continue

        def load(app_id: str = manifest.app_id):
            return store.launch(app_id)

        entries.append(
            LauncherEntry(
                manifest.app_id,
                manifest.name,
                manifest.category,
                load,
                manifest.description,
            )
        )
        known.add(manifest.app_id)
    return entries


def catalog_source(store: AppStore) -> Callable[[], list[LauncherEntry]]:
    return lambda: builtin_entries(store)


__all__ = ["BUILTIN_APP_TYPES", "builtin_entries", "catalog_source"]
