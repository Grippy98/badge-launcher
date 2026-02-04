"""System information application.

Displays system details including OS version, kernel, memory usage,
storage, and CPU information.
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import os

class AboutApp(app.App):
    def __init__(self):
        super().__init__("About")
        self.screen = None
        
    def get_info(self):
        info = []
        
        # Distro
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split('=')[1].strip().strip('"')
                        info.append(f"OS: {distro}")
                        break
        except:
            info.append("OS: Unknown Linux")

        # Kernel
        try:
            with open('/proc/sys/kernel/osrelease', 'r') as f:
                kver = f.read().strip()
                info.append(f"Kernel: {kver}")
        except: pass
            
        # Memory
        try:
            total = 0
            avail = 0
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        total = int(line.split()[1]) // 1024 # MB
                    elif line.startswith('MemAvailable:'):
                        avail = int(line.split()[1]) // 1024 # MB
            info.append(f"RAM: {avail}MB / {total}MB Free")
        except:
             info.append("RAM: N/A")
             
        # Storage
        try:
            st = os.statvfs('/')
            # Micropython statvfs returns tuple usually
            bsize = st[0]
            total = (bsize * st[2]) / 1024 / 1024 / 1024 # GB
            free = (bsize * st[3]) / 1024 / 1024 / 1024 # GB
            info.append(f"Disk: {free:.1f}GB / {total:.1f}GB Free")
        except:
             info.append("Disk: N/A")

        # Versions
        try:
            mp_ver = sys.version.split(' ')[0].strip(';')
            info.append(f"MicroPython: {mp_ver}")
        except: pass
        
        try:
            ver = f"{lv.version_major()}.{lv.version_minor()}.{lv.version_patch()}"
            info.append(f"LVGL: {ver}")
        except: pass

        return "\n".join(info)

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
        
        # Main Container
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_style_pad_all(20, 0)
        cont.set_style_border_width(0, 0)
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_style_pad_gap(10, 0)
        
        # Title
        title = lv.label(cont)
        title.set_text("System Info")
        try:
            title.set_style_text_font(lv.font_montserrat_24, 0)
        except: 
            try:
                 title.set_style_text_font(lv.font_montserrat_20, 0)
            except: pass
        title.set_style_text_color(lv.color_black(), 0)
        
        # Divider
        line = lv.obj(cont)
        line.set_size(lv.pct(100), 2)
        line.set_style_bg_color(lv.color_black(), 0)
        line.set_style_bg_opa(lv.OPA.COVER, 0)

        # Info Items
        info_str = self.get_info()
        lines = info_str.split("\n")
        
        for line_text in lines:
            lbl = lv.label(cont)
            lbl.set_text(line_text)
            lbl.set_style_text_color(lv.color_black(), 0)
            lbl.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
            try:
                lbl.set_style_text_font(lv.font_montserrat_16, 0)
            except: pass

        # Footer Hint
        hint = lv.label(self.screen)
        hint.set_text("Press BACK to Exit")
        hint.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        try:
            hint.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        hint.set_style_text_color(lv.color_black(), 0)
        
    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC or key == lv.KEY.BACKSPACE or key == 14 or key == lv.KEY.LEFT:
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
            
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
