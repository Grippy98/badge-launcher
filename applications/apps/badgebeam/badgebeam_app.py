"""BadgeBeam app for receiving and displaying images from the WebBLE app.

Listens for the latest.bin file updated by the background BLE service.
"""

import lvgl as lv
import sys
import os

if "core" not in sys.path:
    sys.path.append("core")
from core import app

class BadgeBeamApp(app.App):
    def __init__(self):
        super().__init__("BadgeBeam")
        self.screen = None
        self.on_exit_cb = None
        self.img_obj = None
        self.img_dsc = None
        
        # Path to the data payload updated by DBus service
        self.data_path = "applications/apps/badgebeam/latest.bin"
        
        # Timer to auto-refresh the display when the file is updated
        self.refresh_timer = None
        self.last_mtime = 0

    def load_image(self):
        try:
            with open(self.data_path, 'rb') as f:
                data = f.read()

            if len(data) != 15000:
                print(f"BadgeBeam: Image size is {len(data)}, expected 15000 bytes.")
                return None

            dsc = lv.image_dsc_t()
            dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            dsc.header.cf = lv.COLOR_FORMAT.I1  # 1-bit color format
            dsc.header.w = 400
            dsc.header.h = 300
            dsc.data_size = len(data) + 8
            
            # I1 format requires a palette of 2 colors (4 bytes per color: blue, green, red, alpha)
            # Palettes are typically BGR in little-endian.
            # Color 0 (Black): 0x00 0x00 0x00 0xFF
            # Color 1 (White): 0xFF 0xFF 0xFF 0xFF
            palette = b'\x00\x00\x00\xFF\xFF\xFF\xFF\xFF'
            
            # Combine palette and raw pixel data
            dsc.data = palette + data
            return dsc
            
        except OSError:
            # File doesn't exist yet
            return None

    def refresh_check(self, timer):
        try:
            st = os.stat(self.data_path)
            new_mtime = st[8] # mtime is usually index 8 in micropython os.stat
            if new_mtime != self.last_mtime:
                self.last_mtime = new_mtime
                print("BadgeBeam: Detected new image payload, refreshing...")
                
                # Load the new descriptor
                new_dsc = self.load_image()
                if new_dsc:
                    self.img_dsc = new_dsc
                    if self.img_obj:
                        self.img_obj.set_src(self.img_dsc)
        except OSError:
            pass

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        
        # Add a full screen image object
        self.img_obj = lv.image(self.screen)
        self.img_obj.align(lv.ALIGN.CENTER, 0, 0)
        
        # Initial load
        self.img_dsc = self.load_image()
        if self.img_dsc:
            self.img_obj.set_src(self.img_dsc)
            
            # Initialize mtime
            try:
                self.last_mtime = os.stat(self.data_path)[8]
            except Exception:
                pass
        else:
            # Fallback text if no image has been sent yet
            lbl = lv.label(self.screen)
            lbl.set_text("Waiting for Beam...")
            lbl.align(lv.ALIGN.CENTER, 0, 0)
            
            hint = lv.label(self.screen)
            hint.set_text("Open BadgeBeam app on phone and connect")
            hint.align(lv.ALIGN.BOTTOM_MID, 0, -10)
            try:
                hint.set_style_text_font(lv.font_montserrat_14, 0)
            except:
                pass

        lv.screen_load(self.screen)

        # Setup input group
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        # Start periodic check for new payloads (every 1 second)
        self.refresh_timer = lv.timer_create(self.refresh_check, 1000, None)

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb:
                self.on_exit_cb()

    def exit(self):
        if self.refresh_timer:
            self.refresh_timer.delete()
            self.refresh_timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
