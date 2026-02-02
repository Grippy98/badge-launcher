import app
import lvgl as lv
import os
import sys
import time

# Add libtuxdriver to path
LIBTUX_PATH = "/root/badge_launcher/libtuxdriver/include"
if LIBTUX_PATH not in sys.path:
    sys.path.append(LIBTUX_PATH)

from tux_driver_mp import *

class TuxDriverApp(app.App):
    def __init__(self):
        super().__init__("Tux Driver")
        self.screen = None
        self.tux_drv = None
        self.dongle_connected = False
        self.rf_connected = False
        self.battery_level = 0
        self.status_labels = {}
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

    def on_status_event(self, status):
        if not self.tux_drv: return
        try:
            status_struct = self.tux_drv.GetStatusStruct(status)
            name = status_struct['name']
            value = status_struct['value']
            
            if name == 'radio_state':
                self.rf_connected = bool(value)
                lv.async_call(lambda _: self.update_status_label('rf', f"RF: {'OK' if self.rf_connected else 'LOST'}"), None)
            elif name == 'battery_level':
                self.battery_level = value
                lv.async_call(lambda _: self.update_status_label('batt', f"Batt: {self.battery_level}%"), None)
            elif name == 'dongle_plug':
                self.dongle_connected = bool(value)
                lv.async_call(lambda _: self.update_status_label('dongle', f"Dongle: {'IN' if self.dongle_connected else 'OUT'}"), None)
        except: pass

    def on_dongle_connected(self):
        self.dongle_connected = True
        lv.async_call(lambda _: self.update_status_label('dongle', "Dongle: IN"), None)

    def update_status_label(self, key, text):
        if key in self.status_labels:
            self.status_labels[key].set_text(text)

    def create_btn(self, parent, text, cmd):
        btn = lv.button(parent)
        btn.set_size(110, 40)
        btn.add_style(self.style_btn_rel, 0)
        btn.add_style(self.style_btn_pr, lv.STATE.PRESSED)
        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        
        btn.add_event_cb(lambda e: self.send_cmd(cmd), lv.EVENT.CLICKED, None)
        btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        lbl = lv.label(btn)
        lbl.set_text(text)
        lbl.center()
        
        self.controls.append(btn)
        return btn

    def send_cmd(self, cmd):
        if self.tux_drv:
            if cmd == "RESET_POS":
                print("Sending RESET_POS")
                self.tux_drv.ResetPositions()
            else:
                print(f"Sending command: {cmd}")
                self.tux_drv.PerformCommand(0, cmd)
        else:
            print("Cannot send command: Driver not initialized")

    def enter(self, on_exit=None):
        self.on_exit = on_exit
        self.controls = []
        
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Header Info
        header = lv.obj(self.screen)
        header.set_size(400, 40)
        header.align(lv.ALIGN.TOP_MID, 0, 0)
        header.set_flex_flow(lv.FLEX_FLOW.ROW)
        header.set_flex_align(lv.FLEX_ALIGN.SPACE_AROUND, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        header.set_style_border_width(0, 0)
        header.set_style_bg_opa(0, 0)

        self.status_labels['dongle'] = lv.label(header)
        self.status_labels['dongle'].set_text("Dongle: ?")
        self.status_labels['rf'] = lv.label(header)
        self.status_labels['rf'].set_text("RF: ?")
        self.status_labels['batt'] = lv.label(header)
        self.status_labels['batt'].set_text("Batt: ?")

        # Main Body - Buttons (Column for simplicity and visibility)
        grid = lv.obj(self.screen)
        grid.set_size(lv.pct(100), lv.pct(80))
        grid.align(lv.ALIGN.CENTER, 0, 20)
        grid.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        grid.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        grid.set_style_pad_gap(5, 0)
        grid.set_style_border_width(0, 0)
        grid.set_style_bg_opa(0, 0)
        grid.set_scroll_dir(lv.DIR.VER)

        self.create_btn(grid, "Eyes Open", "TUX_CMD:EYES:OPEN")
        self.create_btn(grid, "Eyes Close", "TUX_CMD:EYES:CLOSE")
        self.create_btn(grid, "Mouth Open", "TUX_CMD:MOUTH:OPEN")
        self.create_btn(grid, "Mouth Close", "TUX_CMD:MOUTH:CLOSE")
        self.create_btn(grid, "Flap Open", "TUX_CMD:FLIPPERS:ON:4:OPEN")
        self.create_btn(grid, "Flap Close", "TUX_CMD:FLIPPERS:OFF")
        self.create_btn(grid, "Spin Left", "TUX_CMD:SPINNING:LEFT_ON_DURING:2.0")
        self.create_btn(grid, "Spin Right", "TUX_CMD:SPINNING:RIGHT_ON_DURING:2.0")
        self.create_btn(grid, "Reset Pos", "RESET_POS") # Special handling or cmd

        # Init Tux Driver Synchronously (no threading)
        self.init_tux()
        
        # Set up a timer to poll the USB connection periodically
        self.poll_timer = lv.timer_create(lambda _: self.poll_tux(), 100, None)

        # Input Group
        import input
        if input.driver and input.driver.group:
            g = input.driver.group
            g.remove_all_objs()
            for obj in self.controls:
                g.add_obj(obj)
            if self.controls:
                lv.group_focus_obj(self.controls[0])
        
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

    def poll_tux(self):
        """Called periodically to poll the Tux Driver."""
        if self.tux_drv:
            try:
                self.tux_drv.Poll()
            except: pass

    def init_tux(self):
        try:
            # Try to find the library in the project structure
            lib_path = "/root/badge_launcher/libtuxdriver/unix/libtuxdriver.so"
            # if not os.path.exists(lib_path):
            #      lib_path = "libtuxdriver.so" # Fallback
            print(f"Loading libtuxdriver from {lib_path}")
            self.tux_drv = TuxDrv(lib_path)
            if self.tux_drv and self.tux_drv.tux_driver_lib:
                self.tux_drv.SetLogLevel(LOG_LEVEL_INFO)
                # Enable callbacks
                print("Enabling callbacks...")
                # Set log target to SHELL (1)
                try:
                    self.tux_drv.tux_driver_lib.func("v", "TuxDrv_SetLogTarget", "i")(1)
                except: pass
                
                self.tux_drv.SetStatusCallback(self.on_status_event)
                self.tux_drv.SetDongleConnectedCallback(self.on_dongle_connected)
                # Just try a simple command to test
                self.tux_drv.Start()  # This now just initializes
                print("Tux Driver initialized (polling mode)")
        except Exception as e:
            print(f"Failed to start Tux Driver: {e}")

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.BACKSPACE:
            self.exit()

    def exit(self):
        if self.tux_drv:
            self.tux_drv.Stop()
            self.tux_drv = None
        if self.on_exit:
            self.on_exit()
