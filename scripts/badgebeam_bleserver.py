#!/usr/bin/env python3
"""BlueZ GATT receiver for 400x300 monochrome BadgeBeam frames.

The receiver is deliberately a separate process from the launcher.  A malformed
Bluetooth connection therefore cannot take down the UI, and the viewer only
needs to watch one atomically replaced payload file.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

try:
    from .badgebeam_advertising import LegacyAdvertisingError, LegacyMgmtAdvertiser
    from .badgebeam_frames import FrameAccumulator
except ImportError:  # Direct execution from the installed scripts directory.
    from badgebeam_advertising import LegacyAdvertisingError, LegacyMgmtAdvertiser
    from badgebeam_frames import FrameAccumulator


BLUEZ = "org.bluez"
OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
PROPERTIES = "org.freedesktop.DBus.Properties"
ADAPTER = "org.bluez.Adapter1"
GATT_MANAGER = "org.bluez.GattManager1"
GATT_SERVICE = "org.bluez.GattService1"
GATT_CHARACTERISTIC = "org.bluez.GattCharacteristic1"
AD_MANAGER = "org.bluez.LEAdvertisingManager1"
ADVERTISEMENT = "org.bluez.LEAdvertisement1"

SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
DISPLAY_UUID = "12345678-1234-5678-1234-56789abcdef1"
FRAME_BYTES = 400 * 300 // 8


def _payload_path() -> Path:
    root = Path(os.environ.get("BADGE_DATA_DIR", "/var/lib/badge-launcher"))
    return root / "app-data" / "badgebeam" / "latest.bin"


def _write_frame(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".latest-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _marker_path(payload: Path) -> Path:
    return payload.parent / "receiver.json"


def _write_marker(payload: Path, advertising: str, warning: str = "") -> None:
    marker = _marker_path(payload)
    marker.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".receiver-", dir=marker.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "pid": os.getpid(),
                    "started": int(time.time()),
                    "advertising": advertising,
                    "warning": warning,
                },
                stream,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)


class Application(dbus.service.Object):
    def __init__(self, bus: dbus.SystemBus, payload: Path) -> None:
        self.path = "/com/beagleboard/badgebeam"
        self.services = [BadgeService(bus, 0, payload)]
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(OBJECT_MANAGER, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        objects = {}
        for service in self.services:
            objects[service.get_path()] = service.get_properties()
            for characteristic in service.characteristics:
                objects[characteristic.get_path()] = characteristic.get_properties()
        return objects


class Service(dbus.service.Object):
    def __init__(self, bus, index: int, uuid: str) -> None:
        self.path = f"/com/beagleboard/badgebeam/service{index}"
        self.uuid = uuid
        self.characteristics: list[Characteristic] = []
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_SERVICE: {
                "UUID": self.uuid,
                "Primary": dbus.Boolean(True),
                "Characteristics": dbus.Array(
                    [item.get_path() for item in self.characteristics], signature="o"
                ),
            }
        }


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index: int, uuid: str, flags: list[str], service: Service) -> None:
        self.path = f"{service.path}/char{index}"
        self.uuid = uuid
        self.flags = flags
        self.service = service
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_CHARACTERISTIC: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": dbus.Array(self.flags, signature="s"),
            }
        }


class BadgeService(Service):
    def __init__(self, bus, index: int, payload: Path) -> None:
        super().__init__(bus, index, SERVICE_UUID)
        self.characteristics.append(DisplayCharacteristic(bus, 0, self, payload))


class DisplayCharacteristic(Characteristic):
    def __init__(self, bus, index: int, service: Service, payload: Path) -> None:
        super().__init__(
            bus,
            index,
            DISPLAY_UUID,
            ["write", "write-without-response"],
            service,
        )
        self.payload = payload
        self.frames = FrameAccumulator(FRAME_BYTES)

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, _options):
        return dbus.Array([], signature="y")

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="aya{sv}")
    def WriteValue(self, value, _options):
        chunk = bytes(value)
        # BlueZ commonly supplies offset=0 for every write-without-response
        # packet.  BadgeBeam is a fixed-size byte stream, not a mutable GATT
        # attribute, so append each packet and slice complete frames.  Clearing
        # at an apparent frame boundary loses the tail of writes that straddle
        # the 15,000-byte boundary.
        for frame in self.frames.push(chunk):
            _write_frame(self.payload, frame)
            print(f"BadgeBeam: wrote {FRAME_BYTES}-byte image to {self.payload}", flush=True)


class Advertisement(dbus.service.Object):
    def __init__(self, bus, index: int) -> None:
        self.path = f"/com/beagleboard/badgebeam/advertisement{index}"
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        # Do not request a secondary PHY here. BlueZ/controller capabilities
        # still determine the command path, so CC33xx auto mode below avoids
        # this D-Bus advertiser entirely. The 128-bit service UUID may move the
        # local name into the scan response, which is valid behavior.
        return {
            ADVERTISEMENT: {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array([SERVICE_UUID], signature="s"),
                "LocalName": dbus.String("BeagleBadge"),
                "Discoverable": dbus.Boolean(True),
            }
        }

    @dbus.service.method(PROPERTIES, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self.get_properties()[interface][prop]

    @dbus.service.method(PROPERTIES, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.get_properties().get(interface, {})

    @dbus.service.method(ADVERTISEMENT)
    def Release(self):
        print("BadgeBeam: advertisement released", flush=True)


def _adapter(bus):
    manager = dbus.Interface(bus.get_object(BLUEZ, "/"), OBJECT_MANAGER)
    for path, interfaces in manager.GetManagedObjects().items():
        if GATT_MANAGER not in interfaces:
            continue
        obj = bus.get_object(BLUEZ, path)
        advertising = dbus.Interface(obj, AD_MANAGER) if AD_MANAGER in interfaces else None
        return (
            path,
            dbus.Interface(obj, GATT_MANAGER),
            advertising,
            dbus.Interface(obj, PROPERTIES),
        )
    raise RuntimeError("no BlueZ adapter exposing GattManager1 was found")


def _is_cc33xx(adapter_path: str) -> bool:
    """Best-effort detection for the badge controller with legacy-ad issues."""

    override = os.environ.get("BADGEBEAM_CONTROLLER", "")
    if override:
        return "cc33" in override.lower()
    adapter = adapter_path.rsplit("/", 1)[-1]
    device = Path("/sys/class/bluetooth") / adapter / "device"
    candidates = [device / "driver", device / "driver/module", device / "uevent", device / "modalias"]
    for candidate in candidates:
        try:
            if "cc33" in str(candidate.resolve()).lower():
                return True
            if candidate.is_file() and "cc33" in candidate.read_text(errors="replace").lower():
                return True
        except OSError:
            continue
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--advertising",
        choices=("auto", "bluez", "external", "legacy-mgmt"),
        default=os.environ.get("BADGEBEAM_ADVERTISING", "auto").lower(),
        help="provider: auto, bluez, external, or the opt-in unvalidated legacy-mgmt experiment",
    )
    parser.add_argument(
        "--no-advertise",
        action="store_true",
        default=os.environ.get("BADGEBEAM_NO_ADVERTISE", "0") in {"1", "true", "yes"},
        help="deprecated alias for --advertising external",
    )
    args = parser.parse_args(argv)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path, gatt, advertising, properties = _adapter(bus)
    properties.Set(ADAPTER, "Powered", dbus.Boolean(True))

    advertising_mode = "external" if args.no_advertise else args.advertising
    if advertising_mode not in {"auto", "bluez", "external", "legacy-mgmt"}:
        parser.error("BADGEBEAM_ADVERTISING must be auto, bluez, external, or legacy-mgmt")
    advertising_warning = ""
    if advertising_mode == "auto":
        if _is_cc33xx(str(adapter_path)):
            # BlueZ 5.82 has been observed selecting extended-advertising
            # commands that the CC33xx firmware silently drops.  We do not
            # substitute unvalidated raw HCI/MGMT commands here: keep GATT
            # active and require a board-proven legacy advertiser instead.
            advertising_mode = "external"
            advertising_warning = "CC33xx detected; external legacy advertiser required"
        else:
            advertising_mode = "bluez"
    if advertising_warning:
        print(f"BadgeBeam: {advertising_warning}", file=sys.stderr, flush=True)

    legacy_advertiser = None
    if advertising_mode == "legacy-mgmt":
        try:
            instance = int(os.environ.get("BADGEBEAM_MGMT_INSTANCE", "1"), 0)
            adapter_name = str(adapter_path).rsplit("/", 1)[-1]
            legacy_advertiser = LegacyMgmtAdvertiser(
                adapter_name,
                SERVICE_UUID,
                instance=instance,
            )
        except (TypeError, ValueError) as error:
            parser.error(str(error))
        advertising_warning = "experimental legacy MGMT advertising; hardware validation required"
        print(f"BadgeBeam: {advertising_warning}", file=sys.stderr, flush=True)

    payload = _payload_path()
    _marker_path(payload).unlink(missing_ok=True)
    application = Application(bus, payload)
    advertisement = Advertisement(bus, 0)
    loop = GLib.MainLoop()
    failures: list[str] = []
    ready: set[str] = set()
    expected = {"GATT application"}
    if advertising_mode == "bluez":
        expected.add("advertisement")
    elif advertising_mode == "legacy-mgmt":
        expected.add("legacy MGMT advertisement")

    def registered(kind: str):
        print(f"BadgeBeam: {kind} registered on {adapter_path}", flush=True)
        ready.add(kind)
        if ready == expected:
            _write_marker(payload, advertising_mode, advertising_warning)

    def failed(kind: str, error):
        failures.append(f"{kind}: {error}")
        print(f"BadgeBeam: failed to register {kind}: {error}", file=sys.stderr, flush=True)
        loop.quit()

    gatt.RegisterApplication(
        application.get_path(),
        {},
        reply_handler=lambda: registered("GATT application"),
        error_handler=lambda error: failed("GATT application", error),
    )
    if legacy_advertiser is not None:
        try:
            legacy_advertiser.start()
        except LegacyAdvertisingError as error:
            print(f"BadgeBeam: failed to add legacy MGMT advertisement: {error}", file=sys.stderr, flush=True)
            legacy_advertiser.stop()
            return 1
        registered("legacy MGMT advertisement")
    if advertising_mode == "bluez":
        if advertising is None:
            print("BadgeBeam: adapter has no LEAdvertisingManager1", file=sys.stderr)
            return 1
        advertising.RegisterAdvertisement(
            advertisement.get_path(),
            {},
            reply_handler=lambda: registered("advertisement"),
            error_handler=lambda error: failed("advertisement", error),
        )

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, loop.quit)
        print(f"BadgeBeam: receiving {FRAME_BYTES}-byte frames into {payload}", flush=True)
        loop.run()
    finally:
        _marker_path(payload).unlink(missing_ok=True)
        try:
            gatt.UnregisterApplication(application.get_path())
        except dbus.DBusException:
            pass
        if advertising is not None and advertising_mode == "bluez":
            try:
                advertising.UnregisterAdvertisement(advertisement.get_path())
            except dbus.DBusException:
                pass
        if legacy_advertiser is not None:
            legacy_advertiser.stop()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
