"""Smallest interactive Badge SDK example."""

from badge_sdk import App, Button, Column, Screen, Text


class HelloBadge(App):
    app_id = "hello-badge"
    name = "Hello Badge"
    category = "apps"
    description = "A minimal portable BeagleBadge app"

    def __init__(self) -> None:
        super().__init__()
        self.message = "Hello, badge!"

    def greet(self) -> None:
        self.message = "You wrote your first app."
        self.invalidate()

    def view(self) -> Screen:
        return Screen(
            Column(
                Text(self.message, size=22, align="center", flex=1),
                Button("Say hello", self.greet, key="hello"),
                padding=12,
                gap=8,
            ),
            title=self.name,
            footer="ENTER: greet  BACK: exit",
        )
