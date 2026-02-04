import sys
import os
import app_loader

# Match main.py paths
sys.path.append('lib')
sys.path.append('drivers')

print("--- Debugging Category: tools ---")
apps = app_loader.load_apps_from_category("tools")
print(f"Loaded {len(apps)} apps from tools")

print("\n--- Debugging Category: apps ---")
apps = app_loader.load_apps_from_category("apps")
print(f"Loaded {len(apps)} apps from apps")

print("\n--- Testing Tux Driver Import ---")
try:
    from libtuxdriver.include.tux_driver_mp import TuxDrv
    print("TuxDrv import OK")
except Exception as e:
    print(f"TuxDrv import FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing libtuxdriver.so loading ---")
try:
    import ffi
    lib = ffi.open("/opt/badge_launcher/libtuxdriver/unix/libtuxdriver.so")
    print("libtuxdriver.so open OK")
except Exception as e:
    print(f"libtuxdriver.so open FAILED: {e}")
