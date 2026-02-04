"""Input driver for keyboard and badge button events.

Handles Linux input events from /dev/input/event* devices, mapping
scancodes to LVGL keys and ASCII characters.
"""

import lvgl as lv
import uselect
import ustruct
import sys
import os
import ffi

# Load libc for ioctl
try:
    libc = ffi.open("libc.so.6")
    # ioctl(int fd, unsigned long request, void* arg)
    # Using 'L' for request (unsigned long), 'i' for arg (int 1)
    ioctl = libc.func("i", "ioctl", "iLi")
except:
    print("Warning: Could not load libc for ioctl")
    ioctl = None

EVIOCGRAB = 0x40044590

# Key mapping for special/navigation keys
KEY_MAP = {
    103: lv.KEY.PREV,  # KEY_UP -> PREV (Focus Previous)
    108: lv.KEY.NEXT,  # KEY_DOWN -> NEXT (Focus Next)
    105: lv.KEY.LEFT,  # KEY_LEFT
    106: lv.KEY.RIGHT, # KEY_RIGHT
    28:  lv.KEY.ENTER, # KEY_ENTER
    96:  lv.KEY.ENTER, # KEY_KPENTER
    14:  lv.KEY.BACKSPACE, # KEY_BACKSPACE
    1:   lv.KEY.ESC,   # KEY_ESC
    158: lv.KEY.ESC,   # KEY_BACK -> ESC (Universal Exit)
    353: lv.KEY.ENTER, # KEY_SELECT -> ENTER (Universal Select)
    57:  ord(' '),     # KEY_SPACE
}

# Scancode to ASCII
SCAN_TO_ASCII = {
    2: '1', 3: '2', 4: '3', 5: '4', 6: '5', 7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
    16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't', 21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p',
    30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g', 35: 'h', 36: 'j', 37: 'k', 38: 'l',
    44: 'z', 45: 'x', 46: 'c', 47: 'v', 48: 'b', 49: 'n', 50: 'm',
    52: '.', 51: ','
}

SCAN_TO_ASCII_SHIFT = {
    2: '!', 3: '@', 4: '#', 5: '$', 6: '%', 7: '^', 8: '&', 9: '*', 10: '(', 11: ')',
    16: 'Q', 17: 'W', 18: 'E', 19: 'R', 20: 'T', 21: 'Y', 22: 'U', 23: 'I', 24: 'O', 25: 'P',
    30: 'A', 31: 'S', 32: 'D', 33: 'F', 34: 'G', 35: 'H', 36: 'J', 37: 'K', 38: 'L',
    44: 'Z', 45: 'X', 46: 'C', 47: 'V', 48: 'B', 49: 'N', 50: 'M',
    52: ':', 51: '<'
}

class InputDriver:
    """LVGL input driver for Linux input events.

    Polls multiple /dev/input/event* devices, translates scancodes to
    LVGL keys and ASCII, and manages input focus groups.
    """

    def __init__(self):
        self.poll = uselect.poll()
        self.files = {} # fd -> (file_obj, path)
        self.shift_pressed = False
        
        # Try to open likely devices
        self.add_device("/dev/input/event0") # Badge Keys
        
        # Scan for others (keyboard)
        try:
            for entry in os.listdir("/dev/input"):
                if entry.startswith("event") and entry != "event0":
                    path = "/dev/input/" + entry
                    self.add_device(path)
        except Exception as e:
            print(f"Error scanning input devices: {e}")

        if not self.files:
            print("Warning: No input devices opened!")

        self.indev_drv = lv.indev_create()
        self.indev_drv.set_type(lv.INDEV_TYPE.KEYPAD)
        self.indev_drv.set_read_cb(self.read_cb)
        
        # Create a group for keypad input
        self.group = lv.group_create()
        self.group.set_default()
        self.indev_drv.set_group(self.group)
        print("Input driver initialized and group created")
        
        self.last_key = 0
        self.state = lv.INDEV_STATE.RELEASED

    def add_device(self, dev_path):
        """Register an input device for polling.

        Args:
            dev_path: Path to input device (e.g., '/dev/input/event0')
        """
        try:
            f = open(dev_path, "rb")
            self.poll.register(f, uselect.POLLIN)
            self.files[f.fileno()] = (f, dev_path)
            print(f"Registered input device: {dev_path}")
            
            # Grab device to stop TTY interference
            if ioctl:
                try:
                    res = ioctl(f.fileno(), EVIOCGRAB, 1)
                    if res == 0:
                        print(f"  -> Grabbed exclusive access")
                    else:
                        print(f"  -> Grab failed with {res}")
                except Exception as e:
                    print(f"  -> Grab error: {e}")


        except Exception as e:
            print(f"Could not open {dev_path}: {e}")

    def read_cb(self, indev_drv, data):
        """LVGL input callback to read and process input events.

        Args:
            indev_drv: LVGL input device driver
            data: LVGL input data structure to populate
        """
        if not self.files:
            return

        # Poll for data (timeout 0)
        try:
            ready_list = self.poll.poll(0)
            
            for obj, event in ready_list:
                if event & uselect.POLLIN:
                    if isinstance(obj, int): fd = obj
                    else: fd = obj.fileno()
                        
                    if fd not in self.files: continue
                        
                    f, path = self.files[fd]
                    raw = f.read(24)
                    if not raw or len(raw) < 24: continue
                        
                    sec, usec, type, code, value = ustruct.unpack('llHHi', raw)
                    
                    if type == 1: # EV_KEY
                        # Value: 0=up, 1=down, 2=repeat
                        
                        # Handle Shift
                        if code in [42, 54]: # KEY_LEFTSHIFT, KEY_RIGHTSHIFT
                            self.shift_pressed = (value != 0)
                            continue

                        if value == 1 or value == 2: # Pressed or Repeat
                            mapped_key = 0
                            
                            if code in KEY_MAP:
                                mapped_key = KEY_MAP[code]
                            elif self.shift_pressed and code in SCAN_TO_ASCII_SHIFT:
                                mapped_key = ord(SCAN_TO_ASCII_SHIFT[code])
                            elif code in SCAN_TO_ASCII:
                                mapped_key = ord(SCAN_TO_ASCII[code])
                            
                            if mapped_key != 0:
                                self.last_key = mapped_key
                                self.state = lv.INDEV_STATE.PRESSED
                                # Play click sound
                                import sound
                                sound.beep(10, 800)
                            elif value == 1: # Unmapped key pressed
                                # Still need to report state if we want to support long-press logic elsewhere
                                # but usually we just ignore it.
                                pass

                        elif value == 0: # Released
                            # Release state regardless of key mapping
                            self.state = lv.INDEV_STATE.RELEASED
                                
        except Exception as e:
            print(f"Input error: {e}")
                        
        data.key = self.last_key
        data.state = self.state
        data.continue_reading = False

driver = None

def init():
    """Initialize the global input driver instance.

    Returns:
        InputDriver instance
    """
    global driver
    driver = InputDriver()
    return driver
