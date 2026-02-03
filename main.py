import sys
sys.path.append('lib')
sys.path.append('drivers')

import lvgl as lv
import lv_utils
import display
import sound
import input
import menu
import statusbar
import tty
import time
import config

import os

def main():
    config.load()
    lv.init()
    
    # Init Drivers
    display.init()
    sound.init()
    input.init()
    tty.init()
    
    # App Loop
    # App Loop
    app_menu = menu.MenuApp()
    app_menu.enter()
    
    print("Python Badge Launcher running...")
    
    # Keep script alive and handle tasks manually
    try:
        while True:
            lv.task_handler()
            time.sleep(0.005) # 5ms delay
    finally:
        print("Cleaning up...")
        tty.cleanup()

if __name__ == "__main__":
    main()
