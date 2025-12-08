import os
import sys

import os
import sys

# Target the current active console
TTY_DEVS = ["/dev/tty0", "/dev/tty1", "/dev/console"]

def init():
    for dev in TTY_DEVS:
        try:
            # Disable echo and canonical mode on the console
            # -echo: Disable echo
            # -icanon: Disable canonical mode (line buffering)
            # raw: Pass input through unprocessed (optional, but good for games)
            os.system(f"stty -F {dev} raw -echo")
            
            # Hide cursor
            try:
                with open(dev, 'w') as f:
                    f.write("\033[?25l")
            except:
                pass
                
            print(f"Configured {dev}")
        except Exception as e:
            # print(f"Failed to configure {dev}: {e}")
            pass

def cleanup():
    for dev in TTY_DEVS:
        try:
            # Restore settings (sane puts it back to normal)
            os.system(f"stty -F {dev} sane")
            
            # Show cursor
            try:
                with open(dev, 'w') as f:
                    f.write("\033[?25h")
            except:
                pass
        except Exception as e:
            pass
