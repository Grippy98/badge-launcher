"""Badge Mode application for displaying badge information.

Shows the user's name, info text, and logo. Allows editing badge details
and cycling through logo options (Random, Beagle, TI).
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import random
import config
import time

class BadgeModeApp(app.App):
    def __init__(self):
        super().__init__("Badge Mode")
        self.screen = None
        self.on_exit_cb = None
        self.ti_dsc = self.load_logo("assets/ti_logo.bin")
        self.beagle_dsc = self.load_logo("assets/beagle_logo.bin")
        
        self.editing = False
        self.edit_target = "name" # "name" or "info"
        self.ta = None
        
    def load_logo(self, path):
        try:
            with open(path, 'rb') as f:
                data = f.read()
            dsc = lv.image_dsc_t()
            dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            dsc.header.cf = lv.COLOR_FORMAT.L8
            dsc.header.w = 128
            dsc.header.h = 128
            dsc.data_size = len(data)
            dsc.data = data
            return dsc
        except:
            return None

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Add to input group
        import input
        if input.driver and input.driver.group:
            input.driver.group.set_editing(False)
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        self.render()

    def render(self):
        self.screen.clean()
        
        if self.editing:
            self.render_editor()
            return

        # Badge View
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        cont.set_style_border_width(0, 0)
        cont.set_style_pad_all(0, 0)
        
        # Logo
        logo_img = lv.image(cont)
        
        # Determine which logo to show
        show_beagle = False
        if config.badge_logo == 0: # Random
            show_beagle = random.random() > 0.5
        elif config.badge_logo == 1: # Force Beagle
            show_beagle = True
        else: # Force TI
            show_beagle = False

        if show_beagle:
            if self.beagle_dsc: logo_img.set_src(self.beagle_dsc)
        else:
            if self.ti_dsc: logo_img.set_src(self.ti_dsc)
            
        # Name
        self.lbl_name = lv.label(cont)
        self.lbl_name.set_text(config.badge_name)
        self.lbl_name.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            self.lbl_name.set_style_text_font(lv.font_montserrat_24, 0)
        except: pass
        
        # Info
        self.lbl_info = lv.label(cont)
        self.lbl_info.set_text(config.badge_info)
        self.lbl_info.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        
        # Hint
        hint = lv.label(self.screen)
        hint.set_text("Press ENTER to Edit")
        try:
            hint.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        hint.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        hint.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)
        
        # Logo Mode Hint
        mode_hint = lv.label(self.screen)
        modes = ["Random", "Force Beagle", "Force TI"]
        mode_hint.set_text(f"Logo: {modes[config.badge_logo]}")
        try:
            mode_hint.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        mode_hint.align(lv.ALIGN.TOP_MID, 0, 5)
        mode_hint.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)

    def render_editor(self):
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        cont.set_style_pad_all(10, 0)
        
        title = lv.label(cont)
        title.set_text(f"Edit {'Name' if self.edit_target == 'name' else 'Info'}")
        
        self.ta = lv.textarea(cont)
        self.ta.set_size(lv.pct(90), 80)
        self.ta.set_text(config.badge_name if self.edit_target == "name" else config.badge_info)
        self.ta.set_one_line(False)
        
        import input
        if input.driver and input.driver.group:
            input.driver.group.add_obj(self.ta)
            lv.group_focus_obj(self.ta)
            input.driver.group.set_editing(True) 
            
        self.ta.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            
        hint = lv.label(cont)
        hint.set_text("ESC: Save & Next | BACKSPACE: Clear")
        try:
            hint.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass

    def on_key(self, e):
        key = e.get_key()
        if not self.editing:
            if key == lv.KEY.ESC:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()
            elif key == lv.KEY.ENTER:
                self.editing = True
                self.edit_target = "name"
                self.render()
            elif key == lv.KEY.LEFT:
                # Cycle: Random (0) -> TI (2) -> Beagle (1) -> Random
                config.badge_logo = (config.badge_logo - 1) % 3
                config.save()
                self.render()
            elif key == lv.KEY.RIGHT:
                config.badge_logo = (config.badge_logo + 1) % 3
                config.save()
                self.render()
        else:
            # Editing mode
            if key == lv.KEY.ESC:
                # Save current
                val = self.ta.get_text()
                # Strip control characters (like ESC key which might get inserted)
                clean_val = "".join([c for c in val if ord(c) >= 32 or c == "\n"])
                
                if self.edit_target == "name":
                    config.badge_name = clean_val
                    self.edit_target = "info"
                    self.render()
                else:
                    config.badge_info = clean_val
                    config.save()
                    self.editing = False
                    self.render()
                    # Restore focus
                    import input
                    if input.driver and input.driver.group:
                        input.driver.group.set_editing(False)
                        input.driver.group.remove_all_objs()
                        input.driver.group.add_obj(self.screen)
                        lv.group_focus_obj(self.screen)
            elif key == lv.KEY.ENTER:
                # Enter is handled by textarea for newlines automatically
                # unless we override it. We want it to be a newline.
                pass
                
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None