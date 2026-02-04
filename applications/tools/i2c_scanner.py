"""I2C bus scanner tool.

Scans the I2C bus for connected devices and displays their addresses.
Useful for hardware debugging and device discovery.
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import time
import os

class I2CScannerApp(app.App):
    def __init__(self):
        super().__init__("I2C Scanner")
        self.screen = None
        self.buses = []
        self.sel_idx = 0
        self.left_cont = None
        self.right_cont = None
        self.btn_objs = [] # List of (obj, label)
        self.timer = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Input isolation
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        # Detect Buses
        # Explicitly check for common buses since os.listdir can be flaky or limited
        self.buses = []
        for i in [0, 1, 2]:
            try:
                # Check directly if device exists
                os.stat(f"/dev/i2c-{i}")
                self.buses.append(i)
            except:
                pass
                
        if not self.buses:
            self.buses = [0, 2] # Fallback if everything fails

        # Keyboard event support for SDL mode
        self.current_key = 0
        self.key_state = lv.INDEV_STATE.RELEASED
        self.screen.add_event_cb(self.on_key_event, lv.EVENT.KEY, None)

        # Add to input group for keyboard focus
        import input
        if input.driver and input.driver.group:
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.build_ui()

        self.prev_state = lv.INDEV_STATE.RELEASED
        self.timer = lv.timer_create(self.loop, 50, None)

    def build_ui(self):
        self.state = "SELECT"
        # Title
        title = lv.label(self.screen)
        title.set_text("I2C Scanner")
        title.align(lv.ALIGN.TOP_LEFT, 10, 5)
        title.set_style_text_color(lv.color_black(), 0)
        
        disp = lv.display_get_default()
        width = disp.get_horizontal_resolution()
        height = disp.get_vertical_resolution()
        content_h = height - 40
        
        # Left Container (Buses) 35%
        self.left_cont = lv.obj(self.screen)
        self.left_cont.set_size(int(width * 0.35), content_h)
        self.left_cont.align(lv.ALIGN.BOTTOM_LEFT, 0, 0)
        self.left_cont.set_style_bg_opa(lv.OPA.TRANSP, 0)
        self.left_cont.set_style_border_width(0, 0)
        self.left_cont.set_style_pad_all(5, 0)
        self.left_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.left_cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # Divider Line
        div = lv.obj(self.screen)
        div.set_size(2, content_h - 10)
        div.align(lv.ALIGN.BOTTOM_LEFT, int(width * 0.35) + 2, -5)
        div.set_style_bg_color(lv.palette_main(lv.PALETTE.GREY), 0)
        div.set_style_bg_opa(lv.OPA.COVER, 0)
        div.set_style_border_width(0, 0)
        
        # Right Container (Results) ~64%
        self.right_cont = lv.obj(self.screen)
        self.right_cont.set_size(int(width * 0.60), content_h)
        self.right_cont.align(lv.ALIGN.BOTTOM_RIGHT, 0, 0)
        self.right_cont.set_style_bg_color(lv.palette_lighten(lv.PALETTE.GREY, 4), 0)
        self.right_cont.set_style_bg_opa(lv.OPA.COVER, 0)
        self.right_cont.set_style_border_width(0, 0)
        self.right_cont.set_style_pad_all(15, 0) # More padding
        self.right_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.right_cont.set_style_pad_row(10, 0) # Gap between items
        
        # Populate Buses
        self.btn_objs = []
        for i, bus in enumerate(self.buses):
            btn = lv.obj(self.left_cont)
            btn.set_width(lv.pct(100))
            btn.set_height(40)
            btn.set_style_radius(5, 0)
            btn.set_style_border_width(1, 0)
            
            lbl = lv.label(btn)
            lbl.set_text(f"Bus {bus}")
            lbl.center()
            
            self.btn_objs.append((btn, lbl))
            
        self.update_selection()
        
        # Initial Hint
        hint = lv.label(self.right_cont)
        hint.set_text("Select Bus\nPress ENTER to Scan")
        hint.set_style_text_color(lv.color_black(), 0)


        
    def update_selection(self):
        for i, (btn, lbl) in enumerate(self.btn_objs):
            if i == self.sel_idx:
                btn.set_style_bg_color(lv.color_black(), 0)
                btn.set_style_bg_opa(lv.OPA.COVER, 0)
                lbl.set_style_text_color(lv.color_white(), 0)
            else:
                btn.set_style_bg_color(lv.color_white(), 0)
                btn.set_style_bg_opa(lv.OPA.COVER, 0)
                lbl.set_style_text_color(lv.color_black(), 0)

    def run_scan(self):
        bus = self.buses[self.sel_idx]
        
        self.right_cont.clean()

        
        lbl = lv.label(self.right_cont)
        lbl.set_text(f"Scanning Bus {bus}...")
        lbl.set_style_text_color(lv.color_black(), 0)
        lv.task_handler()
        
        cmd = f"i2cdetect -y -r {bus} > /tmp/i2c_scan.txt"
        res = os.system(cmd)
        
        found_list = []
        parsing_error = False
        
        if res == 0:
            try:
                # Check file existence using stat for MicroPython compatibility (no os.path)
                try:
                    os.stat("/tmp/i2c_scan.txt")
                    file_exists = True
                except:
                    file_exists = False

                if not file_exists:
                    found_list = ["No output file"]
                else:
                    with open("/tmp/i2c_scan.txt", "r") as f:
                        lines = f.readlines()
                        for line in lines:
                            parts = line.strip().split()
                            if not parts: continue
                            token0 = parts[0]
                            if token0.endswith(':'):
                                try:
                                    base_addr = int(token0[:-1], 16)
                                    # Fix for row 00 offset (starts at col 8 -> 0x08)
                                    start_col = 0
                                    if base_addr == 0:
                                        start_col = 8
                                        
                                    for i, cell in enumerate(parts[1:]):
                                        addr = base_addr + start_col + i
                                        if cell == "UU":
                                            found_list.append(f"0x{addr:02X} (Used)")
                                        elif cell != "--":
                                            found_list.append(f"0x{cell.upper()}")
                                except: pass
            except Exception as e:
                parsing_error = True
                parsing_error_msg = str(e)
        else:
            found_list = ["Scan Error", "Check i2c-tools"]
            
        self.right_cont.clean()
        
        title = lv.label(self.right_cont)
        title.set_text(f"Results (Bus {bus}):")
        title.set_style_text_font(lv.font_montserrat_14, 0)
        title.set_style_text_color(lv.color_black(), 0)
        
        if parsing_error:
             err = lv.label(self.right_cont)
             err.set_text(f"Error: {parsing_error_msg}")
             err.set_style_text_color(lv.palette_main(lv.PALETTE.RED), 0)
        elif not found_list:
            lbl = lv.label(self.right_cont)
            lbl.set_text("No devices found.")
            lbl.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)
        else:
            for item in found_list:
                item_lbl = lv.label(self.right_cont)
                item_lbl.set_text(item)
                item_lbl.set_long_mode(lv.label.LONG_MODE.WRAP)
                item_lbl.set_width(lv.pct(100))
                item_lbl.set_style_text_color(lv.color_black(), 0)
                item_lbl.set_style_bg_color(lv.color_white(), 0)
                item_lbl.set_style_bg_opa(lv.OPA.COVER, 0)
                item_lbl.set_style_pad_all(5, 0)
                item_lbl.set_style_radius(4, 0)
                item_lbl.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
                
        self.state = "SHOW"

    def on_key_event(self, e):
        """Handle LVGL keyboard events (for SDL mode)."""
        key = e.get_key()
        self.current_key = key
        self.key_state = lv.INDEV_STATE.PRESSED

    def loop(self, t):
        import input

        # Try SDL/LVGL keyboard first
        key = self.current_key
        state = self.key_state

        # Fall back to hardware input driver if no SDL key
        if state != lv.INDEV_STATE.PRESSED and input.driver:
            key = input.driver.last_key
            state = input.driver.state

        # Edge Detection
        if state == lv.INDEV_STATE.PRESSED and self.prev_state == lv.INDEV_STATE.RELEASED:
            # Reset key state after processing
            self.key_state = lv.INDEV_STATE.RELEASED
            print(f"I2C Key: {key}")


            if key == lv.KEY.ESC or key == lv.KEY.LEFT or key == lv.KEY.BACKSPACE or key == ord('q'):
                if self.state == "SHOW":
                    self.build_ui()
                else:
                    self.exit()
                    if self.on_exit_cb: self.on_exit_cb()
                    
            elif key == lv.KEY.UP or key == 103 or key == 11 or key == lv.KEY.PREV:
                self.sel_idx = (self.sel_idx - 1) % len(self.buses)
                self.update_selection()
                    
            elif key == lv.KEY.DOWN or key == 108 or key == 9 or key == lv.KEY.NEXT:
                self.sel_idx = (self.sel_idx + 1) % len(self.buses)
                self.update_selection()
                    
            elif key == lv.KEY.ENTER or key == 10:
                self.run_scan()
                    
        self.prev_state = state

    def exit(self):
        if self.timer:
            self.timer.delete()
            self.timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
