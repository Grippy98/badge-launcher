import app
import lvgl as lv
import os
import time
import input

class WiFiApp(app.App):
    def __init__(self):
        super().__init__("WiFi")
        # self.name assigned by super
        self.screen = None
        self.list_cont = None
        self.status_label = None
        self.keyboard = None
        self.ta = None
        self.connect_btn = None
        self.selected_ssid = None
        self.scanning = False
        self.scan_results = {} # Store metadata like security
        
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
            # Use os.system and redirect to tmp file since subprocess is missing
            tmp_file = "/tmp/wifi_cmd.out"
            res = os.system(f"{cmd} > {tmp_file} 2>&1")
            
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
        
        # Style setup
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        
        # Main layout
        self.render_main_menu()
        
    def render_main_menu(self):
        self.screen.clean()
        
        # Reset input group
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()

        # Title
        title = lv.label(self.screen)
        title.set_text("WiFi Settings")
        title.align(lv.ALIGN.TOP_MID, 0, 10)
        
        # Status Label
        self.status_label = lv.label(self.screen)
        self.status_label.set_width(380)
        self.status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.status_label.align(lv.ALIGN.TOP_MID, 0, 40)
        self.update_status()
        
        # Check connection state for Disconnect button
        is_connected = False
        try:
             status_out = self.run_command("nmcli -t -f GENERAL.STATE dev show wlan0")
             if status_out and ":100" in status_out: # 100 is connected
                 is_connected = True
        except: pass

        # Buttons Container
        btn_cont = lv.obj(self.screen)
        btn_cont.set_size(300, lv.SIZE_CONTENT) # Auto-height
        btn_cont.center() # Center accurately
        btn_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        btn_cont.set_style_border_width(0, 0)
        
        # Scan Button
        btn_scan = lv.button(btn_cont)
        btn_scan.set_width(lv.pct(100))
        lbl_scan = lv.label(btn_scan)
        lbl_scan.set_text("Scan Networks")
        lbl_scan.center()
        btn_scan.add_style(self.style_btn_rel, 0)
        btn_scan.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn_scan.add_event_cb(self.on_scan_click, lv.EVENT.CLICKED, None)
        
        if is_connected:
            btn_disc = lv.button(btn_cont)
            btn_disc.set_width(lv.pct(100))
            lbl_disc = lv.label(btn_disc)
            lbl_disc.set_text("Disconnect")
            lbl_disc.center()
            btn_disc.add_style(self.style_btn_rel, 0)
            btn_disc.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
            btn_disc.add_event_cb(self.disconnect, lv.EVENT.CLICKED, None)
        
        # Back Button
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
            if is_connected:
                 input.driver.group.add_obj(btn_disc)
            input.driver.group.add_obj(btn_back)
            lv.group_focus_obj(btn_scan)

    def disconnect(self, e):
        self.status_label.set_text("Disconnecting...")
        lv.refr_now(None)
        lv.async_call(lambda _: self.perform_disconnect(), None)

    def perform_disconnect(self):
        self.run_command("nmcli dev disconnect wlan0")
        self.render_main_menu()

    def update_status(self):
        # -t makes it easier to parse: field:value
        output = self.run_command("nmcli -f GENERAL.STATE,IP4.ADDRESS dev show wlan0")
        if output:
            lines = output.strip().split('\n')
            state_str = "Unknown"
            ip_str = ""
            
            for line in lines:
                if "GENERAL.STATE" in line:
                    # E.g. "GENERAL.STATE: 100 (connected)" or just "30 (disconnected)"
                    # or "GENERAL.STATE: 30 (disconnected)"
                    val = line.split(":", 1)[-1].strip()
                    code = val.split()[0]
                    if code == "100": state_str = "Connected"
                    elif code == "30": state_str = "Disconnected"
                    elif code == "20": state_str = "Unavailable"
                    else: state_str = val # Fallback
                elif "IP4.ADDRESS" in line:
                    val = line.split(":", 1)[-1].strip()
                    # ip/cidr e.g. 192.168.1.126/24
                    ip_str = val.split("/")[0]

            if state_str == "Connected" and ip_str:
                self.status_label.set_text(f"Connected: {ip_str}")
            else:
                self.status_label.set_text(state_str)
        else:
            self.status_label.set_text("Status: Unknown")

    def on_scan_click(self, e):
        self.status_label.set_text("Scanning...")
        # Defer scan to allow UI update
        lv.async_call(self.perform_scan, None)

    def perform_scan(self, _):
        # Create a temporary list container
        self.screen.clean()
        
        # Reset input group
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()

        title = lv.label(self.screen)
        title.set_text("Select Network")
        title.align(lv.ALIGN.TOP_MID, 0, 5)

        self.list_cont = lv.obj(self.screen)
        self.list_cont.set_size(380, 220) # Reduced height to prevent off-screen clipping
        self.list_cont.align(lv.ALIGN.CENTER, 0, 10)
        self.list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list_cont.set_style_pad_all(5, 0)
        self.list_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF) # Disable scrollbar
        
        # Use -t (terse) for simpler parsing with : separator
        # Note: SSID can contain spaces, but with -t it's usually Escaped or : separated
        # Simple split might fail if SSID has : but typically rare.
        # Let's assume standard 3 parts.
        output = self.run_command("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list --rescan yes")
        
        if output:
            lines = output.strip().split('\n')
            seen_ssids = set()
            for line in lines:
                # Format: SSID:SIGNAL:SECURITY
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid = parts[0]
                    signal = parts[1]
                    security = parts[2] if len(parts) > 2 else ""
                    self.scan_results[ssid] = security
                    
                    # Filter empty or dummy ssids
                    if not ssid or ssid == "--": continue
                    
                    if ssid not in seen_ssids:
                        seen_ssids.add(ssid)
                        btn = lv.button(self.list_cont)
                        btn.set_width(lv.pct(100))
                        lbl = lv.label(btn)
                        lbl.set_text(f"{ssid} ({signal}%)")
                        
                        btn.add_style(self.style_btn_rel, 0)
                        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
                        btn.add_event_cb(lambda e, s=ssid: self.on_ssid_click(s), lv.EVENT.CLICKED, None)
                        btn.add_event_cb(self.on_list_key, lv.EVENT.KEY, None)
                        if input.driver and input.driver.group:
                            input.driver.group.add_obj(btn)

        # Back Button in list
        btn_back = lv.button(self.list_cont)
        btn_back.set_style_bg_color(lv.palette_main(lv.PALETTE.RED), 0) # Overridden by style if added last? No.
        # Actually replace red style with ours for consistency? Or keep it special? User asked for similar to main menu.
        # Main menu has no red cancel. Let's stick to B&W.
        btn_back.remove_style_all() # Clear raw styles
        btn_back.set_width(lv.pct(100))
        btn_back.set_height(40) # Ensure height matches others if needed
        btn_back.add_style(self.style_btn_rel, 0)
        btn_back.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        
        lbl_back = lv.label(btn_back)
        lbl_back.set_text("Cancel")
        lbl_back.center()
        btn_back.add_event_cb(lambda e: self.render_main_menu(), lv.EVENT.CLICKED, None)
        
        if input.driver and input.driver.group:
            input.driver.group.add_obj(btn_back)
            # Focus first item if available
            if self.list_cont.get_child_count() > 1:
                lv.group_focus_obj(self.list_cont.get_child(0))
            else:
                 lv.group_focus_obj(btn_back)

    def on_ssid_click(self, ssid):
        self.selected_ssid = ssid
        # Check security
        sec = self.scan_results.get(ssid, "")
        # nmcli -t often returns "--" for open, or sometimes just empty depending on version
        if not sec or sec == "--" or "NONE" in sec.upper():
             self.connect_open()
        else:
             self.show_password_entry()

    def connect_open(self):
        self.screen.clean()
        msg = lv.label(self.screen)
        msg.set_text(f"Connecting to {self.selected_ssid}...")
        msg.center()
        
        lv.refr_now(None)
        lv.async_call(lambda _: self.perform_connect_open(), None)

    def perform_connect_open(self):
        # Ensure fresh start
        self.run_command(f"nmcli con delete id '{self.selected_ssid}'")
        
        # Open network connection
        cmd = f"nmcli dev wifi connect '{self.selected_ssid}'"
        res = self.run_command(cmd)
        self.show_connection_result(res)

    def show_connection_result(self, res):
        self.screen.clean()
        res_lbl = lv.label(self.screen)
        res_lbl.set_width(380)
        
        if res and "successfully activated" in res:
             res_lbl.set_text("Connected Successfully!")
        else:
             res_lbl.set_text(f"Failed:\n{res}")
             
        res_lbl.center()
        
        btn = lv.button(self.screen)
        btn.align(lv.ALIGN.BOTTOM_MID, 0, -20)
        lbl = lv.label(btn)
        lbl.set_text("OK")
        btn.add_style(self.style_btn_rel, 0)
        btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn.add_event_cb(lambda e: self.render_main_menu(), lv.EVENT.CLICKED, None)
        
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(btn)
            lv.group_focus_obj(btn)

    def show_password_entry(self):
        self.screen.clean()
        self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF) # No scroll
        
        # Title
        title = lv.label(self.screen)
        title.set_text(f"Password for {self.selected_ssid}")
        title.align(lv.ALIGN.TOP_MID, 0, 40)
        
        # Styled Password Box
        self.ta = lv.textarea(self.screen)
        self.ta.set_one_line(True)
        self.ta.set_password_mode(True)
        self.ta.set_width(280)
        self.ta.set_style_border_width(2, 0)
        self.ta.set_style_border_color(lv.color_black(), 0)
        self.ta.set_style_pad_all(10, 0)
        self.ta.center()
        
        # Connect Button (Visual cue)
        btn_conn = lv.button(self.screen)
        btn_conn.align(lv.ALIGN.BOTTOM_MID, 0, -40)
        lbl_conn = lv.label(btn_conn)
        lbl_conn.set_text("Connect (Enter)")
        btn_conn.add_style(self.style_btn_rel, 0)
        btn_conn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)
        btn_conn.add_event_cb(lambda e: self.connect(), lv.EVENT.CLICKED, None)
        
        # Register events
        self.ta.add_event_cb(self.on_ta_key, lv.EVENT.KEY, None)

        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.ta)
            input.driver.group.add_obj(btn_conn)
            lv.group_focus_obj(self.ta)

    def on_ta_key(self, e):
        key = e.get_key()
        
        # Global Back
        if key == lv.KEY.ESC:
            self.render_main_menu()
            return

        # Enter triggers connect
        if key == lv.KEY.ENTER or key == 10 or key == 13: 
            self.connect()

    def on_list_key(self, e):
        # Handle back from list
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.render_main_menu()

    def connect(self):
        password = self.ta.get_text()
        
        self.screen.clean()
        msg = lv.label(self.screen)
        msg.set_text(f"Connecting to {self.selected_ssid}...")
        msg.center()
        
        lv.refr_now(None)
        
        # Run connection command (blocking slightly bad but ok for simple app)
        # Using async_call better
        lv.async_call(lambda _: self.perform_connect(password), None)

    def perform_connect(self, password):
        # Ensure fresh start to prevent "key-mgmt property missing" errors
        # caused by trying to update a mismatched existing profile
        self.run_command(f"nmcli con delete id '{self.selected_ssid}'")
        
        cmd = f"nmcli dev wifi connect '{self.selected_ssid}' password '{password}'"
        res = self.run_command(cmd)
        self.show_connection_result(res)

    def exit(self):
        if self.on_exit:
            self.on_exit()

