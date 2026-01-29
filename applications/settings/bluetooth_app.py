import app
import lvgl as lv
import os
import time
import input

class BluetoothApp(app.App):
    def __init__(self):
        super().__init__("Bluetooth")
        self.name = "Bluetooth"
        self.screen = None
        self.list_cont = None
        self.status_label = None
        
        # Styles
        self.style_btn_rel = lv.style_t()
        self.style_btn_rel.init()
        self.style_btn_rel.set_radius(0)
        self.style_btn_rel.set_border_width(1)
        self.style_btn_rel.set_border_color(lv.color_black())
        self.style_btn_rel.set_bg_color(lv.color_white())
        self.style_btn_rel.set_text_color(lv.color_black())

        self.style_btn_foc = lv.style_t()
        self.style_btn_foc.init()
        self.style_btn_foc.set_bg_color(lv.color_black())
        self.style_btn_foc.set_text_color(lv.color_white())

    def run_command(self, cmd):
        try:
            tmp_file = "/tmp/bt_cmd.out"
            os.system(f"{cmd} > {tmp_file} 2>&1")
            output = ""
            try:
                with open(tmp_file, 'r') as f:
                    output = f.read()
            except: pass
            return output
        except Exception as e:
            print(f"Error running cmd '{cmd}': {e}")
            return None

    def enter(self, on_exit=None):
        self.on_exit = on_exit
        if not self.screen:
            self.screen = lv.obj()
        lv.screen_load(self.screen)
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        self.render_main_menu()

    def render_main_menu(self):
        self.screen.clean()
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()

        title = lv.label(self.screen)
        title.set_text("Bluetooth")
        title.align(lv.ALIGN.TOP_MID, 0, 10)

        self.status_label = lv.label(self.screen)
        self.status_label.set_width(380)
        self.status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.status_label.align(lv.ALIGN.TOP_MID, 0, 40)
        self.update_status()

        btn_cont = lv.obj(self.screen)
        btn_cont.set_size(300, lv.SIZE_CONTENT)
        btn_cont.center()
        btn_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        btn_cont.set_style_border_width(0, 0)

        # Scan
        btn_scan = lv.button(btn_cont)
        btn_scan.set_width(lv.pct(100))
        lbl_scan = lv.label(btn_scan)
        lbl_scan.set_text("Scan Devices")
        lbl_scan.center()
        btn_scan.add_style(self.style_btn_rel, 0)
        btn_scan.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn_scan.add_event_cb(self.on_scan_click, lv.EVENT.CLICKED, None)
        
        # Back
        btn_back = lv.button(btn_cont)
        btn_back.set_width(lv.pct(100))
        lbl_back = lv.label(btn_back)
        lbl_back.set_text("Back")
        lbl_back.center()
        btn_back.add_style(self.style_btn_rel, 0)
        btn_back.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn_back.add_event_cb(lambda e: self.exit(), lv.EVENT.CLICKED, None)

        if input.driver and input.driver.group:
            input.driver.group.add_obj(btn_scan)
            input.driver.group.add_obj(btn_back)
            lv.group_focus_obj(btn_scan)
            
    def update_status(self):
        # Avoid blocking 'bluetoothctl info'
        # Just show generic status or implement sysfs check later
        self.status_label.set_text("Ready to Scan")

    def on_scan_click(self, e):
        self.status_label.set_text("Scanning... (10s)")
        lv.refr_now(None)
        lv.async_call(self.perform_scan, None)

    def perform_scan(self, _):
        # Start background scan
        # We use & to run in background. 
        # Note: on micropython os.system with & might not be fully supported if shell is limited, 
        # but typical linux sh works.
        self.run_command("bluetoothctl scan on > /dev/null 2>&1 &")
        
        # Schedule finish in 5 seconds
        # We need a timer. lv_utils usually patches machine.Timer or we use lv_timer
        # Let's use lv.timer_create
        lv.timer_create(self.finish_scan, 5000, None)

    def finish_scan(self, timer):
        try:
            lv.timer_delete(timer)
            self.run_command("killall bluetoothctl") # Ensure scan stops
            
            # Get list
            output = self.run_command("bluetoothctl devices")
            
            if not output or not output.strip():
                 self.show_error("Bluetooth Timeout:\nNo devices found.")
            else:
                 self.show_list(output)
        except Exception as e:
            print(f"Scan Error: {e}")
            self.show_error(f"Scan Error:\n{e}")

    def show_error(self, message):
        self.screen.clean()
        msg = lv.label(self.screen)
        msg.set_width(380)
        msg.set_text(message)
        msg.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        msg.center()
        
        btn = lv.button(self.screen)
        btn.align(lv.ALIGN.BOTTOM_MID, 0, -20)
        lbl = lv.label(btn)
        lbl.set_text("Back")
        btn.add_style(self.style_btn_rel, 0)
        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn.add_event_cb(lambda e: self.render_main_menu(), lv.EVENT.CLICKED, None)
        
        if input.driver and input.driver.group:
             input.driver.group.remove_all_objs()
             input.driver.group.add_obj(btn)
             lv.group_focus_obj(btn)
        
    def show_list(self, output):
        self.screen.clean()
        title = lv.label(self.screen)
        title.set_text("Select Device")
        title.align(lv.ALIGN.TOP_MID, 0, 5)
        
        self.list_cont = lv.obj(self.screen)
        self.list_cont.set_size(380, 220)
        self.list_cont.align(lv.ALIGN.CENTER, 0, 10)
        self.list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list_cont.set_style_pad_all(5, 0)
        self.list_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
        
        if output:
            lines = output.strip().split('\n')
            for line in lines:
                # Device MAC Name
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                     mac = parts[1]
                     name = parts[2]
                     
                     btn = lv.button(self.list_cont)
                     btn.set_width(lv.pct(100))
                     lbl = lv.label(btn)
                     lbl.set_text(f"{name}")
                     btn.add_style(self.style_btn_rel, 0)
                     btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
                     # Callback
                     btn.add_event_cb(lambda e, m=mac, n=name: self.connect_device(m, n), lv.EVENT.CLICKED, None)
                     btn.add_event_cb(self.on_list_key, lv.EVENT.KEY, None)
                     
                     if input.driver and input.driver.group:
                         input.driver.group.add_obj(btn)
                         
        # Cancel
        btn_back = lv.button(self.list_cont)
        btn_back.set_width(lv.pct(100))
        lbl_back = lv.label(btn_back)
        lbl_back.set_text("Cancel")
        lbl_back.center()
        btn_back.add_style(self.style_btn_rel, 0)
        btn_back.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn_back.add_event_cb(lambda e: self.render_main_menu(), lv.EVENT.CLICKED, None)
        
        if input.driver and input.driver.group:
            input.driver.group.add_obj(btn_back)
            if self.list_cont.get_child_count() > 1:
                 lv.group_focus_obj(self.list_cont.get_child(0))
            else:
                 lv.group_focus_obj(btn_back)

    def on_list_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.render_main_menu()

    def connect_device(self, mac, name):
        self.screen.clean()
        msg = lv.label(self.screen)
        msg.set_text(f"Connecting to {name}...")
        msg.center()
        lv.refr_now(None)
        lv.async_call(lambda _: self.perform_connect(mac), None)

    def perform_connect(self, mac):
        # Trust, Pair, Connect
        self.run_command(f"bluetoothctl trust {mac}")
        self.run_command(f"bluetoothctl pair {mac}")
        res = self.run_command(f"bluetoothctl connect {mac}")
        
        self.screen.clean()
        res_lbl = lv.label(self.screen)
        res_lbl.set_width(380)
        if res and "...Connection successful" in res: 
             res_lbl.set_text("Connected!")
        elif res and "Connection successful" in res:
             res_lbl.set_text("Connected!")
        else:
             # Shorten error to last bit if possible
             res_lbl.set_text(f"Failed:\n{res[-80:] if res else 'Unknown'}")
        res_lbl.center()
        
        btn = lv.button(self.screen)
        btn.align(lv.ALIGN.BOTTOM_MID, 0, -20)
        lbl = lv.label(btn)
        lbl.set_text("OK")
        btn.add_event_cb(lambda e: self.render_main_menu(), lv.EVENT.CLICKED, None)
        
        if input.driver and input.driver.group:
             input.driver.group.remove_all_objs()
             input.driver.group.add_obj(btn)
             lv.group_focus_obj(btn)

    def exit(self):
        if self.on_exit:
            self.on_exit()
