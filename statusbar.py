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
        self.lbl_bat.set_style_text_color(lv.color_black(), 0)
        self.lbl_bat.align(lv.ALIGN.RIGHT_MID, -5, 0)
        
        self.lbl_wifi = lv.label(self.container)
        self.lbl_wifi.set_text("")
        self.lbl_wifi.set_style_text_color(lv.color_black(), 0)
        self.lbl_wifi.align(lv.ALIGN.RIGHT_MID, -60, 0) # Between Mem and Bat
        
        # State for CPU calc
        self.last_idle = 0
        self.last_total = 0
        
        # Timer (Update every 2000ms)
        self.timer = lv.timer_create(self.update, 2000, None)
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
            free = 0
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
                    status_char = "^"
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
        
        self.lbl_cpu.set_text(f"CPU: {int(cpu)}%")
        self.lbl_mem.set_text(f"MEM: {int(mem)}%")
        
        if bat >= 0:
            self.lbl_bat.set_text(f"{char} {bat}%")
        else:
            self.lbl_bat.set_text("BAT: N/A")
            
        wifi_up, _ = self.get_net_status("wlan")
        if wifi_up:
             self.lbl_wifi.set_text(lv.SYMBOL.WIFI)
        else:
             self.lbl_wifi.set_text("")

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
        print("StatusBar: Showing")
        try:
            self.container.remove_flag(lv.obj.FLAG.HIDDEN)
        except: pass
        self.container.align(lv.ALIGN.TOP_MID, 0, 0)
        self.container.set_size(lv.pct(100), 22)
        self.container.set_style_bg_opa(lv.OPA._80, 0)
        self.container.set_style_border_width(2, 0)
        
    def hide(self):
        print("StatusBar: Hiding")
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
