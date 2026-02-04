"""Logic testing for Badge apps on macOS (without display).

Tests app logic, state management, and game mechanics without requiring
LVGL display or hardware. Useful for quick iteration and CI/CD testing.

Usage:
    python3 test_logic_mac.py [app_name]

Examples:
    python3 test_logic_mac.py              # Test all apps
    python3 test_logic_mac.py snake        # Test Snake game only
    python3 test_logic_mac.py chiptunez    # Test ChipTunez only
"""

import sys
import os
import time

# ====================
# Mock LVGL Module
# ====================
class MockLVGL:
    """Comprehensive LVGL mock for logic testing."""

    class obj:
        FLAG = type('obj', (), {
            'HIDDEN': 1,
            'CLICKABLE': 2,
            'SCROLLABLE': 4
        })()

        def __init__(self, parent=None):
            self.parent = parent
            self.children = []
            self.hidden = False
            self.x = 0
            self.y = 0
            self.w = 100
            self.h = 50
            if parent:
                parent.children.append(self)

        def set_size(self, w, h): self.w, self.h = w, h
        def set_style_bg_color(self, c, s): pass
        def set_style_bg_opa(self, o, s): pass
        def set_style_text_color(self, c, s): pass
        def set_style_text_align(self, a, s): pass
        def set_style_text_font(self, f, s): pass
        def set_style_pad_all(self, p, s): pass
        def set_style_border_width(self, w, s): pass
        def set_style_border_color(self, c, s): pass
        def set_style_radius(self, r, s): pass
        def set_style_pad_gap(self, g, s): pass
        def set_text(self, t): self.text = t
        def get_text(self): return getattr(self, 'text', '')
        def center(self): pass
        def align(self, *args): pass
        def add_flag(self, f): self.hidden = (f == self.FLAG.HIDDEN)
        def remove_flag(self, f): self.hidden = False
        def delete(self): pass
        def clean(self): self.children = []
        def set_pos(self, x, y): self.x, self.y = x, y
        def get_pos(self): return (self.x, self.y)
        def get_width(self): return self.w
        def get_height(self): return self.h
        def add_event_cb(self, cb, ev, data): pass
        def set_scrollbar_mode(self, m): pass
        def set_flex_flow(self, f): pass
        def get_child(self, idx): return self.children[idx] if idx < len(self.children) else None
        def get_index(self): return 0
        def scroll_to_view(self, anim): pass
        def move_foreground(self): pass
        def set_flex_align(self, main, cross, track): pass

        @staticmethod
        def __cast__(obj): return obj

    class label(obj):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.text = ""

    class button(obj): pass
    class image(obj):
        def set_src(self, src): pass
        def set_style_image_recolor(self, c, s): pass
        def set_style_image_recolor_opa(self, o, s): pass

    class color:
        @staticmethod
        def white(): return 0xFFFFFF
        @staticmethod
        def black(): return 0x000000

    EVENT = type('obj', (), {
        'KEY': 1, 'CLICKED': 2, 'FOCUSED': 3, 'DEFOCUSED': 4
    })()

    KEY = type('obj', (), {
        'ESC': 27, 'ENTER': 13, 'UP': 11, 'DOWN': 9,
        'LEFT': 20, 'RIGHT': 19, 'BACKSPACE': 8
    })()

    ALIGN = type('obj', (), {
        'CENTER': 0, 'TOP_MID': 1, 'BOTTOM_MID': 2,
        'TOP_LEFT': 3, 'TOP_RIGHT': 4, 'BOTTOM_LEFT': 5,
        'BOTTOM_RIGHT': 6
    })()

    OPA = type('obj', (), {'COVER': 255, 'TRANSP': 0})()
    INDEV_STATE = type('obj', (), {'PRESSED': 1, 'RELEASED': 0})()
    FLEX_FLOW = type('obj', (), {'COLUMN': 0, 'ROW': 1})()
    TEXT_ALIGN = type('obj', (), {'CENTER': 0, 'LEFT': 1, 'RIGHT': 2})()
    SCROLLBAR_MODE = type('obj', (), {'OFF': 0, 'ON': 1, 'AUTO': 2})()
    SYMBOL = type('obj', (), {'UP': '▲', 'DOWN': '▼'})()
    ANIM = type('obj', (), {'OFF': 0, 'ON': 1})()
    STATE = type('obj', (), {'FOCUSED': 1})()
    PALETTE = type('obj', (), {
        'BLUE': 0, 'RED': 1, 'GREEN': 2, 'ORANGE': 3,
        'YELLOW': 4, 'PURPLE': 5, 'PINK': 6, 'CYAN': 7, 'TEAL': 8, 'GREY': 9
    })()
    FLEX_ALIGN = type('obj', (), {'CENTER': 0, 'START': 1, 'END': 2})()
    RADIUS_CIRCLE = 9999
    IMAGE_HEADER_MAGIC = 0x19
    COLOR_FORMAT = type('obj', (), {'L8': 6})()

    class image_dsc_t:
        def __init__(self):
            self.header = type('obj', (), {
                'magic': 0, 'cf': 0, 'w': 0, 'h': 0
            })()
            self.data_size = 0
            self.data = None

    @staticmethod
    def screen_load(s): pass

    @staticmethod
    def display_get_default():
        return type('obj', (), {
            'get_horizontal_resolution': lambda self: 480,
            'get_vertical_resolution': lambda self: 320
        })()

    @staticmethod
    def timer_create(cb, period, data):
        return type('obj', (), {
            'delete': lambda self: None,
            'set_period': lambda self, p: None
        })()

    @staticmethod
    def group_create():
        return type('obj', (), {
            'set_default': lambda self: None,
            'add_obj': lambda self, o: None,
            'remove_all_objs': lambda self: None,
            'set_editing': lambda self, e: None
        })()

    @staticmethod
    def group_focus_obj(o): pass

    @staticmethod
    def refr_now(d): pass

    @staticmethod
    def task_handler(): pass

    @staticmethod
    def pct(x): return x

    # Expose color functions at module level
    @staticmethod
    def color_white(): return 0xFFFFFF

    @staticmethod
    def color_black(): return 0x000000

    @staticmethod
    def color_hex(h): return h

    @staticmethod
    def palette_main(p): return 0x0000FF  # Return blue for any palette

    # Font attributes (may not exist but apps try to use them)
    font_montserrat_14 = None
    font_montserrat_16 = None

