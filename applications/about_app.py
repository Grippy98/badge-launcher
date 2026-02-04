import lvgl as lv
import app

class AboutApp(app.App):
    def __init__(self):
        super().__init__("About")
        self.screen = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        lbl = lv.label(self.screen)
        lbl.set_text("Beagle Badge Linux Port\n\nVersion: 0.2\n")
        lbl.set_style_text_color(lv.color_black(), 0)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.center()
        
    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.BACKSPACE or key == 14 or key == lv.KEY.LEFT:
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
            
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
