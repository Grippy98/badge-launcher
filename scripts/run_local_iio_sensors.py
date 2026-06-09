import os
import sys
import time

APP_DIR = os.getcwd()

sys.path.append(APP_DIR)
sys.path.append(APP_DIR + "/lib")
sys.path.append(APP_DIR + "/drivers")
sys.path.append(APP_DIR + "/core")
sys.path.append(APP_DIR + "/applications")
sys.path.append(APP_DIR + "/applications/demos")

import lvgl as lv

import config
import display
import input
import sound
import tty

from core import menu
from sensor_visualizer_app import SensorVisualizerApp


def main():
    try:
        config.load()
        lv.init()
        display.init()
        sound.init()
        input.init()
        tty.init()

        current_app = {"instance": None}

        def show_menu():
            current_app["instance"] = menu.MenuApp()
            current_app["instance"].enter()

        current_app["instance"] = SensorVisualizerApp()
        current_app["instance"].enter(on_exit=show_menu)

        while True:
            lv.task_handler()
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print("Fatal error:", exc)
    finally:
        try:
            tty.cleanup()
        except Exception:
            pass
        try:
            input.cleanup() if hasattr(input, "cleanup") else None
        except Exception:
            pass
        try:
            sound.cleanup() if hasattr(sound, "cleanup") else None
        except Exception:
            pass


if __name__ == "__main__":
    main()
