"""Badge Launcher - SDL version for development on macOS/Linux desktop.

Provides full UI testing with SDL display backend, allowing development
and testing without physical badge hardware.

Requirements:
    Build MicroPython with LVGL using setup_sdl_dev.sh (works on Linux too)
    Run with: micropython-lvgl main_sdl.py

Controls:
    Arrow Keys: Navigate menu/games
    Enter: Select
    Escape: Back/Exit
    Mouse: Click to interact
"""

import lvgl as lv
import sys
import os
import time

# Badge resolution (adjust to match your actual badge)
WIDTH = 400
HEIGHT = 300

# Initialize SDL via LVGL
lv.init()
disp = lv.sdl_window_create(WIDTH, HEIGHT)
mouse = lv.sdl_mouse_create()
keyboard = lv.sdl_keyboard_create()

# Create input group and associate keyboard with it
input_group = lv.group_create()
input_group.set_default()

# Set keyboard to use the group for automatic navigation
if hasattr(keyboard, 'set_group'):
    keyboard.set_group(input_group)
    print("Keyboard connected to input group - arrow keys will navigate automatically")

# Debug: Add a callback to see ALL key events
def global_key_debug(e):
    code = e.get_code()
    if code == lv.EVENT.KEY:
        key = e.get_key()
        key_names = {
            lv.KEY.UP: "UP", lv.KEY.DOWN: "DOWN",
            lv.KEY.LEFT: "LEFT", lv.KEY.RIGHT: "RIGHT",
            lv.KEY.ENTER: "ENTER", lv.KEY.ESC: "ESC"
        }
        print(f"[DEBUG] Key event: {key_names.get(key, f'code={key}')}")

# Add event to the active screen to catch all keys
lv.screen_active().add_event_cb(global_key_debug, lv.EVENT.KEY, None)

print("SDL Display initialized")
print(f"Resolution: {WIDTH}x{HEIGHT}")
print("Controls: Arrow Keys (navigate), Enter (select), Escape (back)")

# ====================
# Mock Input Driver
# ====================
class SDLInputDriver:
    """SDL-based input driver that mimics badge button behavior."""

    def __init__(self):
        self.last_key = 0
        self.state = lv.INDEV_STATE.RELEASED
        self.group = input_group  # Use the SDL keyboard's group
        print("SDL Input driver initialized")

    def update(self):
        """Called by main loop to update input state."""
        # SDL keyboard updates happen automatically via LVGL bindings
        pass

# Create global input driver
class MockInputModule:
    def __init__(self):
        self.driver = SDLInputDriver()

sys.modules['input'] = MockInputModule()

# ====================
# Mock Sound Driver
# ====================
# Create a mock module object with direct methods to avoid indirection issues
class MockSoundModule:
    """Mock sound module that prints to console."""

    def __init__(self):
        self.enabled = True
        self.driver = self  # Some apps may access sound.driver

    def beep(self, duration_ms, freq):
        """Module-level beep function to match real driver.

        Args:
            duration_ms: Tone duration in milliseconds
            freq: Tone frequency in Hz
        """
        # Print compact sound notifications based on frequency
        if not self.enabled:
            return
        if freq > 2000:
            print("🔊♪")
        elif freq > 1000:
            print("🔊♫")
        else:
            print("🔊♬")

    def start_tone(self, freq):
        """Module-level start_tone function to match real driver."""
        pass

    def stop_tone(self):
        """Module-level stop_tone function to match real driver."""
        pass

    def init(self):
        """Module-level init function to match real driver."""
        return self

sys.modules['sound'] = MockSoundModule()

# ====================
# Mock TTY Driver
# ====================
class MockTTY:
    """Mock TTY driver (no-op on Mac)."""

    @staticmethod
    def init():
        print("TTY init (mocked)")

    @staticmethod
    def cleanup():
        print("TTY cleanup (mocked)")

sys.modules['tty'] = MockTTY()

# ====================
# Mock System Files
# ====================
# Note: MicroPython doesn't have builtins module, so we can't easily mock open()
# Apps that read /proc or /sys files will need to handle FileNotFoundError gracefully
# For now, we'll create a mock module that apps can import

# Add os.sync() if it doesn't exist (MicroPython Unix port doesn't have it)
# We need to wrap the module since MicroPython modules are read-only
if not hasattr(os, 'sync'):
    import sys
    _original_os = os

    class OSWrapper:
        def __getattr__(self, name):
            if name == 'sync':
                return lambda: None  # No-op sync
            return getattr(_original_os, name)

    os = OSWrapper()
    sys.modules['os'] = os
    print("Added os.sync() mock via wrapper")

# ====================
# Mock Network Commands (if needed by apps)
# ====================
# Note: MicroPython's os module is read-only, so we can't mock os.popen
# Apps that need network status will need to handle missing popen gracefully

# ====================
# Start Badge Application
# ====================
print("\nStarting Badge Launcher...\n")

# Add core to path
if "core" not in sys.path:
    sys.path.insert(0, "core")

# Import core modules
import config
from core import menu, statusbar, bottombar

# Initialize config
config.load()

# Note: MenuApp creates its own status and bottom bars
# Don't create them here to avoid duplication!

# Create and show main menu
main_menu = menu.MenuApp()
main_menu.enter()

print("\n✓ Badge Launcher started successfully!")
print("  Use arrow keys to navigate, Enter to select, Escape to exit")
print("  Sound events shown as: 🔊♪♫♬\n")

# ====================
# Main Loop
# ====================
try:
    while True:
        # Handle LVGL tasks (includes display refresh)
        lv.task_handler()

        # Delay to prevent 100% CPU usage and reduce flashing
        # E-Ink displays refresh slowly, so we can use a slower rate too
        time.sleep(0.05)  # 50ms delay = ~20 FPS max

except KeyboardInterrupt:
    print("\n\nShutting down...")
    sys.exit(0)
