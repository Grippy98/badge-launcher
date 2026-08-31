"""Sound preference and beeper test."""

from badge_sdk import App, Column, Menu, MenuItem, Screen, Text


class SoundSettingsApp(App):
    app_id = "sound"
    name = "Sound"
    category = "settings"
    description = "Enable, disable, and test button sounds"

    def toggle(self) -> None:
        settings = self.context.services.settings
        enabled = not bool(settings.get("sound_enabled", True))
        settings.set("sound_enabled", enabled)
        self.context.services.sound.enabled = enabled
        self.invalidate()

    def test(self) -> None:
        self.context.run_background(self.context.services.sound.beep, 0.08, 1200)

    def view(self) -> Screen:
        enabled = bool(self.context.services.settings.get("sound_enabled", True))
        return Screen(
            Column(
                Text(f"Button sound is {'ON' if enabled else 'OFF'}", size=18, align="center", bold=True),
                Menu([MenuItem("Toggle", self.toggle), MenuItem("Test beep", self.test)]),
                padding=12,
                gap=12,
            ),
            title=self.name,
            footer="ENTER: choose  BACK: exit",
        )
