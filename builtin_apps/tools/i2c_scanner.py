"""Hardware I2C scanner using the platform capability service."""

from __future__ import annotations

from concurrent.futures import Future

from badge_sdk import Action, App, Column, InputEvent, Menu, MenuItem, Screen, Text


class I2CScannerApp(App):
    app_id = "i2c-scanner"
    name = "I2C Scanner"
    category = "tools"
    description = "Find devices on Linux I2C buses"

    def __init__(self) -> None:
        super().__init__()
        self.buses: list[int] = []
        self.selected = 0
        self.result_bus: int | None = None
        self.results: list[str] = []
        self.status = ""

    def on_start(self) -> None:
        self.buses = self.context.services.i2c.buses()

    def _choose(self, bus: int) -> None:
        self.status = f"Scanning bus {bus}..."
        self.invalidate()
        self.context.run_background(self.context.services.i2c.scan, bus, done=lambda future: self._scanned(bus, future))

    def _scanned(self, bus: int, future: Future) -> None:
        try:
            devices, error = future.result()
            self.result_bus = bus
            self.results = [f"0x{item.address:02X}" + (" (kernel driver)" if item.in_use else "") for item in devices]
            self.status = error
        except Exception as exc:
            self.result_bus = bus
            self.results = []
            self.status = str(exc)
        self.invalidate()

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.BACK and self.result_bus is not None:
            self.result_bus = None
            self.results = []
            self.status = ""
            self.invalidate()
            return True
        return False

    def view(self) -> Screen:
        if self.result_bus is not None:
            lines = self.results or ([self.status] if self.status else ["No devices found"])
            return Screen(
                Column(Text(f"Bus {self.result_bus}", size=17, bold=True, align="center"), Text("\n".join(lines), flex=1, align="center")),
                title=self.name,
                footer="BACK: bus list",
                status="" if self.results else self.status,
            )
        items = [MenuItem(f"Bus {bus}", lambda bus=bus: self._choose(bus), detail=f"/dev/i2c-{bus}") for bus in self.buses]
        return Screen(
            Column(
                Text("Select a hardware bus to scan", align="center"),
                Menu(items, selected=self.selected, on_change=lambda index: setattr(self, "selected", index)),
                gap=8,
                padding=8,
            ),
            title=self.name,
            footer="UP/DOWN: select  ENTER: scan  BACK: exit",
            status=self.status if self.status and self.result_bus is None else "",
        )
