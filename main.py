import sys
sys.path.append('lib')
sys.path.append('drivers')
sys.path.append('core')

# Third-party imports
import lvgl as lv
import time

# Local imports - utilities
import lv_utils
import config

# Local imports - drivers
import display
import sound
import input
import tty

# Local imports - core
from core import menu

def main():
    """Main entry point for the Badge Launcher."""
    try:
        # Load configuration
        config.load()

        # Initialize LVGL
        lv.init()

        # Initialize hardware drivers
        print("Initializing drivers...")
        display.init()
        sound.init()
        input.init()
        tty.init()

        # Launch main menu
        app_menu = menu.MenuApp()
        app_menu.enter()

        print("Python Badge Launcher running...")

        # Main event loop
        while True:
            lv.task_handler()
            time.sleep(0.005)  # 5ms delay

    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup all drivers
        print("Cleaning up...")
        try:
            tty.cleanup()
        except:
            pass
        try:
            input.cleanup() if hasattr(input, 'cleanup') else None
        except:
            pass
        try:
            sound.cleanup() if hasattr(sound, 'cleanup') else None
        except:
            pass

if __name__ == "__main__":
    main()
