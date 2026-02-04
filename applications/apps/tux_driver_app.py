"""Tux Droid Robot control application.

Controls Tux Droid robot via RF dongle. Supports movement control,
LED manipulation, and status monitoring.
"""

import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import lvgl as lv
import os
import time

# Add libtuxdriver to path
# Try relative path first (package mode) then absolute (legacy mode)
LIBTUX_PATH = "./libtuxdriver/include"
if LIBTUX_PATH not in sys.path:
    sys.path.append(LIBTUX_PATH)
    # Also add the root if needed for submodule imports
    if "." not in sys.path:
        sys.path.append(".")

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
        
        # Debounce
        self.last_ir_time = 0
        self.debounce_interval = 0.5 # 500ms

        # Button references
        self.btn_eyes = None
        self.btn_mouth = None
        self.btn_flippers = None
        self.btn_leds = None

        # State for toggles
        self.eyes_open = True  # Default to OPEN
        self.mouth_open = False
        self.flippers_up = False
        self.leds_on = True # Default to ON

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

    def log_debug(self, msg):
        try:
            with open("/tmp/tux_app.log", "a") as f:
                f.write(f"{str(time.time())}: {msg}\n")
            print(f"Logged: {msg}")
        except:
            print(f"Log Fail: {msg}")

    def on_status_event(self, status):
        """
        Called when the driver pushes a status update.
        NOTE: 'status' comes as an int pointer due to FFI limitation, so parsing fails.
        We treat this as a signal to POLL attributes instead.
        """
        if not self.tux_drv: return
        
        # 1. Try to parse logic (will fail based on logs, but good to keep structure)
        try:
            status_struct = self.tux_drv.GetStatusStruct(status)
            # If successful, we could use it... but we expect failure.
        except Exception:
            # Expected error: 'int' object has no attribute 'split'
            pass
        
        # 2. Always poll critical inputs on event
        try:
            # Check IR Command
            # GetAttribute uses a pre-allocated buffer so it works reliably
            ir_cmd = self.tux_drv.GetAttribute("remote_button")
            if ir_cmd and ir_cmd != "None":
                 # Log raw ir command
                 # self.log_debug(f"Event Triggered Polled IR: {ir_cmd}")
                 
                 lv.async_call(lambda _: self.update_status_label('ir', f"IR: {ir_cmd}"), None)
                 
                 # Process IR Logic with Debounce
                 current_time = time.time()
                 if (current_time - self.last_ir_time) > self.debounce_interval:
                     
                     triggered = False
                     if "K_UP" in ir_cmd:
                        self.log_debug("Action: K_UP -> Set Flippers UP")
                        lv.async_call(lambda _: self.set_flippers(True), None)
                        triggered = True
                     elif "K_DOWN" in ir_cmd:
                        self.log_debug("Action: K_DOWN -> Set Flippers DOWN")
                        lv.async_call(lambda _: self.set_flippers(False), None)
                        triggered = True
                     elif "K_STANDBY" in ir_cmd:
                        self.log_debug("Action: K_STANDBY -> Toggle LEDs")
                        lv.async_call(lambda _: self.set_leds(not self.leds_on), None)
                        triggered = True
                     elif "K_OK" in ir_cmd:
                        self.log_debug("Action: K_OK -> Toggle Eyes")
                        lv.async_call(lambda _: self.set_eyes(not self.eyes_open), None)
                        triggered = True
                     elif "K_LEFT" in ir_cmd:
                        self.log_debug("Action: K_LEFT -> Set Mouth CLOSED")
                        lv.async_call(lambda _: self.set_mouth(False), None)
                        triggered = True
                     elif "K_RIGHT" in ir_cmd:
                        self.log_debug("Action: K_RIGHT -> Set Mouth OPEN")
                        lv.async_call(lambda _: self.set_mouth(True), None)
                        triggered = True
                        
                     if triggered:
                         self.last_ir_time = current_time
        
            # Update other labels
            lv.async_call(lambda _: self.update_all_labels(), None)

        except Exception as e:
             self.log_debug(f"Event Hndlr Error: {e}")

    def on_dongle_connected(self):
        self.dongle_connected = True
        lv.async_call(lambda _: self.update_status_label('dongle', "Dongle: Connected"), None)
        self.update_all_labels()

    def update_status_label(self, key, text):
        if key in self.status_labels and self.status_labels[key]:
            self.status_labels[key].set_text(text)

    def update_all_labels(self):
        if not self.tux_drv: return
        try:
            if hasattr(self.tux_drv, 'GetAttribute'):
                # RF
                rf_state = self.tux_drv.GetAttribute("radio_state")
                if rf_state:
                    self.rf_connected = (rf_state == "True")
                    lv.async_call(lambda _: self.update_status_label('rf', f"RF: {'OK' if self.rf_connected else 'LOST'}"), None)
                
                # Battery
                batt_lvl_str = self.tux_drv.GetAttribute("battery_level")
                if batt_lvl_str:
                    try:
                        mv = int(batt_lvl_str)
                        volts = mv / 1000.0
                        lv.async_call(lambda _: self.update_status_label('batt', f"Batt: {volts:.2f}V"), None)
                    except ValueError:
                        self.battery_level = batt_lvl_str
                        lv.async_call(lambda _: self.update_status_label('batt', f"Batt: {self.battery_level}"), None)
                
                # Dongle
                dongle = self.tux_drv.GetAttribute("dongle_plug")
                if dongle:
                    self.dongle_connected = (dongle == "True")
                    lv.async_call(lambda _: self.update_status_label('dongle', f"Dongle: {'Connected' if self.dongle_connected else 'Disconnected'}"), None)
                
                # Head
                head = self.tux_drv.GetAttribute("head_button")
                if head:
                    is_pressed = (head == "True")
                    lv.async_call(lambda _: self.update_status_label('head', f"Head: {'ON' if is_pressed else 'OFF'}"), None)

                # IR
                # Note: We duplicate this here to ensure it catches polling updates too
                remote = self.tux_drv.GetAttribute("remote_button")
                if remote and remote != "None":
                     lv.async_call(lambda _: self.update_status_label('ir', f"IR: {remote}"), None)

        except Exception as e:
            self.log_debug(f"Update Labels Err: {e}")

    def create_btn(self, parent, text, cmd_or_cb):
        btn = lv.button(parent)
        btn.set_size(160, 40) 
        btn.add_style(self.style_btn_rel, 0)
        btn.add_style(self.style_btn_pr, lv.STATE.PRESSED)
        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        
        if callable(cmd_or_cb):
            btn.add_event_cb(lambda e: cmd_or_cb(btn), lv.EVENT.CLICKED, None)
        else:
            btn.add_event_cb(lambda e: self.send_cmd(cmd_or_cb), lv.EVENT.CLICKED, None)
            
        btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        lbl = lv.label(btn)
        lbl.set_text(text)
        lbl.center()
        
        self.controls.append(btn)
        return btn, lbl

    def send_cmd(self, cmd):
        if self.tux_drv:
            if cmd == "RESET_POS":
                self.log_debug("Sending RESET_POS")
                self.tux_drv.ResetPositions()
                self.eyes_open = True
                self.mouth_open = False
                self.flippers_up = False
                self.leds_on = True 
                
                for btn in self.controls:
                    lbl = btn.get_child(0)
                    if hasattr(lbl, 'get_text'):
                        txt = lbl.get_text()
                        if "Eyes:" in txt: lbl.set_text("Eyes: OPEN")
                        if "Mouth:" in txt: lbl.set_text("Mouth: CLOSED")
                        if "Flippers:" in txt: lbl.set_text("Flippers: DOWN")
                        if "LEDs:" in txt: lbl.set_text("LEDs: ON")

            else:
                self.log_debug(f"Sending CMD: {cmd}")
                self.tux_drv.PerformCommand(0, cmd)
        else:
            self.log_debug("Err: Driver not initialized")

    # --- ACTION PRIMITIVES (State Setters) ---

    def set_eyes(self, open_eyes):
        self.eyes_open = open_eyes
        cmd = "TUX_CMD:EYES:OPEN" if self.eyes_open else "TUX_CMD:EYES:CLOSE"
        self.send_cmd(cmd)
        if self.btn_eyes:
            lbl = self.btn_eyes.get_child(0)
            if lbl: lbl.set_text(f"Eyes: {'OPEN' if self.eyes_open else 'CLOSED'}")

    def set_mouth(self, open_mouth):
        self.mouth_open = open_mouth
        cmd = "TUX_CMD:MOUTH:OPEN" if self.mouth_open else "TUX_CMD:MOUTH:CLOSE"
        self.send_cmd(cmd)
        if self.btn_mouth:
            lbl = self.btn_mouth.get_child(0)
            if lbl: lbl.set_text(f"Mouth: {'OPEN' if self.mouth_open else 'CLOSED'}")

    def set_flippers(self, up):
        self.flippers_up = up
        cmd = "TUX_CMD:FLIPPERS:UP" if self.flippers_up else "TUX_CMD:FLIPPERS:DOWN"
        self.send_cmd(cmd)
        if self.btn_flippers:
            lbl = self.btn_flippers.get_child(0)
            if lbl: lbl.set_text(f"Flippers: {'UP' if self.flippers_up else 'DOWN'}")

    def set_leds(self, on):
        self.leds_on = on
        cmd = "TUX_CMD:LED:ON:LED_BOTH:255" if self.leds_on else "TUX_CMD:LED:OFF:LED_BOTH"
        self.send_cmd(cmd)
        if self.btn_leds:
            lbl = self.btn_leds.get_child(0)
            if lbl: lbl.set_text(f"LEDs: {'ON' if self.leds_on else 'OFF'}")

    # --- UI CALLBACKS (Toggle Handlers) ---

    def toggle_eyes(self, btn):
        self.set_eyes(not self.eyes_open)

    def toggle_mouth(self, btn):
        self.set_mouth(not self.mouth_open)

    def toggle_flippers(self, btn):
        self.set_flippers(not self.flippers_up)

    def toggle_leds(self, btn):
        self.set_leds(not self.leds_on)

    def enter(self, on_exit=None):
        self.on_exit = on_exit
        self.controls = []
        
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Main Content Area (Split Left/Right) - Full Screen
        main_cont = lv.obj(self.screen)
        main_cont.set_size(400, 300) 
        main_cont.align(lv.ALIGN.TOP_MID, 0, 0) 
        main_cont.set_style_border_width(0, 0)
        main_cont.set_style_bg_opa(0, 0)

        # Left Column: Controls (60% width)
        left_col = lv.obj(main_cont)
        left_col.set_size(240, lv.pct(100))
        left_col.align(lv.ALIGN.TOP_LEFT, -30, 0) 
        left_col.set_style_border_width(0, 0)
        left_col.set_style_bg_opa(0, 0)
        left_col.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        left_col.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        left_col.set_style_pad_gap(6, 0) 
        left_col.set_style_pad_top(5, 0) 
        
        # Right Column: Status (Widened for IR)
        right_col = lv.obj(main_cont)
        right_col.set_size(175, lv.pct(100)) 
        right_col.align(lv.ALIGN.TOP_RIGHT, 0, 0)
        right_col.set_style_border_width(0, 0)
        right_col.set_style_bg_opa(0, 0)
        right_col.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        right_col.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
        right_col.set_style_pad_gap(8, 0)
        right_col.set_style_pad_left(10, 0)
        right_col.set_style_pad_top(5, 0)

        # --- Left Column: Buttons ---
        self.btn_eyes, _ = self.create_btn(left_col, "Eyes: OPEN", self.toggle_eyes)
        self.btn_mouth, _ = self.create_btn(left_col, "Mouth: CLOSED", self.toggle_mouth)
        self.btn_flippers, _ = self.create_btn(left_col, "Flippers: DOWN", self.toggle_flippers)
        self.btn_leds, _ = self.create_btn(left_col, f"LEDs: {'ON' if self.leds_on else 'OFF'}", self.toggle_leds)
        self.create_btn(left_col, "Reset", "RESET_POS")

        # --- Right Column: Status Indicators ---
        self.status_labels['dongle'] = lv.label(right_col)
        self.status_labels['dongle'].set_text("Dongle: ?")
        
        self.status_labels['rf'] = lv.label(right_col)
        self.status_labels['rf'].set_text("RF: ?")
        
        self.status_labels['batt'] = lv.label(right_col)
        self.status_labels['batt'].set_text("Batt: ?")
        
        self.status_labels['head'] = lv.label(right_col)
        self.status_labels['head'].set_text("Head: ?")

        self.status_labels['ir'] = lv.label(right_col)
        self.status_labels['ir'].set_text("IR: ?")

        # Init Tux Driver
        self.init_tux()
        
        self.poll_counter = 0
        self.poll_timer = lv.timer_create(lambda _: self.poll_tux(), 50, None)

        import input
        if input.driver and input.driver.group:
            g = input.driver.group
            g.remove_all_objs()
            for obj in self.controls:
                g.add_obj(obj)
            if self.controls:
                lv.group_focus_obj(self.controls[0])
        
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        # Send initial state
        if self.eyes_open: self.send_cmd("TUX_CMD:EYES:OPEN")
        if self.leds_on: self.send_cmd("TUX_CMD:LED:ON:LED_BOTH:255")
        
        lv.async_call(lambda _: self.update_all_labels(), None)

    def poll_tux(self):
        """Called periodically to poll the Tux Driver."""
        if self.tux_drv:
            try:
                self.tux_drv.Poll()
                self.poll_counter += 1
                if self.poll_counter >= 10:
                     self.poll_counter = 0
                     # DEBUG HEAD STATUS
                     try: 
                         head_raw = self.tux_drv.GetAttribute("head_button")
                         # self.log_debug(f"HEAD POLL: {head_raw}")
                     except: pass
                     self.update_all_labels()
            except: pass

    def init_tux(self):
        try:
            # Look for libtuxdriver.so in relative path first
            lib_path = "./libtuxdriver/unix/libtuxdriver.so"
            print(f"Loading libtuxdriver from {lib_path}")
            self.tux_drv = TuxDrv(lib_path)
            if self.tux_drv and self.tux_drv.tux_driver_lib:
                self.tux_drv.SetLogLevel(LOG_LEVEL_INFO)
                try:
                    self.tux_drv.tux_driver_lib.func("v", "TuxDrv_SetLogTarget", "i")(1)
                except: pass
                
                self.tux_drv.SetStatusCallback(self.on_status_event)
                self.tux_drv.SetDongleConnectedCallback(self.on_dongle_connected)
                
                self.tux_drv.Start()
                self.log_debug("Tux Driver Started")
                self.update_all_labels()
        except Exception as e:
            self.log_debug(f"Init Error: {e}")

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
