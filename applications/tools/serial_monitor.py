import lvgl as lv
import app
import tty

class SerialMonitorApp(app.App):
    def __init__(self):
        super().__init__("Serial Monitor")
        self.screen = None
        self.ta = None
        self.timer = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_black(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Input Isolation
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        # Text Area
        self.ta = lv.textarea(self.screen)
        self.ta.set_size(lv.pct(100), lv.pct(100))
        self.ta.set_style_bg_color(lv.color_black(), 0)
        self.ta.set_style_text_color(lv.palette_main(lv.PALETTE.GREEN), 0)
        self.ta.set_style_text_font(lv.font_montserrat_10, 0) # Small font
        self.ta.set_style_border_width(0, 0)
        self.ta.set_text("Serial Monitor (ttyS0)\n")
        self.ta.set_cursor_click_pos(False)
        self.ta.set_read_only(True)
        
        # tty init if needed (global tty usually init in main)
        
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        self.timer = lv.timer_create(self.loop, 100, None)
        
    def loop(self, t):
        # Read from TTY
        data = tty.read() # Assume tty module has read()
        if data:
            try:
                text = data.decode('utf-8', 'ignore')
                self.ta.add_text(text)
            except: pass
            
    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.LEFT or key == lv.KEY.BACKSPACE:
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
            
    def exit(self):
        if self.timer:
            self.timer.delete()
            self.timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
