"""System information screen."""

from badge_sdk import App, Column, Screen, Text


class AboutSystemApp(App):
    app_id = "about-system"
    name = "About"
    category = "settings"
    description = "Badge Launcher and operating-system information"

    def view(self) -> Screen:
        details = self.context.services.system.about()
        lines = [f"{key}: {value}" for key, value in details.items()]
        return Screen(Column(Text("\n".join(lines), size=12, flex=1, wrap=True), padding=8), title=self.name, footer="BACK: exit")
