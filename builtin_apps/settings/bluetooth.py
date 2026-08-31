"""Bluetooth scan/pair/connect UI."""

from __future__ import annotations

from concurrent.futures import Future

from badge_sdk import Action, App, Column, InputEvent, Menu, MenuItem, Screen, Text


class BluetoothApp(App):
    app_id = "bluetooth"
    name = "Bluetooth"
    category = "settings"
    description = "Discover and connect Bluetooth devices"

    def __init__(self) -> None:
        super().__init__()
        self.devices = []
        self.selected = 0
        self.status = ""
        self.busy = False

    def on_start(self) -> None:
        self.scan()

    def scan(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.status = "Scanning for Bluetooth devices..."
        self.invalidate()
        self.context.run_background(self.context.services.bluetooth.scan, done=self._scanned)

    def _scanned(self, future: Future) -> None:
        self.busy = False
        try:
            self.devices = future.result()
            self.status = "" if self.devices else "No devices found"
        except Exception as exc:
            self.status = str(exc)
        self.invalidate()

    def connect(self, device) -> None:
        if self.busy:
            return
        self.busy = True
        self.status = f"Pairing with {device.name}..."
        self.invalidate()
        self.context.run_background(self.context.services.bluetooth.connect, device.address, done=self._connected)

    def _connected(self, future: Future) -> None:
        self.busy = False
        try:
            ok, message = future.result()
            self.status = message or ("Connected" if ok else "Connection failed")
        except Exception as exc:
            self.status = str(exc)
        self.invalidate()

    def view(self) -> Screen:
        items = [MenuItem(item.name, lambda item=item: self.connect(item), detail=item.address[-8:]) for item in self.devices]
        items.append(MenuItem("Scan again", self.scan))
        return Screen(
            Column(Menu(items, selected=self.selected, on_change=lambda value: setattr(self, "selected", value), rows=6), padding=7),
            title=self.name,
            footer="ENTER: pair/connect  BACK: exit",
            status=self.status,
        )
