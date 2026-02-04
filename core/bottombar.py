"""Bottom status bar displaying network and USB device information.

Shows Ethernet/WiFi connection status with IP address and USB device count.
"""

import lvgl as lv
import os

class BottomBar:
    """Bottom bar showing network interface and USB status.

    Displays connection status prioritizing Ethernet over WiFi,
    with IP address and USB device count.
    """
    def __init__(self):
        self.container = lv.obj(lv.layer_top())
        self.container.set_size(lv.pct(100), 22)
        # Inverted Colors: White BG, Black Text
        self.container.set_style_bg_color(lv.color_white(), 0)
        self.container.set_style_bg_opa(lv.OPA._80, 0)
        self.container.set_style_radius(0, 0)
        
        # Start hidden (Menu will show it)
        self.container.set_y(100) # Offscreen down
        
        # Border Divider (Top)
        self.container.set_style_border_width(2, 0)
        self.container.set_style_border_color(lv.color_black(), 0)
        self.container.set_style_border_side(lv.BORDER_SIDE.TOP, 0)
        
        # Labels - New Order: ETH (Left), WIFI (Center), USB (Right)
        
        # ETH (Left)
        self.lbl_eth = lv.label(self.container)
        self.lbl_eth.set_text("")
        self.lbl_eth.set_style_text_color(lv.color_black(), 0)

        self.lbl_eth.align(lv.ALIGN.LEFT_MID, 5, 0)
        try:
            self.lbl_eth.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        
        # USB (Right)
        self.lbl_usb = lv.label(self.container)
        self.lbl_usb.set_text("")
        self.lbl_usb.set_style_text_color(lv.color_black(), 0)
        self.lbl_usb.align(lv.ALIGN.RIGHT_MID, -5, 0)
        try:
            self.lbl_usb.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        
        # Timer (Update every 10000ms for E-ink to reduce flashing)
        # Network status changes infrequently, so 10s is reasonable
        self.timer = lv.timer_create(self.update, 10000, None)

        # Check if we're on macOS/BSD (SDL mode) - pause timer to avoid flickering
        import sys
        if sys.platform in ['darwin', 'freebsd', 'openbsd', 'netbsd']:
            self.timer.set_period(0)  # Pause timer
            # Set static empty values for SDL mode
            self.lbl_eth.set_text("")
            self.lbl_usb.set_text("")
        else:
            self.update(None)

    def get_ip_address(self, iface):
        """Get IPv4 address for a network interface.

        Args:
            iface: Network interface name (e.g., 'eth0', 'wlan0')

        Returns:
            IP address string or None if not found
        """
        try:
            # os.popen missing, use os.system redirect
            os.system(f"ip -4 addr show {iface} > /tmp/ip_status.txt")
            with open("/tmp/ip_status.txt", "r") as f:
                for line in f:
                    if "inet " in line:
                        # inet 192.168.1.128/24 ...
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            ip = parts[1].split('/')[0]
                            return ip
        except: pass
        return None

    def get_net_status(self, iface_prefix):
        """Check if a network interface matching prefix is up.

        Args:
            iface_prefix: Interface name prefix (e.g., 'en', 'eth', 'wl')

        Returns:
            Tuple of (is_up: bool, interface_name: str or None)
        """
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

    def get_usb_count(self):
        """Count connected USB devices.

        Returns:
            Number of USB devices (excludes USB hubs and virtual devices)
        """
        try:
            count = 0
            for d in os.listdir('/sys/bus/usb/devices/'):
                if d.startswith('usb'): continue
                if ':' in d: continue
                count += 1
            return count
        except: return 0

    def update(self, t):
        """Update bottom bar display with current network and USB status.

        Args:
            t: Timer parameter (unused, required by LVGL timer callback)
        """
        # Network Status Priority: Ethernet > Wifi
        iface = None
        icon = ""

        # Check Ethernet
        eth_up, eth_iface = self.get_net_status("en")
        if not eth_up: eth_up, eth_iface = self.get_net_status("eth")

        if eth_up and eth_iface:
            iface = eth_iface
            icon = lv.SYMBOL.ETHERNET if hasattr(lv.SYMBOL, 'ETHERNET') else "ETH"
        else:
            # Check Wifi if Ethernet is down
            wifi_up, wifi_iface = self.get_net_status("wl")
            if wifi_up and wifi_iface:
                iface = wifi_iface
                icon = lv.SYMBOL.WIFI if hasattr(lv.SYMBOL, 'WIFI') else "WIFI"

        # Only update if text has changed
        new_eth_text = ""
        if iface:
            ip = self.get_ip_address(iface)
            display_name = iface
            # Truncate if too long (e.g. enx00e04c...)
            if len(display_name) > 10:
                display_name = display_name[:8] + ".."

            if ip:
                new_eth_text = f"{icon} {display_name} {ip}"
            else:
                new_eth_text = f"{icon} {display_name}"

        if self.lbl_eth.get_text() != new_eth_text:
            self.lbl_eth.set_text(new_eth_text)

        # USB - only update if changed
        cnt = self.get_usb_count()
        new_usb_text = ""
        if cnt > 2:
            sym = lv.SYMBOL.USB if hasattr(lv.SYMBOL, 'USB') else "USB"
            new_usb_text = f"{sym} {cnt}"

        if self.lbl_usb.get_text() != new_usb_text:
            self.lbl_usb.set_text(new_usb_text)

    def show(self):
        """Show the bottom bar and restore default styling."""
        try:
            self.container.remove_flag(lv.obj.FLAG.HIDDEN)
        except: pass
        self.container.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.container.set_size(lv.pct(100), 22)
        self.container.set_style_bg_opa(lv.OPA._80, 0)
        self.container.set_style_border_width(2, 0)

    def hide(self):
        """Hide the bottom bar by moving it offscreen and clearing styling."""
        try:
            self.container.add_flag(lv.obj.FLAG.HIDDEN)
        except: pass
        self.container.align(lv.ALIGN.BOTTOM_MID, 0, 100) # Offscreen down
        self.container.set_size(0, 0)
        self.container.set_style_bg_opa(0, 0)
        self.container.set_style_border_width(0, 0)
