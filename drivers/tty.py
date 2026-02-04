"""TTY configuration for console input/output.

Disables echo and canonical mode, hides cursor for badge UI.
"""

import os
import sys

# Target the current active console
TTY_DEVS = ["/dev/tty0", "/dev/tty1", "/dev/console"]

def init():
    """Configure TTY devices for raw input and hide cursor.

    Disables echo and canonical mode on console devices,
    and hides the text cursor for clean UI display.
    """
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
            pass

def cleanup():
    """Restore TTY devices to normal settings and show cursor."""
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
