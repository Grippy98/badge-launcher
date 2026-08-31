"""Confirmed reboot and power-off operations."""

from __future__ import annotations

from concurrent.futures import Future

from badge_sdk import App, Column, Menu, MenuItem, Screen, Text


class _PowerApp(App):
    verb = "power off"

    def __init__(self) -> None:
        super().__init__()
        self.status = ""

    def execute(self) -> None:
        self.status = f"Requesting {self.verb}..."
        self.invalidate()
        operation = self.context.services.system.reboot if self.verb == "reboot" else self.context.services.system.poweroff
        self.context.run_background(operation, done=self._complete)

    def _complete(self, future: Future) -> None:
        try:
            self.status = "Request accepted" if future.result() else "Request failed; check service permissions"
        except Exception as exc:
            self.status = str(exc)
        self.invalidate()

    def view(self) -> Screen:
        return Screen(
            Column(
                Text(f"Really {self.verb} the badge?", size=18, bold=True, align="center"),
                Menu([MenuItem("Cancel", self.close), MenuItem(self.verb.title(), self.execute)]),
                padding=14,
                gap=12,
            ),
            title=self.name,
            footer="Select Cancel unless you intend to stop the launcher",
            status=self.status,
        )


class RebootApp(_PowerApp):
    app_id = "reboot"
    name = "Reboot"
    category = "settings"
    description = "Restart the badge"
    verb = "reboot"


class ShutdownApp(_PowerApp):
    app_id = "shutdown"
    name = "Shutdown"
    category = "settings"
    description = "Power off the badge"
    verb = "power off"
