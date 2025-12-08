import lvgl as lv
import app
import os
import random

class PhotosApp(app.App):
    def __init__(self):
        super().__init__("Photos")
        self.screen = None
        self.img = None
        self.files = []
        self.idx = 0
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
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
        exts = [".jpg", ".jpeg", ".png", ".bmp"]
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
        # Add internal fallback if empty
        if not self.files:
            self.files = ['ti_logo.bin'] 
             
    def load_image(self):
        if not self.files: return
        
        fname = self.files[self.idx]
        src_path = f"photos/{fname}"
        
        # Check if it needs conversion
        if fname.endswith(".bin"):
             # Direct load
             self.display_raw(src_path)
             return
             
        # Needs conversion
        cache_name = fname + ".dither.bin"
        cache_path = f"photos/{cache_name}"
        
        # Check if cache exists
        try:
            os.stat(cache_path)
            # Exists, load it
            self.display_raw(cache_path)
        except:
            # Not cached, convert!
            self.show_loading()
            lv.task_handler() # Force refresh
            
            cmd = f"./img2bin \"{src_path}\" \"{cache_path}\""
            res = os.system(cmd)
            
            if res == 0:
                self.display_raw(cache_path)
            else:
                print(f"Conversion failed for {fname}")

    def show_loading(self):
        # We could show a spinner, but blocking call freezes UI anyway
        # Just update label if possible, or hope user waits 1s
        pass
        
    def display_raw(self, path):
        try:
            with open(path, 'rb') as f:
                data = f.read()
            dsc = lv.image_dsc_t()
            dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            dsc.header.cf = lv.COLOR_FORMAT.L8
            dsc.header.w = 128
            dsc.header.h = 128
            dsc.data_size = len(data)
            dsc.data = data
            self.current_data = data # keep ref
            
            self.img.set_src(dsc)
        except Exception as e:
            print(f"Load error: {e}")
            
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
        if self.screen:
            self.screen.delete()
            self.screen = None
