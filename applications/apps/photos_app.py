"""Photo viewer application.

Displays images from the photos/ directory. Navigate through photos using
arrow keys to view the slideshow.
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import os
import random

class PhotosApp(app.App):
    def __init__(self):
        super().__init__("Photos")
        self.screen = None
        self.img = None
        self.files = []
        self.idx = 0
        self.loading_label = None
        # Target resolution for photos (full screen)
        self.photo_width = 400
        self.photo_height = 300
        # Track cached files for cleanup
        self.cached_files = []
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit

        # Clean up any leftover cached files from previous runs
        try:
            import glob
            old_cache_files = glob.glob("/tmp/badge_photo_*.dither.bin")
            for f in old_cache_files:
                try:
                    os.remove(f)
                except:
                    pass
        except:
            pass  # glob might not be available in MicroPython

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        self.scan_photos()
        
        self.img = lv.image(self.screen)
        self.img.center()
        self.load_image()
        
        lbl = lv.label(self.screen)
        lbl.set_text("< Prev  Next >")
        lbl.set_style_text_color(lv.color_black(), 0)
        lbl.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        
    def scan_photos(self):
        self.files = []
        # Support various formats since we use img2bin
        exts = [".jpg", ".jpeg", ".png", ".bmp", ".bin"]
        try:
            root = "photos"
            # create photos dir if missing logic handle via shell command step, assuming exists
            for entry in os.listdir(root):
                for ext in exts:
                    if entry.lower().endswith(ext):
                        self.files.append(entry)
                        break
            self.files.sort()
        except:
             pass
        # Add internal fallback if empty (using assets directory)
        if not self.files:
            self.files = ['../assets/ti_logo.bin'] 
             
    def load_image(self):
        if not self.files: return

        # Clean up any previous loading/error messages
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.delete()
            self.loading_label = None

        fname = self.files[self.idx]
        src_path = f"photos/{fname}"

        # Check if it needs conversion
        if fname.endswith(".bin"):
             # Direct load
             self.display_raw(src_path)
             return

        # Needs conversion - use /tmp for cache
        # Create a safe filename for /tmp (replace problematic chars)
        safe_fname = fname.replace("/", "_").replace(" ", "_")
        cache_name = f"badge_photo_{safe_fname}.dither.bin"
        cache_path = f"/tmp/{cache_name}"

        # Check if cache exists in /tmp
        try:
            os.stat(cache_path)
            # Exists, load it (and track it for cleanup if not already tracked)
            if cache_path not in self.cached_files:
                self.cached_files.append(cache_path)
            self.display_raw(cache_path)
        except:
            # Not cached, convert!
            self.show_loading(fname)
            lv.task_handler() # Force refresh

            # Check if img2bin exists
            try:
                os.stat("./img2bin")
            except:
                self.show_error("img2bin tool not found!\nRun: gcc -o img2bin tools/img2bin.c -lm")
                return

            # Use 'contain' mode to maintain aspect ratio with white borders if needed
            cmd = f"./img2bin \"{src_path}\" \"{cache_path}\" {self.photo_width} {self.photo_height} contain"
            res = os.system(cmd)

            if res == 0:
                # Track this file for cleanup
                if cache_path not in self.cached_files:
                    self.cached_files.append(cache_path)

                # Clear loading message
                if hasattr(self, 'loading_label') and self.loading_label:
                    self.loading_label.delete()
                    self.loading_label = None
                self.display_raw(cache_path)
            else:
                self.show_error(f"Conversion failed!\n{fname}")

    def show_loading(self, fname):
        # Show loading message on screen
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.delete()

        self.loading_label = lv.label(self.screen)
        self.loading_label.set_text(f"Converting...\n{fname}")
        self.loading_label.center()
        self.loading_label.set_style_text_color(lv.color_black(), 0)
        self.loading_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

    def show_error(self, message):
        # Clear any existing loading label
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.delete()
            self.loading_label = None

        # Show error message
        error_lbl = lv.label(self.screen)
        error_lbl.set_text(message)
        error_lbl.center()
        error_lbl.set_style_text_color(lv.color_black(), 0)
        error_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

    def display_raw(self, path):
        try:
            with open(path, 'rb') as f:
                data = f.read()

            # Determine dimensions based on file size
            # Full screen photos are 400x300 = 120000 bytes
            # Asset logos are 128x128 = 16384 bytes
            if len(data) == self.photo_width * self.photo_height:
                img_w, img_h = self.photo_width, self.photo_height
            elif len(data) == 128 * 128:
                img_w, img_h = 128, 128
            else:
                # Try to infer from data size (assume square if possible)
                try:
                    import math
                    size = len(data)
                    sqrt_size = int(math.sqrt(size))
                    if sqrt_size * sqrt_size == size:
                        img_w, img_h = sqrt_size, sqrt_size
                    else:
                        # Fall back to photo dimensions
                        img_w, img_h = self.photo_width, self.photo_height
                except:
                    # Fall back to photo dimensions if math not available
                    img_w, img_h = self.photo_width, self.photo_height

            dsc = lv.image_dsc_t()
            try:
                dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            except AttributeError:
                dsc.header.magic = 0x19  # Default LV_IMAGE_HEADER_MAGIC value
            try:
                dsc.header.cf = lv.COLOR_FORMAT.L8
            except AttributeError:
                try:
                    dsc.header.cf = lv.COLOR_FORMAT_L8
                except AttributeError:
                    dsc.header.cf = 0x08  # L8 format value
            dsc.header.w = img_w
            dsc.header.h = img_h
            dsc.data_size = len(data)
            dsc.data = data
            self.current_data = data # keep ref

            self.img.set_src(dsc)

            # Force a refresh to ensure the new image is displayed
            lv.refr_now(None)
        except Exception as e:
            import sys
            error_msg = str(e)
            print(f"Load error: {error_msg}")
            try:
                sys.print_exception(e)
            except:
                pass
            
    def on_key(self, e):
        k = e.get_key()
        if k == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb: self.on_exit_cb()
        elif k == lv.KEY.LEFT:
            self.idx = (self.idx - 1) % len(self.files)
            self.load_image()
        elif k == lv.KEY.RIGHT:
            self.idx = (self.idx + 1) % len(self.files)
            self.load_image()
            
    def exit(self):
        # Clean up cached conversions in /tmp
        for cached_file in self.cached_files:
            try:
                os.remove(cached_file)
            except:
                pass  # Silently ignore if file doesn't exist

        self.cached_files = []

        # Clean up screen
        if self.screen:
            self.screen.delete()
            self.screen = None