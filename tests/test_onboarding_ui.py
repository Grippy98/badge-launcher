import sys
import unittest


class MockObject:
    class FLAG:
        CLICKABLE = 1

    def __init__(self, parent=None):
        self.parent = parent
        self.children = []
        self.events = []
        if parent is not None:
            parent.children.append(self)

    def add_event_cb(self, callback, event, data):
        self.events.append((callback, event, data))

    def add_flag(self, _flag):
        pass

    def align(self, *_args):
        pass

    def center(self):
        pass

    def clean(self):
        self.children = []

    def delete(self):
        pass

    def set_pos(self, *_args):
        pass

    def set_size(self, *_args):
        pass

    def set_width(self, *_args):
        pass

    def set_style_bg_color(self, *_args):
        pass

    def set_style_bg_opa(self, *_args):
        pass

    def set_style_border_color(self, *_args):
        pass

    def set_style_border_width(self, *_args):
        pass

    def set_style_radius(self, *_args):
        pass

    def set_style_pad_all(self, *_args):
        pass

    def set_style_text_align(self, *_args):
        pass

    def set_style_text_color(self, *_args):
        pass

    def set_style_text_font(self, *_args):
        pass


class MockLabel(MockObject):
    def set_text(self, text):
        self.text = text


class MockGroup:
    def __init__(self):
        self.objects = []

    def set_editing(self, _editing):
        pass

    def remove_all_objs(self):
        self.objects = []

    def add_obj(self, obj):
        self.objects.append(obj)


class MockLVGL:
    obj = MockObject
    label = MockLabel
    button = MockObject
    OPA = type("OPA", (), {"COVER": 255})()
    EVENT = type("EVENT", (), {"KEY": 1, "CLICKED": 2})()
    KEY = type(
        "KEY",
        (),
        {
            "ENTER": 13,
            "RIGHT": 19,
            "LEFT": 20,
            "UP": 11,
            "DOWN": 9,
            "PREV": 11,
            "NEXT": 9,
            "BACKSPACE": 8,
            "ESC": 27,
        },
    )()
    ALIGN = type("ALIGN", (), {"TOP_MID": 1})()
    TEXT_ALIGN = type("TEXT_ALIGN", (), {"CENTER": 1})()
    font_montserrat_12 = object()
    font_montserrat_14 = object()
    font_montserrat_16 = object()
    font_montserrat_20 = object()
    font_montserrat_24 = object()

    @staticmethod
    def color_white():
        return 0xFFFFFF

    @staticmethod
    def color_black():
        return 0

    @staticmethod
    def screen_load(_screen):
        pass

    @staticmethod
    def group_focus_obj(_obj):
        pass

    @staticmethod
    def refr_now(_display):
        pass

    @staticmethod
    def async_call(callback, value):
        callback(value)


class MockInput:
    driver = type("Driver", (), {"group": MockGroup()})()


sys.modules["lvgl"] = MockLVGL()
sys.modules["input"] = MockInput()

from core.onboarding import (
    FIELDS,
    FIELD_DIVIDER_Y,
    KEYBOARD_KEY_HEIGHT,
    KEYBOARD_ROW_HEIGHT,
    KEYBOARD_START_Y,
    STAGES,
    OnboardingApp,
    _display_name,
)


class Event:
    def __init__(self, key):
        self.key = key

    def get_key(self):
        return self.key


class SuccessfulBackend:
    def __init__(self):
        self.received = None

    def is_pending(self):
        return True

    def complete(self, answers):
        self.received = dict(answers)
        return type("Result", (), {"complete": True, "message": "Setup complete"})()


class OnboardingUiTests(unittest.TestCase):
    def setUp(self):
        MockInput.driver.group = MockGroup()

    def test_successful_wizard_reaches_launcher(self):
        opened = []
        backend = SuccessfulBackend()
        app = OnboardingApp(lambda: opened.append(True), backend=backend)
        app.enter()
        self.assertEqual(app.mode, "welcome")

        app._on_key(Event(MockLVGL.KEY.ENTER))
        self.assertEqual(app.mode, "field")

        values = {
            "root_password": "root-password",
            "username": "BadgeUser",
            "user_password": "user-password",
        }
        for index, field in enumerate(FIELDS):
            app.field_index = index
            app.answers[field[0]] = values[field[0]]
            app._next_field()

        self.assertEqual(app.mode, "confirm")
        app._on_key(Event(MockLVGL.KEY.ENTER))
        self.assertEqual(app.mode, "success")
        self.assertEqual(backend.received["username"], "badgeuser")
        self.assertEqual(backend.received["real_name"], "Badgeuser")

        app._on_key(Event(MockLVGL.KEY.ENTER))
        self.assertEqual(opened, [True])

    def test_short_password_is_accepted_without_confirmation(self):
        app = OnboardingApp(lambda: None, backend=SuccessfulBackend())
        app.enter()
        app.field_index = 0
        app.answers["root_password"] = "x"
        app._next_field()
        self.assertEqual(app.field_index, 1)
        self.assertEqual(app.mode, "field")

    def test_password_can_be_shown_and_hidden(self):
        app = OnboardingApp(lambda: None, backend=SuccessfulBackend())
        app.enter()
        app._on_key(Event(MockLVGL.KEY.ENTER))

        self.assertIn("SHOW", app._current_keys()[-1])
        app._activate_key("SHOW")
        self.assertTrue(app.password_visible)
        self.assertIn("HIDE", app._current_keys()[-1])
        app._activate_key("HIDE")
        self.assertFalse(app.password_visible)

    def test_user_password_can_reuse_root_password(self):
        app = OnboardingApp(lambda: None, backend=SuccessfulBackend())
        app.enter()
        app.field_index = len(FIELDS) - 1
        app.answers["root_password"] = "root-choice"
        app.answers["username"] = "badgeuser"
        app.answers["real_name"] = "Badgeuser"
        app._render_field()

        self.assertIn("USE_ROOT", app._current_keys()[-1])
        app._activate_key("USE_ROOT")

        self.assertEqual(app.answers["user_password"], "root-choice")
        self.assertEqual(app.mode, "confirm")

    def test_progress_line_matches_wizard_stages(self):
        self.assertEqual(
            tuple(stage[0] for stage in STAGES),
            ("Root", "Username", "Password", "Review"),
        )

    def test_display_name_uses_micropython_compatible_operations(self):
        self.assertEqual(_display_name("grippy98"), "Grippy98")

    def test_keyboard_uses_lower_screen_space_without_overflow(self):
        keyboard_bottom = KEYBOARD_START_Y + 4 * KEYBOARD_ROW_HEIGHT + KEYBOARD_KEY_HEIGHT
        self.assertEqual(keyboard_bottom, 295)
        self.assertEqual(300 - keyboard_bottom, 5)

    def test_field_progress_has_divider_and_root_instruction(self):
        self.assertEqual(FIELD_DIVIDER_Y, 29)
        self.assertEqual(FIELDS[0][1], "Pick a root password")

    def test_redraw_restores_screen_as_only_input_target(self):
        app = OnboardingApp(lambda: None, backend=SuccessfulBackend())
        app.enter()
        app._on_key(Event(MockLVGL.KEY.ENTER))

        group = MockInput.driver.group
        group.objects.append(MockObject(app.screen))
        app._on_key(Event(MockLVGL.KEY.RIGHT))

        self.assertEqual(group.objects, [app.screen])
        self.assertEqual(app.column, 1)


if __name__ == "__main__":
    unittest.main()
