import sys
import os

APP_DIR = os.getcwd()

sys.path.append(APP_DIR)
sys.path.append(APP_DIR + '/lib')
sys.path.append(APP_DIR + '/drivers')
sys.path.append(APP_DIR + '/core')
sys.path.append(APP_DIR + '/applications')
sys.path.append(APP_DIR + '/applications/games')
sys.path.append(APP_DIR + '/applications/games/battlesnake')

import lvgl as lv
import time

import config
import display
import input
import sound
import tty

from battlesnake_app import BattlesnakeApp


def debug(msg):
    try:
        with open('/tmp/battlesnake-debug.log', 'a') as handle:
            handle.write(msg + '\n')
    except Exception:
        pass


def main():
    try:
        debug('start')
        config.load()
        debug('config loaded')
        lv.init()
        debug('lv init')
        display.init()
        debug('display init')
        sound.init()
        debug('sound init')
        input.init()
        debug('input init')
        tty.init()
        debug('tty init')

        app = BattlesnakeApp()
        debug('app created')
        app.enter()
        debug('app entered')

        while True:
            lv.task_handler()
            time.sleep(0.005)
    except KeyboardInterrupt:
        debug('keyboard interrupt')
        pass
    except Exception as exc:
        debug('fatal: ' + str(exc))
        print("Fatal error:", exc)
    finally:
        debug('cleanup')
        try:
            tty.cleanup()
        except Exception:
            pass
        try:
            input.cleanup() if hasattr(input, 'cleanup') else None
        except Exception:
            pass
        try:
            sound.cleanup() if hasattr(sound, 'cleanup') else None
        except Exception:
            pass


if __name__ == "__main__":
    debug('__main__')
    main()
