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
    ("root_password", "Pick a root password", "Use Show to review as you type", True),
    ("username", "Your username", "Letters and numbers only", False),
    ("user_password", "User password", "Enter one or choose Root", True),
)

STAGES = (
    ("Root", 52),
    ("Username", 82),
    ("Password", 82),
    ("Review", 64),
)

KEYBOARD_START_Y = 144
KEYBOARD_ROW_HEIGHT = 31
KEYBOARD_KEY_HEIGHT = 27
FIELD_DIVIDER_Y = 29


def _display_name(username):
    """Capitalize a normalized username using MicroPython string methods."""
    return username[:1].upper() + username[1:]


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
        self.password_visible = False
        self.error_label = None
        self.answers = {field[0]: "" for field in FIELDS}
        self.answers["real_name"] = ""

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
            self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
            self.screen.add_event_cb(self._on_key, lv.EVENT.KEY, None)
            self._restore_input_focus()

    def _restore_input_focus(self):
        """Keep the wizard as the sole keypad target after a redraw.

        The launcher input group is LVGL's default group, so widgets created
        while rendering are added to it automatically.  Without resetting the
        group, the first navigation key can move focus from the screen to a
        decorative keyboard button and subsequent keys never reach _on_key().
        """
        import input
        if input.driver and input.driver.group and self.screen:
            input.driver.group.set_editing(False)
            input.driver.group.remove_all_objs()
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

    def _draw_stage_line(self, current):
        arrow_width = 12
        gap = 2
        total_width = sum(stage[1] for stage in STAGES)
        total_width += arrow_width * (len(STAGES) - 1)
        total_width += gap * (len(STAGES) * 2 - 2)
        x = (400 - total_width) // 2

        for index, (name, width) in enumerate(STAGES):
            stage = lv.obj(self.screen)
            stage.set_size(width, 24)
            stage.set_pos(x, 2)
            stage.set_style_radius(0, 0)
            stage.set_style_border_width(1, 0)
            stage.set_style_border_color(lv.color_black(), 0)
            stage.set_style_pad_all(0, 0)
            selected = index == current
            stage.set_style_bg_color(lv.color_black() if selected else lv.color_white(), 0)
            label = lv.label(stage)
            label.set_text(name)
            label.set_style_text_color(lv.color_white() if selected else lv.color_black(), 0)
            try:
                label.set_style_text_font(lv.font_montserrat_12, 0)
            except Exception:
                pass
            label.center()
            x += width

            if index + 1 < len(STAGES):
                x += gap
                arrow = lv.label(self.screen)
                arrow.set_text(">")
                arrow.set_width(arrow_width)
                arrow.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
                try:
                    arrow.set_style_text_font(lv.font_montserrat_12, 0)
                except Exception:
                    pass
                arrow.set_pos(x, 6)
                x += arrow_width + gap

    def _draw_field_divider(self):
        divider = lv.obj(self.screen)
        divider.set_size(380, 1)
        divider.align(lv.ALIGN.TOP_MID, 0, FIELD_DIVIDER_Y)
        divider.set_style_border_width(0, 0)
        divider.set_style_bg_color(lv.color_black(), 0)

    def _render_welcome(self):
        self.mode = "welcome"
        self._reset_screen()
        self._label("Welcome to BeagleBadge", 35, getattr(lv, "font_montserrat_24", None))
        self._label(
            "Let's secure Armbian and create your daily user account.",
            100,
            getattr(lv, "font_montserrat_16", None),
        )
        version_reader = getattr(self.backend, "system_version", None)
        version = version_reader() if version_reader else "Armbian"
        self._label(
            "System: " + version,
            160,
            getattr(lv, "font_montserrat_14", None),
        )
        self._draw_action_button("Begin Setup", 220, True)
        self._refresh()

    def _render_field(self, error=""):
        self.mode = "field"
        self._reset_screen()
        name, title, hint, is_password = FIELDS[self.field_index]
        self._draw_stage_line(self.field_index)
        self._draw_field_divider()
        self._label(title, 34, getattr(lv, "font_montserrat_20", None))

        value = self.answers[name]
        shown = ("*" * len(value)) if is_password and not self.password_visible else value
        if len(shown) > 34:
            shown = "..." + shown[-31:]
        value_box = lv.obj(self.screen)
        value_box.set_size(370, 38)
        value_box.align(lv.ALIGN.TOP_MID, 0, 62)
        value_box.set_style_bg_color(lv.color_white(), 0)
        value_box.set_style_border_width(2, 0)
        value_box.set_style_border_color(lv.color_black(), 0)
        value_label = lv.label(value_box)
        value_label.set_text(shown + ("_" if len(value) < 128 else ""))
        value_label.center()

        self.error_label = self._label(
            error if error else hint,
            103,
            getattr(lv, "font_montserrat_12", None),
        )
        self._draw_keyboard()
        self._refresh()

    def _draw_keyboard(self):
        rows = self._current_keys()
        for row_index, keys in enumerate(rows):
            count = len(keys)
            gap = 3
            available = 382 - gap * (count - 1)
            width = available // count
            start_x = (400 - (width * count + gap * (count - 1))) // 2
            for column_index, key in enumerate(keys):
                button = lv.button(self.screen)
                button.set_size(width, KEYBOARD_KEY_HEIGHT)
                button.set_pos(
                    start_x + column_index * (width + gap),
                    KEYBOARD_START_Y + row_index * KEYBOARD_ROW_HEIGHT,
                )
                selected = row_index == self.row and column_index == self.column
                button.set_style_radius(0, 0)
                button.set_style_border_width(1, 0)
                button.set_style_border_color(lv.color_black(), 0)
                button.set_style_bg_color(lv.color_black() if selected else lv.color_white(), 0)
                label = lv.label(button)
                display_key = {
                    "SHIFT": "Shift",
                    "SPACE": "Space",
                    "BACK": "Del",
                    "SHOW": "Show",
                    "HIDE": "Hide",
                    "USE_ROOT": "Root",
                    "NEXT": "Next",
                }.get(key, key)
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
        self._draw_stage_line(3)
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
        self._draw_stage_line(3)
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
        self._draw_stage_line(3)
        if result.complete:
            self.mode = "success"
            for key in ("root_password", "user_password"):
                self.answers[key] = ""
            self._label("Your BeagleBadge is ready", 65, getattr(lv, "font_montserrat_24", None))
            self._label(
                "Armbian onboarding completed successfully.\n"
                "Welcome, %s!" % self.answers["real_name"].strip(),
                145,
                getattr(lv, "font_montserrat_16", None),
            )
            self._draw_action_button("Let's Go!", 225, True)
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
        self._restore_input_focus()
        try:
            lv.refr_now(None)
        except Exception:
            pass

    def _current_keys(self):
        rows = UPPER_KEYS if self.shifted else LOWER_KEYS
        if FIELDS[self.field_index][3]:
            visibility_key = "HIDE" if self.password_visible else "SHOW"
            actions = ("SHIFT", "SPACE", "BACK", visibility_key, "NEXT")
            if FIELDS[self.field_index][0] == "user_password":
                actions = ("SHIFT", "SPACE", "BACK", visibility_key, "USE_ROOT", "NEXT")
            return rows[:-1] + (actions,)
        return rows

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
        elif key in ("SHOW", "HIDE"):
            self.password_visible = not self.password_visible
            self._render_field()
        elif key == "USE_ROOT":
            self.answers["user_password"] = self.answers["root_password"]
            self._next_field()
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
        from .armbian_onboarding import validate_password, validate_username
        if name in ("root_password", "user_password"):
            validate_password(value)
        elif name == "username":
            username = validate_username(value)
            self.answers[name] = username
            self.answers["real_name"] = _display_name(username)

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
            self.password_visible = False
            self._render_field()
        else:
            self.password_visible = False
            self._render_confirmation()

    def _previous_field(self):
        if self.field_index > 0:
            self.field_index -= 1
        self.row = 0
        self.column = 0
        self.shifted = False
        self.password_visible = False
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
                self.password_visible = False
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
                self.password_visible = False
                self._render_field()
            return
        if self.mode == "success" and key in (lv.KEY.ENTER, lv.KEY.RIGHT, 10, 13):
            self._finish()
