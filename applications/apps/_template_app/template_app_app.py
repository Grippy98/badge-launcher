"""Template App - Copy this to create your own app!

This is a template for creating folder-based badge applications.
To use this template:
1. Copy the entire _template_app folder
2. Rename it (remove the underscore)
3. Rename this file to match: {foldername}_app.py
4. Update the class name and app details
5. Implement your app logic in the enter() method
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app

class TemplateApp(app.App):
    def __init__(self):
        super().__init__("Template App")
        self.screen = None

    def enter(self, on_exit=None):
        """Called when the app is launched.

        Args:
            on_exit: Callback function to call when exiting the app
        """
        self.on_exit_cb = on_exit

        # Create the screen
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        # Add a title label
        title = lv.label(self.screen)
        title.set_text("Template App")
        title.align(lv.ALIGN.TOP_MID, 0, 20)
        title.set_style_text_color(lv.color_black(), 0)

        # Add main content label
        content = lv.label(self.screen)
        content.set_text("Replace this with\nyour app content!")
        content.center()
        content.set_style_text_color(lv.color_black(), 0)

        # Add instructions
        instructions = lv.label(self.screen)
        instructions.set_text("Press ESC to exit")
        instructions.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        instructions.set_style_text_color(lv.color_black(), 0)

        # Setup input handling
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

    def on_key(self, e):
        """Handle keyboard events."""
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb:
                self.on_exit_cb()

    def exit(self):
        """Clean up and exit the app."""
        if self.screen:
            self.screen.delete()
            self.screen = None
