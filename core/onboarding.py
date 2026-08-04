"""Joystick-driven, on-screen first-boot wizard for Armbian images."""

import lvgl as lv

from .armbian_onboarding import ArmbianOnboarding, ValidationError


LOWER_KEYS = (
    tuple("1234567890"),
    tuple("qwertyuiop"),
    tuple("asdfghjkl"),
    tuple("zxcvbnm._-"),
    ("SHIFT", "SPACE", "BACK", "NEXT"),
)

UPPER_KEYS = (
    tuple("!@#$%^&*()"),
    tuple("QWERTYUIOP"),
    tuple("ASDFGHJKL"),
    tuple("ZXCVBNM._-"),
    ("SHIFT", "SPACE", "BACK", "NEXT"),
)

FIELDS = (
    ("root_password", "Root password", "At least 8 characters", True),
    ("root_password_confirm", "Repeat root password", "Enter it again", True),
    ("username", "Your username", "Letters and numbers only", False),
    ("real_name", "Your name", "Shown with your account", False),
    ("user_password", "User password", "At least 8 characters", True),
    ("user_password_confirm", "Repeat user password", "Enter it again", True),
)


class OnboardingApp:
    """Full-screen setup UI displayed before the normal launcher menu."""

    def __init__(self, on_complete, backend=None):
        self.on_complete = on_complete
        self.backend = backend if backend is not None else ArmbianOnboarding()
        self.screen = None
        self.mode = "welcome"
        self.field_index = 0
        self.row = 0
        self.column = 0
        self.shifted = False
        self.error_label = None
        self.answers = {field[0]: "" for field in FIELDS}

    @staticmethod
    def should_start(backend=None):
        backend = backend if backend is not None else ArmbianOnboarding()
        return backend.is_pending()

    def enter(self):
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        self._take_input_focus()
        self._render_welcome()

    def _take_input_focus(self):
        import input
        if input.driver and input.driver.group:
            input.driver.group.set_editing(False)
            input.driver.group.remove_all_objs()
            self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
            self.screen.add_event_cb(self._on_key, lv.EVENT.KEY, None)
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

    def _reset_screen(self):
        self.screen.clean()
        self.error_label = None

    def _label(self, text, y, font=None):
        label = lv.label(self.screen)
        label.set_text(text)
        label.set_width(380)
        label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        if font is not None:
            try:
                label.set_style_text_font(font, 0)
            except Exception:
                pass
        label.align(lv.ALIGN.TOP_MID, 0, y)
        return label

    def _render_welcome(self):
        self.mode = "welcome"
        self._reset_screen()
        self._label("Welcome to BeagleBadge", 35, getattr(lv, "font_montserrat_24", None))
        self._label(
            "Let's secure Armbian and create your daily user account.\n"
            "Everything is completed locally on this badge.",
            100,
            getattr(lv, "font_montserrat_16", None),
        )
        self._draw_action_button("SELECT  Begin setup", 220, True)
        self._refresh()

    def _render_field(self, error=""):
        self.mode = "field"
        self._reset_screen()
        name, title, hint, is_password = FIELDS[self.field_index]
        self._label(
            "BeagleBadge setup  %d/%d" % (self.field_index + 1, len(FIELDS)),
            8,
            getattr(lv, "font_montserrat_14", None),
        )
        self._label(title, 30, getattr(lv, "font_montserrat_20", None))

        value = self.answers[name]
        shown = ("*" * len(value)) if is_password else value
        if len(shown) > 34:
            shown = "..." + shown[-31:]
        value_box = lv.obj(self.screen)
        value_box.set_size(370, 38)
        value_box.align(lv.ALIGN.TOP_MID, 0, 58)
        value_box.set_style_bg_color(lv.color_white(), 0)
        value_box.set_style_border_width(2, 0)
        value_box.set_style_border_color(lv.color_black(), 0)
        value_label = lv.label(value_box)
        value_label.set_text(shown + ("_" if len(value) < 128 else ""))
        value_label.center()

        self.error_label = self._label(
            error if error else hint,
            99,
            getattr(lv, "font_montserrat_12", None),
        )
        self._draw_keyboard()
        self._refresh()

    def _draw_keyboard(self):
        rows = UPPER_KEYS if self.shifted else LOWER_KEYS
        start_y = 121
        row_height = 31
        for row_index, keys in enumerate(rows):
            count = len(keys)
            gap = 3
            available = 382 - gap * (count - 1)
            width = available // count
            start_x = (400 - (width * count + gap * (count - 1))) // 2
            for column_index, key in enumerate(keys):
                button = lv.button(self.screen)
                button.set_size(width, 27)
                button.set_pos(start_x + column_index * (width + gap), start_y + row_index * row_height)
                selected = row_index == self.row and column_index == self.column
                button.set_style_radius(0, 0)
                button.set_style_border_width(1, 0)
                button.set_style_border_color(lv.color_black(), 0)
                button.set_style_bg_color(lv.color_black() if selected else lv.color_white(), 0)
                label = lv.label(button)
                display_key = {"SHIFT": "Shift", "SPACE": "Space", "BACK": "Del", "NEXT": "Next"}.get(key, key)
                label.set_text(display_key)
                label.set_style_text_color(lv.color_white() if selected else lv.color_black(), 0)
                try:
                    label.set_style_text_font(lv.font_montserrat_12, 0)
                except Exception:
                    pass
                label.center()
                button.add_event_cb(lambda event, value=key: self._activate_key(value), lv.EVENT.CLICKED, None)

    def _render_confirmation(self):
        self.mode = "confirm"
        self.row = 0
        self.column = 0
        self._reset_screen()
        self._label("Ready to set up Armbian", 30, getattr(lv, "font_montserrat_24", None))
        self._label(
            "User: %s\nName: %s\n\n"
            "Armbian will create a sudo-enabled account and finish its normal first-login tasks."
            % (self.answers["username"].lower(), self.answers["real_name"].strip()),
            88,
            getattr(lv, "font_montserrat_16", None),
        )
        self._draw_action_button("SELECT  Apply setup", 220, True)
        self._label("BACK  Review answers", 265, getattr(lv, "font_montserrat_12", None))
        self._refresh()

    def _render_applying(self):
        self.mode = "applying"
        self._reset_screen()
        self._label("Setting up your BeagleBadge", 70, getattr(lv, "font_montserrat_24", None))
        self._label(
            "Armbian is securing the root account and creating your user.\n\n"
            "Please keep the badge powered on.",
            145,
            getattr(lv, "font_montserrat_16", None),
        )
        self._refresh()
        lv.async_call(self._complete_setup, None)

    def _render_result(self, result):
        self._reset_screen()
        if result.complete:
            self.mode = "success"
            for key in ("root_password", "root_password_confirm", "user_password", "user_password_confirm"):
                self.answers[key] = ""
            self._label("Your BeagleBadge is ready", 65, getattr(lv, "font_montserrat_24", None))
            self._label(
                "Armbian onboarding completed successfully.\n"
                "Welcome, %s!" % self.answers["real_name"].strip(),
                145,
                getattr(lv, "font_montserrat_16", None),
            )
            self._draw_action_button("SELECT  Open Badge Launcher", 225, True)
        else:
            self.mode = "failure"
            self._label("Setup needs attention", 55, getattr(lv, "font_montserrat_24", None))
            self._label(
                result.message + "\n\nNo completed setup was marked as finished.",
                125,
                getattr(lv, "font_montserrat_16", None),
            )
            self._draw_action_button("SELECT  Retry", 220, True)
            self._label("BACK  Review answers", 265, getattr(lv, "font_montserrat_12", None))
        self._refresh()

    def _draw_action_button(self, text, y, selected):
        button = lv.button(self.screen)
        button.set_size(300, 42)
        button.align(lv.ALIGN.TOP_MID, 0, y)
        button.set_style_radius(0, 0)
        button.set_style_border_width(2, 0)
        button.set_style_border_color(lv.color_black(), 0)
        button.set_style_bg_color(lv.color_black() if selected else lv.color_white(), 0)
        label = lv.label(button)
        label.set_text(text)
        label.set_style_text_color(lv.color_white() if selected else lv.color_black(), 0)
        label.center()

    def _refresh(self):
        try:
            lv.refr_now(None)
        except Exception:
            pass

    def _current_keys(self):
        return UPPER_KEYS if self.shifted else LOWER_KEYS

    def _move(self, row_delta, column_delta):
        rows = self._current_keys()
        self.row = (self.row + row_delta) % len(rows)
        self.column = (self.column + column_delta) % len(rows[self.row])
        self._render_field()

    def _append_character(self, character):
        name = FIELDS[self.field_index][0]
        if len(self.answers[name]) >= 128:
            return
        if name == "username":
            character = character.lower()
        self.answers[name] += character
        self._render_field()

    def _activate_key(self, key):
        if key == "SHIFT":
            self.shifted = not self.shifted
            self._render_field()
        elif key == "SPACE":
            self._append_character(" ")
        elif key == "BACK":
            self._delete_character()
        elif key == "NEXT":
            self._next_field()
        else:
            self._append_character(key)

    def _delete_character(self):
        name = FIELDS[self.field_index][0]
        self.answers[name] = self.answers[name][:-1]
        self._render_field()

    def _field_error(self):
        name = FIELDS[self.field_index][0]
        value = self.answers[name]
        from .armbian_onboarding import validate_password, validate_real_name, validate_username
        if name in ("root_password", "user_password"):
            validate_password(value)
        elif name == "root_password_confirm" and value != self.answers["root_password"]:
            raise ValidationError("Root passwords do not match")
        elif name == "username":
            self.answers[name] = validate_username(value)
        elif name == "real_name":
            self.answers[name] = validate_real_name(value)
        elif name == "user_password_confirm" and value != self.answers["user_password"]:
            raise ValidationError("User passwords do not match")

    def _next_field(self):
        try:
            self._field_error()
        except ValidationError as error:
            self._render_field(str(error))
            return
        if self.field_index + 1 < len(FIELDS):
            self.field_index += 1
            self.row = 0
            self.column = 0
            self.shifted = False
            self._render_field()
        else:
            self._render_confirmation()

    def _previous_field(self):
        if self.field_index > 0:
            self.field_index -= 1
        self.row = 0
        self.column = 0
        self.shifted = False
        self._render_field()

    def _complete_setup(self, _unused):
        try:
            result = self.backend.complete(self.answers)
        except ValidationError as error:
            result = type("Result", (), {"complete": False, "message": str(error)})()
        except Exception as error:
            result = type("Result", (), {"complete": False, "message": "Setup failed: " + str(error)})()
        self._render_result(result)

    def _finish(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
        self.on_complete()

    def _on_key(self, event):
        key = event.get_key()
        if self.mode == "welcome":
            if key in (lv.KEY.ENTER, lv.KEY.RIGHT, 10, 13):
                self._render_field()
            return
        if self.mode == "field":
            previous = getattr(lv.KEY, "PREV", lv.KEY.UP)
            following = getattr(lv.KEY, "NEXT", lv.KEY.DOWN)
            if key in (lv.KEY.UP, previous):
                self._move(-1, 0)
            elif key in (lv.KEY.DOWN, following):
                self._move(1, 0)
            elif key == lv.KEY.LEFT:
                self._move(0, -1)
            elif key == lv.KEY.RIGHT:
                self._move(0, 1)
            elif key in (lv.KEY.ENTER, 10, 13):
                self._activate_key(self._current_keys()[self.row][self.column])
            elif key in (lv.KEY.BACKSPACE, 8, 14):
                self._delete_character()
            elif key == lv.KEY.ESC:
                self._previous_field()
            elif isinstance(key, int) and 32 <= key <= 126:
                self._append_character(chr(key))
            return
        if self.mode == "confirm":
            if key in (lv.KEY.ENTER, lv.KEY.RIGHT, 10, 13):
                self._render_applying()
            elif key in (lv.KEY.ESC, lv.KEY.LEFT, lv.KEY.BACKSPACE, 8, 14):
                self.field_index = len(FIELDS) - 1
                self.row = 0
                self.column = 0
                self.shifted = False
                self._render_field()
            return
        if self.mode == "failure":
            if key in (lv.KEY.ENTER, lv.KEY.RIGHT, 10, 13):
                self._render_applying()
            elif key in (lv.KEY.ESC, lv.KEY.LEFT, lv.KEY.BACKSPACE, 8, 14):
                self.field_index = len(FIELDS) - 1
                self.row = 0
                self.column = 0
                self.shifted = False
                self._render_field()
            return
        if self.mode == "success" and key in (lv.KEY.ENTER, lv.KEY.RIGHT, 10, 13):
            self._finish()
