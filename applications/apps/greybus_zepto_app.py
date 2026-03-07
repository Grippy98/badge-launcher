import os
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import lvgl as lv


def make_led_cb(e):
    obj = e.get_target_obj()
    val = "1" if obj.has_state(lv.STATE.CHECKED) else "0"
    print(val)

class GreybusZeptoApp(app.App):
    def __init__(self):
        super().__init__("Greybus Zepto")
        self.screen = None
        
        self.node_path = "/sys/devices/platform/greybus-i2c-host/greybus1/1-0/1-0.0"
        self.led = self.node_path + "/1-0.0.1/leds"
        self.led_pwm = self.node_path + "/1-0.0.2/leds"
        self.controls = []

    def enter(self, on_exit=None):
        self.on_exit = on_exit

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        # Main Layout: Column
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        cont.set_style_pad_all(10, 0) # Reduced padding
        cont.set_style_pad_gap(5, 0) # Reduced gap
        cont.set_style_border_width(0, 0)

        # Enable scrolling for the container if needed
        cont.set_scroll_dir(lv.DIR.VER)

        # Title
        title = lv.label(cont)
        title.set_text("Greybus Zepto")
        try:
            title.set_style_text_font(lv.font_montserrat_16, 0)
        except: pass

        leds = self.populate_leds(self.led)
        for (name, path) in leds:
            row = lv.obj(cont)
            row.set_size(lv.pct(80), lv.pct(20))
            row.set_flex_flow(lv.FLEX_FLOW.ROW)
            row.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
            row.set_style_border_width(0, 0)

            label = lv.label(row)
            label.set_text(name)

            sw = lv.switch(row)
            sw.add_event_cb(self.make_led_cb(path), lv.EVENT.VALUE_CHANGED, None)
            
            self.controls.append(sw)

        leds = self.populate_leds_max_brightness(self.led_pwm)
        for (name, path, max_brightness, cur_brightness) in leds:
            cur_per = int((cur_brightness * 100) / max_brightness)

            label = lv.label(cont)
            label.set_text(f"{name}")

            slider = lv.slider(cont)
            slider.set_range(0, max_brightness)
            slider.set_value(cur_per, 0)
            slider.add_event_cb(self.make_slider_cb(path, max_brightness), lv.EVENT.VALUE_CHANGED, None)

            self.controls.append(slider)

        # Setup input handling
        import input
        if input.driver and input.driver.group:
            # input.driver.group.remove_all_objs()
            # input.driver.group.add_obj(self.screen)
            # lv.group_focus_obj(self.screen)
            g = input.driver.group
            g.remove_all_objs()
            
            # Add all controls to group
            for obj in self.controls:
                g.add_obj(obj)
            
            # Focus first button (Slider now)
            if self.controls:
                lv.group_focus_obj(self.controls[0])

        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

    def make_led_cb(self, brightness_path):
        def cb(e):
            sw = e.get_target_obj()
            val = "1" if sw.has_state(lv.STATE.CHECKED) else "0"
            with open(brightness_path, 'w') as f:
                f.write(val)

        return cb

    def make_slider_cb(self, brightness_path, max_brightness):
        def cb(e):
            slider = e.get_target_obj()
            val = slider.get_value()
            brightness = int((val / 100) * max_brightness)
            with open(brightness_path, 'w') as f:
                f.write(str(brightness))

        return cb

    def populate_leds(self, base_path):
        res = []
        for fname in os.listdir(base_path):
            brightness = f"{base_path}/{fname}/brightness"
            res.append((fname, brightness))

        return res

    def populate_leds_max_brightness(self, base_path):
        res = []
        for fname in os.listdir(base_path):
            brightness_path = f"{base_path}/{fname}/brightness"
            max_brightness_path = f"{base_path}/{fname}/max_brightness"
            max_brightness = 255
            brightness = 0

            with open(max_brightness_path) as f:
                max_brightness = int(f.read().strip())

            with open(brightness_path) as f:
                brightness = int(f.read().strip())

            res.append((fname, brightness_path, max_brightness, brightness))

        return res

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.BACKSPACE:
            self.exit()

    def exit(self):
        if self.on_exit:
            self.on_exit()
