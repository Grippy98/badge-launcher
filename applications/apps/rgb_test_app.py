import app
import lvgl as lv
import time
import math

class RGBTestApp(app.App):
    def __init__(self):
        super().__init__("RGB Test")
        self.screen = None
        self.timer = None
        self.hue = 0
        self.led_path = "/sys/class/leds/rgb:"
        self.mode = "OFF" # OFF, STATIC, RAINBOW
        self.current_rgb = (0, 0, 0)
        self.brightness = 13 # ~5% of 255
        self.controls = []

        # Styles
        self.style_btn_rel = lv.style_t()
        self.style_btn_rel.init()
        self.style_btn_rel.set_radius(0)
        self.style_btn_rel.set_border_width(1)
        self.style_btn_rel.set_border_color(lv.color_black())
        self.style_btn_rel.set_bg_color(lv.color_white())
        self.style_btn_rel.set_text_color(lv.color_black())

        self.style_btn_pr = lv.style_t()
        self.style_btn_pr.init()
        self.style_btn_pr.set_bg_color(lv.color_black())
        self.style_btn_pr.set_text_color(lv.color_white())

        self.style_btn_foc = lv.style_t()
        self.style_btn_foc.init()
        self.style_btn_foc.set_bg_color(lv.color_black())
        self.style_btn_foc.set_text_color(lv.color_white())
        
    def set_hw_color(self, r, g, b):
        try:
            with open(f"{self.led_path}/multi_intensity", "w") as f:
                f.write(f"{r} {g} {b}")
            with open(f"{self.led_path}/brightness", "w") as f:
                f.write(f"{self.brightness}")
        except: pass

    def update_rainbow(self, timer):
        try:
            if self.mode != "RAINBOW": return

            # HSV to RGB
            h = self.hue
            s = 1.0
            v = 1.0
            
            c = v * s
            x = c * (1 - abs((h / 60) % 2 - 1))
            m = v - c
            
            if 0 <= h < 60: r, g, b = c, x, 0
            elif 60 <= h < 120: r, g, b = x, c, 0
            elif 120 <= h < 180: r, g, b = 0, c, x
            elif 180 <= h < 240: r, g, b = 0, x, c
            elif 240 <= h < 300: r, g, b = x, 0, c
            elif 300 <= h < 360: r, g, b = c, 0, x
            else: r, g, b = 0, 0, 0
            
            ir, ig, ib = int((r+m)*255), int((g+m)*255), int((b+m)*255)
            self.current_rgb = (ir, ig, ib)
            self.set_hw_color(ir, ig, ib)

            self.hue = (self.hue + 5) % 360
        except Exception as e:
            print(f"LED Error: {e}")

    def set_static_color(self, r, g, b):
        self.mode = "STATIC"
        self.current_rgb = (r, g, b)
        self.set_hw_color(r, g, b)

    def set_rainbow(self):
        self.mode = "RAINBOW"

    def set_off(self):
        self.mode = "OFF"
        self.set_hw_color(0, 0, 0)

    def on_slider_change(self, e):
        slider = e.get_target_obj()
        val = slider.get_value()
        self.brightness = int((val / 100) * 255)
        self.val_lbl.set_text(f"Brightness: {val}%")
        
        # Apply immediate update
        if self.mode == "STATIC":
            r, g, b = self.current_rgb
            self.set_hw_color(r, g, b)
        elif self.mode == "RAINBOW":
            pass # Timer picks it up next cycle
        elif self.mode == "OFF":
             pass

    def create_btn(self, parent, text, callback):
        btn = lv.button(parent)
        btn.set_width(lv.pct(80)) # Full list width
        btn.set_height(30) # Compact height
        
        # Apply Styles
        btn.add_style(self.style_btn_rel, 0)
        btn.add_style(self.style_btn_pr, lv.STATE.PRESSED)
        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)

        btn.add_event_cb(lambda e: callback(), lv.EVENT.CLICKED, None)
        btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        lbl = lv.label(btn)
        lbl.set_text(text)
        lbl.center()
        try:
           lbl.set_style_text_font(lv.font_montserrat_14, 0) # Smaller font
        except: pass
        
        self.controls.append(btn)
        return btn

    def enter(self, on_exit=None):
        self.on_exit = on_exit
        self.controls = [] # Reset controls list
        
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
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
        title.set_text("RGB LED Control")
        try:
            title.set_style_text_font(lv.font_montserrat_16, 0)
        except: pass
        
        # --- Slider Section (Moved to Top) ---
        self.val_lbl = lv.label(cont)
        self.val_lbl.set_text(f"Brightness: {int(self.brightness/255*100)}%")
        try:
            self.val_lbl.set_style_text_font(lv.font_montserrat_14, 0) # Smaller font
        except: pass
        
        self.slider = lv.slider(cont)
        self.slider.set_width(lv.pct(80))
        self.slider.set_range(0, 100)
        self.slider.set_value(int(self.brightness/255*100), 0)
        self.slider.add_event_cb(self.on_slider_change, lv.EVENT.VALUE_CHANGED, None)
        self.slider.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        self.controls.append(self.slider)

        # Spacer
        spacer = lv.obj(cont)
        spacer.set_size(lv.pct(100), 20)
        spacer.set_style_bg_opa(0, 0) # Transparent
        spacer.set_style_border_width(0, 0)


        # --- Vertical Column of Buttons ---
        self.create_btn(cont, "Red", lambda: self.set_static_color(255, 0, 0))
        self.create_btn(cont, "Green", lambda: self.set_static_color(0, 255, 0))
        self.create_btn(cont, "Blue", lambda: self.set_static_color(0, 0, 255))
        self.create_btn(cont, "Rainbow", lambda: self.set_rainbow())
        self.create_btn(cont, "Off", lambda: self.set_off())


        # Timer
        self.timer = lv.timer_create(lambda t: self.update_rainbow(t), 50, None)
        
        # Focus Group
        import input
        if input.driver and input.driver.group:
            g = input.driver.group
            g.remove_all_objs()
            
            # Add all controls to group
            for obj in self.controls:
                g.add_obj(obj)
            
            # Focus first button (Slider now)
            if self.controls:
                lv.group_focus_obj(self.controls[0])
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.BACKSPACE:
            self.exit()
            
    def exit(self):
        if self.timer:
            self.timer.delete()
            self.timer = None
        self.set_off()
        if self.on_exit:
            self.on_exit()
