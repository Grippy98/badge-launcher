"""System status bar displaying CPU, RAM, battery, WiFi, and Bluetooth status.

Monitors system resources via /proc and /sys, updating every 2 seconds.
"""

import lvgl as lv
import os
import time

class StatusBar:
    def __init__(self):
        self.container = lv.obj(lv.layer_top())
        self.container.set_size(lv.pct(100), 22)
        # Inverted Colors: White BG, Black Text
        self.container.set_style_bg_color(lv.color_white(), 0)
        self.container.set_style_bg_opa(lv.OPA._80, 0)
        self.container.set_style_radius(0, 0)
        self.container.align(lv.ALIGN.TOP_MID, 0, 0)
        
        # Border Divider (Underline)
        self.container.set_style_border_width(2, 0)
        self.container.set_style_border_color(lv.color_black(), 0)
        self.container.set_style_border_side(lv.BORDER_SIDE.BOTTOM, 0)
        
        # Labels
        self.lbl_cpu = lv.label(self.container)
        self.lbl_cpu.set_text("CPU: --%")
        self.lbl_cpu.set_style_text_color(lv.color_black(), 0)
        self.lbl_cpu.align(lv.ALIGN.LEFT_MID, 5, 0)
        
        self.lbl_mem = lv.label(self.container)
        self.lbl_mem.set_text("RAM: --%")
        self.lbl_mem.set_style_text_color(lv.color_black(), 0)
        self.lbl_mem.align(lv.ALIGN.CENTER, 0, 0)
        
        self.lbl_bat = lv.label(self.container)
        self.lbl_bat.set_text("BAT: --%")
        self.lbl_bat.set_style_text_color(lv.color_black(), 0)
        self.lbl_bat.align(lv.ALIGN.RIGHT_MID, -5, 0)
        
        self.lbl_wifi = lv.label(self.container)
        self.lbl_wifi.set_text("")
        self.lbl_wifi.set_style_text_color(lv.color_black(), 0)
        self.lbl_wifi.align(lv.ALIGN.RIGHT_MID, -90, 0) # Shifted Left
        
        self.lbl_bt = lv.label(self.container)
        self.lbl_bt.set_text("")
        self.lbl_bt.set_style_text_color(lv.color_black(), 0)
        self.lbl_bt.align(lv.ALIGN.RIGHT_MID, -70, 0) # Between Wifi and Bat
        
        # State for CPU calc
        self.last_idle = 0
        self.last_total = 0
        
        # Timer (Update every 5000ms for E-ink to reduce flashing)
        # For E-ink displays, less frequent updates = less flashing
        self.timer = lv.timer_create(self.update, 5000, None)

        # Check if we're on macOS/BSD (SDL mode) - pause timer to avoid flickering
        import sys
        if sys.platform in ['darwin', 'freebsd', 'openbsd', 'netbsd']:
            self.timer.set_period(0)  # Pause timer
            # Set static values for SDL mode
            self.lbl_cpu.set_text("CPU: --")
            self.lbl_mem.set_text("MEM: --")
            self.lbl_bat.set_text("BAT: --")
            self.lbl_wifi.set_text("")
            self.lbl_bt.set_text("")
        else:
            self.update(None)

    def get_cpu_usage(self):
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                parts = line.split()
                # user+nice+system+idle+iowait+irq+softirq
                idle = int(parts[4])
                total = sum(int(x) for x in parts[1:8])
                
                diff_idle = idle - self.last_idle
                diff_total = total - self.last_total
                
                self.last_idle = idle
                self.last_total = total
                
                if diff_total == 0: return 0
                return 100 * (1 - diff_idle / diff_total)
        except:
            return 0

    def get_mem_usage(self):
        try:
            total = 0
            avail = 0
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        avail = int(line.split()[1])
                    if total and avail: break
            
            if total == 0: return 0
            used = total - avail
            return (used / total) * 100
        except:
            return 0

    def get_bat_status(self):
        level = -1
        status_char = ""
        try:
            with open('/sys/class/power_supply/bq27541-0/capacity', 'r') as f:
                level = int(f.read().strip())
            
            with open('/sys/class/power_supply/bq27541-0/status', 'r') as f:
                st = f.read().strip()
                if st == "Charging":
                    status_char = lv.SYMBOL.CHARGE if hasattr(lv.SYMBOL, 'CHARGE') else "^"
                elif st == "Discharging" or st == "Not charging":
                    status_char = "v"
                elif st == "Full":
                    status_char = "="
        except:
            pass
        return level, status_char

    def update(self, t):
        cpu = self.get_cpu_usage()
        mem = self.get_mem_usage()
        bat, char = self.get_bat_status()

        # Only update labels if values have changed to avoid unnecessary redraws
        new_cpu_text = f"CPU: {int(cpu)}%"
        if self.lbl_cpu.get_text() != new_cpu_text:
            self.lbl_cpu.set_text(new_cpu_text)

        new_mem_text = f"MEM: {int(mem)}%"
        if self.lbl_mem.get_text() != new_mem_text:
            self.lbl_mem.set_text(new_mem_text)

        if bat >= 0:
            # Determine Battery Icon
            bat_icon = lv.SYMBOL.BATTERY_EMPTY
            if bat > 90: bat_icon = lv.SYMBOL.BATTERY_FULL
            elif bat > 70: bat_icon = lv.SYMBOL.BATTERY_3
            elif bat > 50: bat_icon = lv.SYMBOL.BATTERY_2
            elif bat > 20: bat_icon = lv.SYMBOL.BATTERY_1

            new_bat_text = f"{char} {bat_icon} {bat}%"
            if self.lbl_bat.get_text() != new_bat_text:
                self.lbl_bat.set_text(new_bat_text)
        else:
            if self.lbl_bat.get_text() != "BAT: N/A":
                self.lbl_bat.set_text("BAT: N/A")

        wifi_up, _ = self.get_net_status("wlan")
        new_wifi_text = lv.SYMBOL.WIFI if wifi_up else ""
        if self.lbl_wifi.get_text() != new_wifi_text:
            self.lbl_wifi.set_text(new_wifi_text)

        bt_up = self.get_bt_status()
        new_bt_text = lv.SYMBOL.BLUETOOTH if bt_up else ""
        if self.lbl_bt.get_text() != new_bt_text:
            self.lbl_bt.set_text(new_bt_text)

    def get_bt_status(self):
        try:
            # Check for active connections in sysfs
            # usually /sys/class/bluetooth/hci0/conn*
            base = "/sys/class/bluetooth/hci0"
            if not os.path.exists(base): return False
            
            for d in os.listdir(base):
                if d.startswith("conn"):
                    return True
        except: pass
        return False

    def get_net_status(self, iface_prefix):
        found_iface = None
        is_up = False
        try:
            for d in os.listdir('/sys/class/net/'):
                if d.startswith(iface_prefix):
                    found_iface = d
                    with open(f'/sys/class/net/{d}/operstate', 'r') as f:
                        if f.read().strip() == "up":
                            is_up = True
                    break
        except: pass
        return is_up, found_iface
            
    def show(self):
        try:
            self.container.remove_flag(lv.obj.FLAG.HIDDEN)
        except: pass
        self.container.align(lv.ALIGN.TOP_MID, 0, 0)
        self.container.set_size(lv.pct(100), 22)
        self.container.set_style_bg_opa(lv.OPA._80, 0)
        self.container.set_style_border_width(2, 0)
        
    def hide(self):
        try:
            self.container.add_flag(lv.obj.FLAG.HIDDEN)
        except: pass
        # Move offscreen using alignment to override previous align
        self.container.align(lv.ALIGN.TOP_MID, 0, -100)
        self.container.set_size(0, 0)
        self.container.set_style_bg_opa(0, 0)
        self.container.set_style_border_width(0, 0)
        
        # Force redraw of screen to clear artifacts
        try:
            lv.obj.invalidate(lv.scr_act())
        except: pass
