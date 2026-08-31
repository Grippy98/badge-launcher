"""Badge SDK UI for Armbian's distribution-owned first-login workflow."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from typing import Callable

from badge_sdk import (
    Action,
    App,
    Box,
    Button,
    Column,
    InputEvent,
    Keyboard,
    RefreshMode,
    Row,
    Rule,
    Screen,
    Spacer,
    Text,
)
from .armbian_backend import (
    ArmbianOnboarding,
    ValidationError,
    validate_password,
    validate_username,
)


LOWER_KEYS = (
    tuple("1234567890"),
    tuple("qwertyuiop"),
    tuple("asdfghjkl"),
    tuple("zxcvbnm._-"),
)
UPPER_KEYS = (
    tuple("!@#$%^&*()"),
    tuple("QWERTYUIOP"),
    tuple("ASDFGHJKL"),
    tuple("ZXCVBNM._-"),
)


@dataclass(frozen=True, slots=True)
class _Field:
    key: str
    title: str
    hint: str
    password: bool
    max_length: int


FIELDS = (
    _Field("root_password", "Pick a root password", "Use Show to review as you type", True, 128),
    _Field("username", "Your username", "Letters and numbers only", False, 32),
    _Field("user_password", "User password", "Enter one or choose Root", True, 128),
)
STAGES = ("Root", "Username", "Password", "Review")


@dataclass(frozen=True, slots=True)
class _FailureResult:
    complete: bool
    message: str
    exit_code: int = 1


class ArmbianOnboardingApp(App):
    """Joystick-first setup wizard that hands answers back to Armbian."""

    app_id = "system.armbian-onboarding"
    name = "Armbian Setup"
    category = "system"
    description = "Secure the image and create the daily user"

    def __init__(
        self,
        on_complete: Callable[[], App | None] | None = None,
        *,
        backend: ArmbianOnboarding | None = None,
    ) -> None:
        super().__init__()
        self.on_complete = on_complete
        self.backend = backend or ArmbianOnboarding()
        self.mode = "welcome"
        self.field_index = 0
        self.keyboard_row = 0
        self.keyboard_column = 0
        self.shifted = False
        self.password_visible = False
        self.error = ""
        self.result = None
        self._completion_future: Future | None = None
        self.answers = {field.key: "" for field in FIELDS}
        self.answers["real_name"] = ""

    @staticmethod
    def should_start(backend: ArmbianOnboarding | None = None) -> bool:
        candidate = backend or ArmbianOnboarding()
        try:
            return bool(candidate.is_pending())
        except Exception:
            return False

    def on_stop(self) -> None:
        if self._completion_future is not None:
            self._completion_future.cancel()
            self._completion_future = None
        self._clear_secrets()

    def _clear_secrets(self) -> None:
        self.answers["root_password"] = ""
        self.answers["user_password"] = ""

    def _transition(self, mode: str, *, full: bool = True) -> None:
        self.mode = mode
        self.error = ""
        self.invalidate(RefreshMode.FULL if full else RefreshMode.PARTIAL)

    def _begin(self) -> None:
        self.field_index = 0
        self.keyboard_row = self.keyboard_column = 0
        self._transition("field")

    def _keyboard_rows(self) -> tuple[tuple[str, ...], ...]:
        rows = UPPER_KEYS if self.shifted else LOWER_KEYS
        actions: tuple[str, ...] = ("SHIFT", "SPACE", "BACK", "SHOW" if not self.password_visible else "HIDE", "OK")
        if FIELDS[self.field_index].key == "user_password":
            actions = ("SHIFT", "SPACE", "BACK", "SHOW" if not self.password_visible else "HIDE", "ROOT", "OK")
        if not FIELDS[self.field_index].password:
            actions = ("SHIFT", "SPACE", "BACK", "OK")
        return rows + (actions,)

    def _keyboard_moved(self, row: int, column: int) -> None:
        self.keyboard_row = row
        self.keyboard_column = column

    def _append(self, value: str) -> None:
        field = FIELDS[self.field_index]
        if field.key == "username":
            value = value.lower()
        current = self.answers[field.key]
        if len(current) < field.max_length:
            self.answers[field.key] = (current + value)[: field.max_length]
            self.error = ""
            self.invalidate(RefreshMode.PARTIAL)

    def _delete(self) -> None:
        field = FIELDS[self.field_index]
        self.answers[field.key] = self.answers[field.key][:-1]
        self.error = ""
        self.invalidate(RefreshMode.PARTIAL)

    def _keyboard_key(self, key: str) -> None:
        if key == "SHIFT":
            self.shifted = not self.shifted
            self.invalidate(RefreshMode.PARTIAL)
        elif key == "SPACE":
            self._append(" ")
        elif key == "BACK":
            self._delete()
        elif key in {"SHOW", "HIDE"}:
            self.password_visible = not self.password_visible
            self.invalidate(RefreshMode.PARTIAL)
        elif key == "ROOT":
            self.answers["user_password"] = self.answers["root_password"]
            self._next_field()
        elif key == "OK":
            self._next_field()
        else:
            self._append(key)

    def _validate_current(self) -> None:
        field = FIELDS[self.field_index]
        value = self.answers[field.key]
        if field.password:
            validate_password(value)
        else:
            username = validate_username(value)
            self.answers["username"] = username
            self.answers["real_name"] = username[:1].upper() + username[1:]

    def _next_field(self) -> None:
        try:
            self._validate_current()
        except ValidationError as error:
            self.error = str(error)
            self.invalidate(RefreshMode.PARTIAL)
            return
        if self.field_index + 1 < len(FIELDS):
            self.field_index += 1
            self.keyboard_row = self.keyboard_column = 0
            self.shifted = False
            self.password_visible = False
            self.error = ""
            self.invalidate(RefreshMode.FULL)
        else:
            self.password_visible = False
            self._transition("review")

    def _previous(self) -> None:
        if self.field_index > 0:
            self.field_index -= 1
        else:
            self._transition("welcome")
            return
        self.keyboard_row = self.keyboard_column = 0
        self.shifted = False
        self.password_visible = False
        self.error = ""
        self.invalidate(RefreshMode.FULL)

    def _apply(self) -> None:
        if self._completion_future is not None and not self._completion_future.done():
            return
        if not self.context:
            self.error = "Setup runtime is unavailable"
            return
        self._transition("applying")
        # Pass a copy: callbacks may clear the in-memory secrets immediately
        # after Armbian reports success.
        payload = dict(self.answers)
        self._completion_future = self.context.run_background(
            self.backend.complete,
            payload,
            done=self._apply_finished,
        )

    def _apply_finished(self, future: Future) -> None:
        self._completion_future = None
        try:
            result = future.result()
        except ValidationError as error:
            result = _FailureResult(False, str(error))
        except Exception as error:
            result = _FailureResult(False, f"Setup failed: {error}")
        self.result = result
        if bool(getattr(result, "complete", False)):
            self._clear_secrets()
            self._transition("success")
        else:
            self._transition("failure")

    def _finish(self) -> None:
        next_app = self.on_complete() if self.on_complete else None
        if isinstance(next_app, App) and self.context:
            self.context.replace(next_app)

    def _review_answers(self) -> None:
        self.field_index = len(FIELDS) - 1
        self.keyboard_row = self.keyboard_column = 0
        self.shifted = False
        self.password_visible = False
        self._transition("field")

    def handle(self, event: InputEvent) -> bool:
        if self.mode == "field":
            if event.action == Action.TEXT and event.text:
                self._append(event.text)
                return True
            if event.action == Action.DELETE:
                self._delete()
                return True
            if event.action == Action.BACK:
                self._previous()
                return True
            return False
        if self.mode == "welcome":
            if event.action in (Action.SELECT, Action.RIGHT):
                self._begin()
            return True
        if self.mode == "review":
            if event.action in (Action.SELECT, Action.RIGHT):
                self._apply()
            elif event.action in (Action.BACK, Action.LEFT):
                self._review_answers()
            return True
        if self.mode == "failure":
            if event.action in (Action.SELECT, Action.RIGHT):
                self._apply()
            elif event.action in (Action.BACK, Action.LEFT):
                self._review_answers()
            return True
        if self.mode == "success":
            if event.action in (Action.SELECT, Action.RIGHT):
                self._finish()
            return True
        # Ignore input while the distribution first-login helper is running.
        return self.mode == "applying"

    def _stage_row(self, selected: int):
        return Row(
            *(
                Box(
                    Text(stage, size=10, align="center", invert=index == selected),
                    padding=2,
                    border=1,
                    invert=index == selected,
                    height=23,
                    flex=1,
                )
                for index, stage in enumerate(STAGES)
            ),
            gap=2,
            height=23,
        )

    def _welcome(self) -> Screen:
        try:
            version = self.backend.system_version()
        except Exception:
            version = "Armbian"
        return Screen(
            Column(
                Spacer(16),
                Text("Welcome to BeagleBadge", size=25, bold=True, align="center", height=42),
                Text(
                    "Secure Armbian and create your daily sudo-enabled user account.",
                    size=15,
                    align="center",
                    height=72,
                ),
                Box(Text(f"System: {version}", size=13, align="center"), height=39, padding=5),
                Spacer(13, flex=1),
                Button("Begin Setup", self._begin, key="begin", height=42),
                padding=14,
                gap=7,
            ),
            title="First Boot",
            footer="SELECT begin",
        )

    def _field(self) -> Screen:
        field = FIELDS[self.field_index]
        value = self.answers[field.key]
        shown = "*" * len(value) if field.password and not self.password_visible else value
        if len(shown) > 36:
            shown = "..." + shown[-33:]
        hint = self.error or field.hint
        keyboard = Keyboard(
            self._keyboard_rows(),
            self._keyboard_key,
            selected_row=self.keyboard_row,
            selected_column=self.keyboard_column,
            on_move=self._keyboard_moved,
            key="on-screen-keyboard",
        )
        return Screen(
            Column(
                self._stage_row(self.field_index),
                Text(field.title, size=18, bold=True, align="center", height=27),
                Box(Text((shown or " ") + "_", size=14, align="center", wrap=False), height=31, padding=3, border=2),
                Text(hint, size=10, align="center", invert=bool(self.error), height=20),
                Rule(),
                keyboard,
                padding=4,
                gap=3,
            ),
            title="Secure Armbian",
            footer="Arrows move | SELECT type | BACK previous",
        )

    def _review(self) -> Screen:
        return Screen(
            Column(
                self._stage_row(3),
                Spacer(8),
                Text("Ready to set up Armbian", size=23, bold=True, align="center", height=42),
                Box(
                    Column(
                        Text(f"User: {self.answers['username']}", size=16, bold=True),
                        Text(f"Name: {self.answers['real_name']}", size=15),
                        Rule(),
                        Text(
                            "Armbian will secure root, create this sudo-enabled "
                            "account, and finish its normal first-login tasks.",
                            size=12,
                            align="center",
                            flex=1,
                        ),
                        gap=5,
                    ),
                    padding=8,
                    flex=1,
                ),
                Button("Apply setup", self._apply, key="apply", height=39),
                padding=7,
                gap=5,
            ),
            title="Review",
            footer="SELECT apply | BACK edit",
        )

    def _applying(self) -> Screen:
        return Screen(
            Column(
                self._stage_row(3),
                Spacer(28),
                Text("Setting up your BeagleBadge", size=23, bold=True, align="center", height=50),
                Text(
                    "Armbian is securing the root account and creating your user.\n\n"
                    "Please keep the badge powered on.",
                    size=15,
                    align="center",
                    flex=1,
                ),
                padding=10,
                gap=8,
            ),
            title="Applying Setup",
            footer="Please wait",
        )

    def _result_view(self, success: bool) -> Screen:
        if success:
            heading = "Your BeagleBadge is ready"
            message = f"Armbian onboarding completed successfully.\n\nWelcome, {self.answers['real_name']}!"
            button = Button("Let's Go!", self._finish, key="finish", height=42)
            footer = "SELECT continue"
        else:
            heading = "Setup needs attention"
            detail = getattr(self.result, "message", "Setup did not finish; it is safe to retry")
            message = f"{detail}\n\nNo completed setup was marked as finished."
            button = Button("Retry", self._apply, key="retry", height=42)
            footer = "SELECT retry | BACK edit"
        return Screen(
            Column(
                self._stage_row(3),
                Spacer(12),
                Text(heading, size=23, bold=True, align="center", height=48),
                Box(Text(message, size=14, align="center"), padding=9, flex=1),
                button,
                padding=8,
                gap=7,
            ),
            title="Armbian Setup",
            footer=footer,
        )

    def view(self) -> Screen:
        if self.mode == "welcome":
            return self._welcome()
        if self.mode == "field":
            return self._field()
        if self.mode == "review":
            return self._review()
        if self.mode == "applying":
            return self._applying()
        if self.mode == "success":
            return self._result_view(True)
        return self._result_view(False)


# Short name retained for code that previously imported core.onboarding.
OnboardingApp = ArmbianOnboardingApp