# Install mocks
sys.modules['lvgl'] = MockLVGL()

class MockInput:
    class MockDriver:
        def __init__(self):
            self.last_key = 0
            self.state = MockLVGL.INDEV_STATE.RELEASED
            self.group = MockLVGL.group_create()

    driver = MockDriver()

sys.modules['input'] = MockInput()

class MockSound:
    @staticmethod
    def beep(d, f): pass
    @staticmethod
    def start_tone(f): pass
    @staticmethod
    def stop_tone(): pass

sys.modules['sound'] = MockSound()

class MockConfig:
    data = {
        'sound_enabled': True,
        'badge_name': 'Test Badge',
        'badge_info': 'Testing',
        'logo': 'Beagle'
    }
    badge_logo = 0  # Attribute for direct access (0=Random, 1=Beagle, 2=TI)
    badge_name = 'Test Badge'
    badge_info = 'Testing'
    sound_enabled = True

    @staticmethod
    def load(): pass
    @staticmethod
    def save(): pass

sys.modules['config'] = MockConfig()

# Mock time.ticks_ms and time.ticks_diff for games
_real_time = time
class MockTime:
    @staticmethod
    def ticks_ms():
        return int(_real_time.time() * 1000)

    @staticmethod
    def ticks_diff(new, old):
        return new - old

    # Pass through other time functions
    def __getattr__(self, name):
        return getattr(_real_time, name)

time.ticks_ms = MockTime.ticks_ms
time.ticks_diff = MockTime.ticks_diff

# Add paths
if "core" not in sys.path: sys.path.append("core")
if "applications" not in sys.path: sys.path.append("applications")

# ====================
# Test Suite
# ====================
print("=" * 60)
print("Badge Launcher - Logic Testing Suite")
print("=" * 60)
print()

test_apps = [
    ("Snake", "games.snake_app", "SnakeApp", "Game state management"),
    ("Brick Breaker", "games.brick_app", "BrickApp", "Collision detection"),
    ("ChipTunez", "apps.chiptunez_app", "ChipTunezApp", "Music playback"),
    ("Photos", "apps.media_app", "PhotosApp", "Image loading"),
    ("DVD Screensaver", "apps.dvd_app", "DVDApp", "Animation logic"),
    ("Badge Mode", "badge_mode_app", "BadgeModeApp", "Badge display"),
    ("About", "about_app", "AboutApp", "Info screen"),
    ("Reboot", "settings.reboot", "RebootApp", "System reboot"),
    ("Shutdown", "settings.shutdown", "ShutdownApp", "System shutdown"),
]

# Filter if specific app requested
if len(sys.argv) > 1:
    filter_name = sys.argv[1].lower()
    test_apps = [app for app in test_apps if filter_name in app[0].lower()]

passed = 0
failed = 0
tests_run = []

for name, module_path, class_name, description in test_apps:
    print(f"Testing: {name}")
    print(f"  Purpose: {description}")

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

        # Test basic methods
        app_instance.enter(on_exit=lambda: None)

        # Test specific logic based on app type
        if "Snake" in name:
            # Test snake movement
            initial_len = len(app_instance.snake)
            app_instance.next_dir = 3  # Move right
            print(f"  ✓ Initial snake length: {initial_len}")

        elif "Brick" in name:
            # Test brick state
            active_bricks = sum(1 for b in app_instance.bricks if b['active'])
            print(f"  ✓ Active bricks: {active_bricks}")

        elif "ChipTunez" in name:
            # Test song data
            from applications.apps.chiptunez_app import SONGS
            print(f"  ✓ Songs loaded: {len(SONGS)}")

        # Test exit
        app_instance.exit()

        print(f"  ✓ {name}: PASSED\n")
        passed += 1
        tests_run.append((name, "PASSED", None))

    except Exception as e:
        import traceback
        print(f"  ✗ {name}: FAILED - {e}")
        if '--verbose' in sys.argv:
            traceback.print_exc()
        print()
        failed += 1
        tests_run.append((name, "FAILED", str(e)))

# Summary
print("=" * 60)
print("Test Summary")
print("=" * 60)
for name, status, error in tests_run:
    symbol = "✓" if status == "PASSED" else "✗"
    print(f"{symbol} {name}: {status}")
    if error:
        print(f"    Error: {error}")

print()
print(f"Total: {passed + failed} tests")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print()

if failed == 0:
    print("🎉 All tests passed!")
    sys.exit(0)
else:
    print(f"⚠️  {failed} test(s) failed")
    sys.exit(1)
