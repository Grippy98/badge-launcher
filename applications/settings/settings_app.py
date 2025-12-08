import lvgl as lv
import app



class SoundApp(app.App):
    def __init__(self):
        super().__init__("Sound")
        self.screen = None
        self.sound_enabled = True
        self.lbl = None
        
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
        
        self.lbl = lv.label(self.screen)
        self.update_ui()
        self.lbl.set_style_text_color(lv.color_black(), 0)
        self.lbl.center()
        
        hint = lv.label(self.screen)
        hint.set_text("Press Enter to Toggle")
        hint.align(lv.ALIGN.BOTTOM_MID, 0, -20)
        hint.set_style_text_color(lv.color_black(), 0)
        
    def update_ui(self):
        import config
        status = "ON" if config.sound_enabled else "OFF"
        self.lbl.set_text(f"Sound is: {status}")
        
    def on_key(self, e):
        import config
        k = e.get_key()
        if k == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
        elif k == lv.KEY.ENTER or k == 28:
            config.sound_enabled = not config.sound_enabled
            config.save()
            # Also update driver if possible
            import sound
            if sound.driver:
                sound.driver.enabled = config.sound_enabled
            self.update_ui()
            
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
