"""DVD screensaver application.

Bouncing logo screensaver. The logo bounces around the screen.
Use arrow keys to change logos and adjust speed.
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import time
import random

class DVDApp(app.App):
    def __init__(self):
        super().__init__("DVD Screensaver")
        self.screen = None
        self.img_dvd = None

        self.asset_files = ['assets/dvd.bin', 'assets/sleeping.bin', 'assets/ti_logo.bin', 'assets/beagle_logo.bin']
        self.current_asset_idx = 0
        self.dvd_dsc = None

        self.asset_dimensions = {
            'assets/dvd.bin': (90, 65, 19, 35),
            'assets/sleeping.bin': (105, 105, 12, 12),
            'assets/ti_logo.bin': (128, 128, 0, 0),
            'assets/beagle_logo.bin': (128, 128, 0, 0)
        }

        self.x_speed = 2
        self.y_speed = 2

        self.anim_timer = None

    def load_current_asset(self):
        filename = self.asset_files[self.current_asset_idx]
        try:
            with open(filename, 'rb') as f:
                data = f.read()

            dsc = lv.image_dsc_t()
            dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            dsc.header.cf = lv.COLOR_FORMAT.L8
            dsc.header.w = 128
            dsc.header.h = 128
            dsc.data_size = len(data)
            dsc.data = data
            self.dvd_data_ref = data 
            
            self.dvd_dsc = dsc

            if self.img_dvd:
                self.img_dvd.set_src(self.dvd_dsc)
                
        except Exception as e:
            print(f"Failed loading {filename}: {e}")
            self.dvd_dsc = None

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)

        self.screen.set_size(lv.pct(100), lv.pct(100))
        self.screen.set_style_pad_all(0, 0)

        try:
            self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        except:
            pass

        lv.screen_load(self.screen)

        self.load_current_asset()

        self.img_dvd = lv.image(self.screen)
        if self.dvd_dsc:
            self.img_dvd.set_src(self.dvd_dsc)
        else:
            self.img_dvd = lv.label(self.screen)
            self.img_dvd.set_text("?")
            
        self.img_dvd.set_size(128, 128)

        sw = self.screen.get_width()
        sh = self.screen.get_height()
        current_file = self.asset_files[self.current_asset_idx]
        content_w, content_h, offset_x, offset_y = self.asset_dimensions.get(
            current_file, (128, 128, 0, 0)
        )
        max_x = sw - content_w - offset_x
        max_y = sh - content_h - offset_y
        self.img_dvd.set_pos(random.randint(-offset_x, max_x), random.randint(-offset_y, max_y))

        # Input
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        self.anim_timer = lv.timer_create(self.animate, 33, None)

    def change_speed(self, delta):
        mag_x = abs(self.x_speed)
        mag_y = abs(self.y_speed)

        mag_x = max(1, min(10, mag_x + delta))
        mag_y = max(1, min(10, mag_y + delta))

        self.x_speed = mag_x * (1 if self.x_speed >= 0 else -1)
        self.y_speed = mag_y * (1 if self.y_speed >= 0 else -1)
        print(f"Speed: {mag_x}")

    def change_asset(self, delta):
        self.current_asset_idx = (self.current_asset_idx + delta) % len(self.asset_files)
        self.load_current_asset()

    def animate(self, t):
        if not self.img_dvd:
            return

        x = self.img_dvd.get_x()
        y = self.img_dvd.get_y()
        sw = self.screen.get_width()
        sh = self.screen.get_height()

        current_file = self.asset_files[self.current_asset_idx]
        content_w, content_h, offset_x, offset_y = self.asset_dimensions.get(
            current_file, (128, 128, 0, 0)
        )

        new_x = x + self.x_speed
        new_y = y + self.y_speed

        bounced = False

        content_x = new_x + offset_x
        content_y = new_y + offset_y

        if content_x <= 0:
            self.x_speed = abs(self.x_speed)
            new_x = -offset_x
            bounced = True
        elif content_x + content_w >= sw:
            self.x_speed = -abs(self.x_speed)
            new_x = sw - content_w - offset_x
            bounced = True

        if content_y <= 0:
            self.y_speed = abs(self.y_speed)
            new_y = -offset_y
            bounced = True
        elif content_y + content_h >= sh:
            self.y_speed = -abs(self.y_speed)
            new_y = sh - content_h - offset_y
            bounced = True

        self.img_dvd.set_pos(int(new_x), int(new_y))

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb:
                self.on_exit_cb()
        elif key == lv.KEY.LEFT:
            self.change_asset(-1)
        elif key == lv.KEY.RIGHT:
            self.change_asset(1)
        elif key == lv.KEY.UP:
            self.change_speed(1)
        elif key == lv.KEY.DOWN:
            self.change_speed(-1)

    def exit(self):
        if self.anim_timer:
            self.anim_timer.delete()
            self.anim_timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
        self.img_dvd = None
