"""NetworkManager Wi-Fi UI with physical-keyboard and on-screen entry."""

from __future__ import annotations

from concurrent.futures import Future

from badge_sdk import App, Column, Keyboard, Menu, MenuItem, Screen, Text, TextInput


LOWER_KEYS = (
    tuple("1234567890"),
    tuple("qwertyuiop"),
    tuple("asdfghjkl"),
    tuple("zxcvbnm"),
    tuple(".:/-_@"),
)


class WifiApp(App):
    app_id = "wifi"
    name = "Wi-Fi"
    category = "settings"
    description = "Scan, connect, and disconnect Wi-Fi networks"

    def __init__(self) -> None:
        super().__init__()
        self.networks = []
        self.selected = 0
        self.state = "list"
        self.target = None
        self.password = ""
        self.keyboard_position = (0, 0)
        self.keyboard_shift = False
        self.status = ""
        self.busy = False

    def on_start(self) -> None:
        self.scan()

    def scan(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.status = "Scanning Wi-Fi..."
        self.invalidate()
        self.context.run_background(self.context.services.network.scan, done=self._scanned)

    def _scanned(self, future: Future) -> None:
        self.busy = False
        try:
            self.networks = future.result()
            self.status = "" if self.networks else "No networks found"
        except Exception as exc:
            self.status = str(exc)
        self.selected = min(self.selected, max(0, len(self.networks) - 1))
        self.invalidate()

    def choose(self, network) -> None:
        self.target = network
        if not network.security or network.security == "--":
            self.connect()
        else:
            self.password = ""
            self.keyboard_shift = False
            self.keyboard_position = (0, 0)
            self.state = "password"
            self.invalidate()

    def _keyboard_rows(self) -> list[list[str]]:
        rows = [list(row) for row in LOWER_KEYS]
        if self.keyboard_shift:
            rows[0] = list("!@#$%^&*()")
            for index in (1, 2, 3):
                rows[index] = [key.upper() for key in rows[index]]
        rows.append(["SHIFT*" if self.keyboard_shift else "SHIFT", "SPACE", "BACK", "OK"])
        return rows

    def _keyboard_key(self, value: str) -> None:
        if value in {"SHIFT", "SHIFT*"}:
            self.keyboard_shift = not self.keyboard_shift
        elif value == "SPACE":
            self.password += " "
        elif value == "BACK":
            self.password = self.password[:-1]
        elif value == "OK":
            self.connect()
        elif len(self.password) < 128:
            self.password += value
            if self.keyboard_shift and len(value) == 1 and value.isalpha():
                self.keyboard_shift = False
        self.invalidate()

    def connect(self) -> None:
        if self.busy or self.target is None:
            return
        self.busy = True
        self.status = f"Connecting to {self.target.ssid}..."
        self.invalidate()
        device = next(iter(self.context.services.network.wifi_devices()), None)
        self.context.run_background(
            self.context.services.network.connect,
            self.target.ssid,
            self.password,
            device,
            done=self._connected,
        )

    def _connected(self, future: Future) -> None:
        self.busy = False
        try:
            ok, message = future.result()
            self.status = message or ("Connected" if ok else "Connection failed")
            if ok:
                self.state = "list"
                self.scan()
        except Exception as exc:
            self.status = str(exc)
        self.invalidate()

    def disconnect(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.status = "Disconnecting..."
        self.invalidate()
        self.context.run_background(self.context.services.network.disconnect, done=self._connected)

    def handle(self, event) -> bool:
        from badge_sdk import Action

        if event.action == Action.BACK and self.state == "password":
            self.state = "list"
            self.status = ""
            self.invalidate()
            return True
        return False

    def view(self) -> Screen:
        if self.state == "password" and self.target:
            row, column = self.keyboard_position
            keyboard = Keyboard(
                self._keyboard_rows(),
                self._keyboard_key,
                selected_row=row,
                selected_column=column,
                on_move=lambda r, c: setattr(self, "keyboard_position", (r, c)),
            )
            return Screen(
                Column(
                    Text(f"Password for {self.target.ssid}", align="center", bold=True),
                    TextInput(self.password, password=True, on_change=lambda value: setattr(self, "password", value), on_submit=self.connect, height=34),
                    keyboard,
                    gap=5,
                    padding=6,
                ),
                title=self.name,
                footer="Keyboard or joystick  BACK: cancel",
                status=self.status if self.busy else "",
            )

        items = [
            MenuItem(
                network.ssid,
                lambda network=network: self.choose(network),
                detail=("* " if network.in_use else "") + f"{network.signal}%",
            )
            for network in self.networks
        ]
        items.extend([MenuItem("Rescan", self.scan), MenuItem("Disconnect", self.disconnect)])
        return Screen(
            Column(Menu(items, selected=self.selected, on_change=lambda value: setattr(self, "selected", value), rows=6), padding=7),
            title=self.name,
            footer="UP/DOWN: select  ENTER: action  BACK: exit",
            status=self.status,
        )
