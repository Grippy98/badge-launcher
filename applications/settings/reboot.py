import lvgl as lv
import app
import os

class RebootApp(app.App):
    def __init__(self):
        super().__init__("Reboot")
        self.screen = None
        self.on_exit_cb = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Input handling
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        # UI
        main_cont = lv.obj(self.screen)
        main_cont.set_size(lv.pct(80), lv.pct(80))
        main_cont.center()
        main_cont.set_style_border_width(0, 0)
        main_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        main_cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        lbl = lv.label(main_cont)
        lbl.set_text("Reboot Device?")
        lbl.set_style_text_font(lv.font_montserrat_24, 0)
        lbl.set_style_text_color(lv.color_black(), 0)
        
        lbl2 = lv.label(main_cont)
        lbl2.set_text("Press ENTER to confirm\nPress LEFT to cancel")
        lbl2.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl2.set_style_text_color(lv.color_black(), 0)
        
    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.LEFT or key == lv.KEY.BACKSPACE or key == ord('q'):
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
        elif key == lv.KEY.ENTER:
            self.do_reboot()
            
    def do_reboot(self):
        # Notify user (visual only since we are about to die)
        msg = lv.label(self.screen)
        msg.set_text("Rebooting...")
        msg.center()
        msg.set_style_bg_color(lv.color_black(), 0)
        msg.set_style_text_color(lv.color_white(), 0)
        msg.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.task_handler() 
        
        # Execute reboot
        try:
            os.system("reboot")
        except Exception as e:
            print(f"Reboot failed: {e}")
            
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
