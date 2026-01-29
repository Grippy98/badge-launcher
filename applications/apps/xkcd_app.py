import app
import lvgl as lv
import os
import json
import input
import time

class XKCDApp(app.App):
    def __init__(self):
        super().__init__("XKCD")
        self.screen = None
        self.current_id = 0
        self.latest_id = 0
        self.title_lbl = None
        self.img_obj = None
        self.caption_lbl = None
        self.loading = False
        self.last_key_time = 0
        self.img_dsc = None
        self.img_data = None
        
    def run_command(self, cmd):
        try:
            tmp_file = "/tmp/xkcd_cmd.out"
            os.system(f"{cmd} > {tmp_file} 2>&1")
            output = ""
            try:
                with open(tmp_file, 'r') as f:
                    output = f.read()
            except: pass
            return output
        except Exception as e:
            print(f"Error running cmd '{cmd}': {e}")
            return None

    def enter(self, on_exit=None):
        self.on_exit = on_exit
        
        try:
            lv.lodepng_init()
            lv.tjpgd_init()
        except: pass

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Title at very top
        self.title_lbl = lv.label(self.screen)
        self.title_lbl.set_width(400)
        self.title_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.title_lbl.set_style_text_color(lv.color_black(), 0)
        self.title_lbl.align(lv.ALIGN.TOP_MID, 0, 2)
        
        # Image container - no visible border
        self.img_cont = lv.obj(self.screen)
        self.img_cont.set_size(400, 220)
        self.img_cont.align(lv.ALIGN.TOP_MID, 0, 18)
        self.img_cont.set_style_border_width(0, 0)
        self.img_cont.set_style_bg_opa(0, 0)
        self.img_cont.set_style_radius(0, 0)
        self.img_cont.set_style_pad_all(0, 0)
        
        # Caption at bottom
        self.caption_lbl = lv.label(self.screen)
        self.caption_lbl.set_width(400)
        self.caption_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.caption_lbl.set_style_text_color(lv.color_black(), 0)
        self.caption_lbl.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        try:
            self.caption_lbl.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass

        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        self.show_message("Fetching latest...")
        lv.refr_now(None)
        lv.async_call(lambda _: self.fetch_comic(), None)

    def show_message(self, text):
        self.title_lbl.set_text(text)
        if self.img_obj:
            try:
                self.img_obj.delete()
            except: pass
            self.img_obj = None
        self.caption_lbl.set_text("")
        # Clear old data
        self.img_dsc = None
        self.img_data = None

    def fetch_comic(self, comic_id=None):
        if self.loading: return
        self.loading = True
        
        url = "https://xkcd.com/info.0.json"
        if comic_id:
            url = f"https://xkcd.com/{comic_id}/info.0.json"
            
        res = self.run_command(f"curl -sL {url}")
        if not res:
            self.show_message("Network Error")
            self.loading = False
            return
            
        try:
            data = json.loads(res)
            self.current_id = data.get("num", 0)
            if not comic_id:
                self.latest_id = self.current_id
                
            title = data.get("title", "Unknown")
            img_url = data.get("img", "")
            alt = data.get("alt", "")
            
            self.title_lbl.set_text(f"#{self.current_id}: {title}")
            self.caption_lbl.set_text(alt)
            
            if img_url:
                ext = img_url.split(".")[-1]
                path = f"/tmp/xkcd_{self.current_id}.{ext}"
                
                # Only download if not cached
                try:
                    os.stat(path)
                except:
                    self.run_command(f"curl -sL {img_url} -o {path}")
                
                self.display_image(path)
            else:
                self.show_message("No Image Found")
                self.loading = False
                
        except Exception as e:
            print(f"JSON Error: {e}")
            self.show_message(f"Parse Error: {e}")
            self.loading = False

    def display_image(self, path):
        # Delete old image first
        if self.img_obj:
            try:
                self.img_obj.delete()
            except: pass
            self.img_obj = None
        
        # Clear old data BEFORE creating new
        self.img_dsc = None
        self.img_data = None
        lv.refr_now(None)  # Force refresh to clear memory
            
        try:
            # Read image data
            with open(path, 'rb') as f:
                self.img_data = bytearray(f.read())
            
            # Create descriptor - DON'T set w/h, let LVGL figure it out
            self.img_dsc = lv.image_dsc_t()
            self.img_dsc.header.cf = lv.COLOR_FORMAT.RAW
            self.img_dsc.data = self.img_data
            self.img_dsc.data_size = len(self.img_data)
            
            # Create image object
            self.img_obj = lv.image(self.img_cont)
            self.img_obj.set_src(self.img_dsc)
            
            # Wait for decode
            lv.timer_create(lambda _: self.apply_scaling(), 500, None)
            
        except Exception as e:
            print(f"Image Display Error: {e}")
            self.show_message(f"Display Error: {e}")
            self.loading = False

    def apply_scaling(self):
        self.loading = False
        if not self.img_obj: return
        
        orig_w = self.img_obj.get_width()
        orig_h = self.img_obj.get_height()
        
        print(f"Image dimensions: {orig_w}x{orig_h}")
        
        if orig_w > 0 and orig_h > 0:
            # Fit inside 400x220
            scale_w = (400 * 256) // orig_w
            scale_h = (220 * 256) // orig_h
            scale = min(scale_w, scale_h, 256)
            
            self.img_obj.set_scale(scale)
            self.img_obj.center()
        else:
            self.show_message("Decoder Fail (0x0)")

    def on_key(self, e):
        key = e.get_key()
        now = time.time()
        
        if key == lv.KEY.ESC:
            self.exit()
        elif key == lv.KEY.LEFT:
            if not self.loading and (now - self.last_key_time > 0.5):
                self.last_key_time = now
                if self.current_id > 1:
                    self.show_message(f"Loading #{self.current_id - 1}...")
                    lv.refr_now(None)
                    lv.async_call(lambda _: self.fetch_comic(self.current_id - 1), None)
        elif key == lv.KEY.RIGHT:
            if not self.loading and (now - self.last_key_time > 0.5):
                self.last_key_time = now
                if self.current_id < self.latest_id:
                    self.show_message(f"Loading #{self.current_id + 1}...")
                    lv.refr_now(None)
                    lv.async_call(lambda _: self.fetch_comic(self.current_id + 1), None)

    def exit(self):
        if self.on_exit:
            self.on_exit()
