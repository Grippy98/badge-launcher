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
from core import onboarding

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

        # Launch Armbian's first-boot UI when its standard pending marker is
        # present. Otherwise go straight to the normal Badge Launcher menu.
        app_menu = None
        onboarding_app = None

        def launch_menu():
            nonlocal app_menu
            app_menu = menu.MenuApp()
            app_menu.enter()

        if onboarding.OnboardingApp.should_start():
            onboarding_app = onboarding.OnboardingApp(on_complete=launch_menu)
            onboarding_app.enter()
        else:
            launch_menu()

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
