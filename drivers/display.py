"""Display driver initialization for Linux framebuffer.

Sets up LVGL to use /dev/fb0 for rendering on the E-Ink display.
"""

import lvgl as lv

def init():
    """Initialize LVGL display driver with Linux framebuffer.

    Configures LVGL to render to /dev/fb0 and performs initial refresh.
    """
    # Register FB display driver
    disp = lv.linux_fbdev_create()
    if not disp:
        print("FAILED to create linux_fbdev")
        return
        
    lv.linux_fbdev_set_file(disp, "/dev/fb0")
    
    # Force refresh
    lv.refr_now(disp)
    
    print("Display initialized on /dev/fb0")
