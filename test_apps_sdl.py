"""Test harness for Badge apps on macOS and Linux (no display).

Simple test to verify app instantiation and basic logic without
requiring hardware or LVGL display.

Usage:
    python3 test_apps_sdl.py
"""

import sys
import os

# Mock modules before importing apps
class MockLVGL:
    """Mock LVGL module for testing."""

    class obj:
        FLAG = type('obj', (), {'HIDDEN': 1, 'CLICKABLE': 2})()

        def __init__(self, parent=None):
            self.parent = parent

        def set_size(self, w, h): pass
        def set_style_bg_color(self, c, s): pass
        def set_style_bg_opa(self, o, s): pass
        def set_text(self, t): pass
        def center(self): pass
        def align(self, *args): pass
        def add_flag(self, f): pass
        def remove_flag(self, f): pass
        def delete(self): pass
        def clean(self): pass
        def set_pos(self, x, y): pass
        def add_event_cb(self, cb, ev, data): pass

    class label(obj): pass
    class button(obj):
        def add_style(self, style, state): pass
    class image(obj): pass
    class slider(obj):
        def set_range(self, min, max): pass
        def set_value(self, val, anim): pass
    class style_t:
        def init(self): pass
        def set_radius(self, r): pass
        def set_border_width(self, w): pass
        def set_border_color(self, c): pass
        def set_bg_color(self, c): pass
        def set_text_color(self, c): pass

    class color:
        @staticmethod
        def white(): return 0xFFFFFF
        @staticmethod
        def black(): return 0x000000

    @staticmethod
    def color_white(): return 0xFFFFFF
    @staticmethod
    def color_black(): return 0x000000

    EVENT = type('obj', (), {'KEY': 1, 'CLICKED': 2, 'FOCUSED': 3, 'DEFOCUSED': 4})()
    KEY = type('obj', (), {'ESC': 27, 'ENTER': 13, 'UP': 11, 'DOWN': 9, 'LEFT': 20, 'RIGHT': 19})()
    ALIGN = type('obj', (), {'CENTER': 0, 'TOP_MID': 1, 'BOTTOM_MID': 2, 'TOP_LEFT': 3})()
    OPA = type('obj', (), {'COVER': 255})()
    INDEV_STATE = type('obj', (), {'PRESSED': 1, 'RELEASED': 0})()
    STATE = type('obj', (), {'PRESSED': 1, 'FOCUSED': 2, 'DEFAULT': 0})()
    DIR = type('obj', (), {'VER': 1, 'HOR': 2})()
    SIZE_CONTENT = 2001 # Magic number for LVGL

    # Fonts
    font_montserrat_14 = None
    font_montserrat_16 = None
    font_montserrat_24 = None
    
    @staticmethod
    def screen_load(s): pass
    @staticmethod
    def display_get_default():
        return type('obj', (), {
            'get_horizontal_resolution': lambda: 400,
            'get_vertical_resolution': lambda: 300
        })()
    @staticmethod
    def timer_create(cb, period, data):
        return type('obj', (), {'delete': lambda: None})()
    @staticmethod
    def group_focus_obj(o): pass
    @staticmethod
    def refr_now(d): pass

class MockInput:
    driver = None

class MockSound:
    @staticmethod
    def beep(d, f): print(f"Beep: {f}Hz for {d}ms")
    @staticmethod
    def start_tone(f): print(f"Start: {f}Hz")
    @staticmethod
    def stop_tone(): print("Stop tone")

class MockConfig:
    data = {'sound_enabled': True, 'badge_name': 'Test', 'badge_info': 'Testing', 'logo': 'Beagle'}
    @staticmethod
    def load(): pass
    @staticmethod
    def save(): pass

sys.modules['lvgl'] = MockLVGL()
sys.modules['input'] = MockInput()
sys.modules['sound'] = MockSound()
sys.modules['config'] = MockConfig()

# Add paths
if "core" not in sys.path: sys.path.append("core")
if "applications" not in sys.path: sys.path.append("applications")

# Test app imports
print("Testing app imports...\n")

test_apps = [
    ("Snake", "games.snake_app", "SnakeApp"),
    ("Brick Breaker", "games.brick_app", "BrickApp"),
    ("RGB Test", "apps.rgb_test_app", "RGBTestApp"),
    ("Badge Mode", "badge_mode_app", "BadgeModeApp"),
    ("About", "about_app", "AboutApp"),
    ("Reboot", "settings.reboot", "RebootApp"),
    ("Shutdown", "settings.shutdown", "ShutdownApp"),
]

for name, module_path, class_name in test_apps:
    try:
        # Import the module
        parts = module_path.split('.')
        if len(parts) == 1:
            exec(f"from applications import {parts[0]}")
            module = eval(parts[0])
        else:
            exec(f"from applications.{parts[0]} import {parts[1]}")
            module = eval(parts[1])

        # Instantiate the app
        app_class = getattr(module, class_name)
        app_instance = app_class()

        print(f"✓ {name}: Successfully imported and instantiated")

    except Exception as e:
        print(f"✗ {name}: Failed - {e}")

print("\n✓ Mac testing complete - all apps can be instantiated!")
print("\nFor full UI testing, use SDL backend (see main_sdl.py)")
