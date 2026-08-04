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
    def set_editing(self, _editing):
        pass

    def remove_all_objs(self):
        pass

    def add_obj(self, _obj):
        pass


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

from core.onboarding import FIELDS, OnboardingApp


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
            "root_password_confirm": "root-password",
            "username": "BadgeUser",
            "real_name": "Badge User",
            "user_password": "user-password",
            "user_password_confirm": "user-password",
        }
        for index, field in enumerate(FIELDS):
            app.field_index = index
            app.answers[field[0]] = values[field[0]]
            app._next_field()

        self.assertEqual(app.mode, "confirm")
        app._on_key(Event(MockLVGL.KEY.ENTER))
        self.assertEqual(app.mode, "success")
        self.assertEqual(backend.received["username"], "badgeuser")

        app._on_key(Event(MockLVGL.KEY.ENTER))
        self.assertEqual(opened, [True])

    def test_mismatched_confirmation_stays_on_field(self):
        app = OnboardingApp(lambda: None, backend=SuccessfulBackend())
        app.enter()
        app.field_index = 1
        app.answers["root_password"] = "root-password"
        app.answers["root_password_confirm"] = "wrong-password"
        app._next_field()
        self.assertEqual(app.field_index, 1)
        self.assertEqual(app.mode, "field")


if __name__ == "__main__":
    unittest.main()
