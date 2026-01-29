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

    def log(self, msg):
        try:
            with open('/tmp/xkcd_debug.txt', 'a') as f:
                f.write(f"{time.time()}: {msg}\n")
        except: pass

    def enter(self, on_exit=None):
        try:
            self.on_exit = on_exit
            
            # Reset Log
            try:
                with open('/tmp/xkcd_debug.txt', 'w') as f:
                    f.write("Starting XKCD\n")
            except: pass
            
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
            try:
                self.title_lbl.set_style_text_font(lv.font_montserrat_16, 0)
            except: pass
            
            # Image container
            self.img_cont = lv.obj(self.screen)
            self.img_cont.set_size(400, 220)
            self.img_cont.align(lv.ALIGN.TOP_MID, 0, 18)
            self.img_cont.set_style_border_width(0, 0)
            
            # White background for safety
            self.img_cont.set_style_bg_color(lv.color_white(), 0)
            self.img_cont.set_style_bg_opa(lv.OPA.COVER, 0)
                
            self.img_cont.set_style_radius(0, 0)
            self.img_cont.set_style_pad_all(0, 0)
            # Force scrollable
            self.img_cont.add_flag(lv.obj.FLAG.SCROLLABLE)
            
            # Caption at bottom
            self.caption_lbl = lv.label(self.screen)
            self.caption_lbl.set_width(380)
            self.caption_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            self.caption_lbl.set_style_text_color(lv.color_black(), 0)
            self.caption_lbl.set_long_mode(lv.label.LONG_MODE.WRAP)
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
            
        except Exception as e:
            with open('/tmp/xkcd_crash.txt', 'w') as f:
                import sys
                sys.print_exception(e, f)
            print(f"XKCD Enter Error: {e}")
            if on_exit: on_exit()

    def show_message(self, text):
        self.log(f"Show Message: {text}")
        self.title_lbl.set_text(text)
        if self.img_obj:
            try:
                self.img_obj.delete()
            except: pass
            self.img_obj = None
        self.caption_lbl.set_text("")
        self.img_dsc = None
        self.img_data = None
        import gc
        gc.collect()

    def fetch_comic(self, comic_id=None):
        if self.loading: return
        self.loading = True
        
        url = "https://xkcd.com/info.0.json"
        if comic_id:
            url = f"https://xkcd.com/{comic_id}/info.0.json"
            
        self.log(f"Fetching: {url}")
        res = self.run_command(f"curl -sL {url}")
        
        if not res or not res.strip().startswith("{"):
            self.log(f"Fetch failed or bad JSON: {res[:50] if res else 'None'}")
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
            
            self.log(f"Got Comic #{self.current_id}: {title}, Img: {img_url}")
            
            self.title_lbl.set_text(f"#{self.current_id}: {title}")
            self.caption_lbl.set_text(alt)
            
            if img_url:
                ext = img_url.split(".")[-1]
                path = f"/tmp/xkcd_{self.current_id}.{ext}"
                
                try:
                    os.stat(path)
                    self.log("Using cached image")
                except:
                    self.log("Downloading image...")
                    self.run_command(f"curl -sL {img_url} -o {path}")
                
                self.display_image(path)
            else:
                self.show_message("No Image Found")
                self.loading = False
                
        except Exception as e:
            self.log(f"JSON/Processing Error: {e}")
            self.show_message(f"Parse Error: {e}")
            self.loading = False

    def display_image(self, path):
        try:
            self.log(f"Displaying: {path}")
            if self.img_obj:
                try:
                    self.img_obj.delete()
                except: pass
                self.img_obj = None
            
            self.img_dsc = None
            self.img_data = None
            try:
                import gc
                gc.collect()
                self.log(f"GC Free: {gc.mem_free()}")
            except: pass
            
            lv.refr_now(None)
                
            try:
                try:
                    st = os.stat(path)
                    self.log(f"File Size: {st[6]}")
                    if st[6] == 0: raise Exception("Empty file")
                except Exception as e:
                    raise Exception(f"File check failed: {e}")

                with open(path, 'rb') as f:
                    self.img_data = bytearray(f.read())
                    
                if len(self.img_data) < 10: raise Exception("Data too short")
                
                # Header log
                h1 = hex(self.img_data[0])
                h2 = hex(self.img_data[1])
                self.log(f"Header: {h1} {h2}")
                
                self.img_dsc = lv.image_dsc_t()
                self.img_dsc.header.cf = lv.COLOR_FORMAT.RAW
                self.img_dsc.data = self.img_data
                self.img_dsc.data_size = len(self.img_data)
                
                self.img_obj = lv.image(self.img_cont)
                self.img_obj.set_src(self.img_dsc)
                
                self.retry_count = 0
                lv.timer_create(lambda t: self.check_decode(t), 100, None)
                
            except Exception as e:
                self.log(f"Display Exception: {e}")
                self.show_message(f"Display Error: {e}")
                self.loading = False
        except Exception as e:
             with open('/tmp/xkcd_crash.txt', 'a') as f:
                 import sys
                 sys.print_exception(e, f)
             print(f"Display Image Crash: {e}")
            
    def check_decode(self, timer):
        try:
            if not self.img_obj: 
                timer.delete()
                return
                
            w = self.img_obj.get_width()
            h = self.img_obj.get_height()
            
            if w > 0 and h > 0:
                self.log(f"Decode Success: {w}x{h}")
                timer.delete()
                self.apply_scaling(w, h)
            else:
                self.retry_count += 1
                if self.retry_count % 10 == 0:
                     self.log(f"Waiting decode... {self.retry_count}")
                     
                if self.retry_count > 100: # 10s
                    self.log("Decode Timeout")
                    timer.delete()
                    self.show_message("Decoder Fail (Timeout)")
                    self.loading = False
        except Exception as e:
             timer.delete()
             with open('/tmp/xkcd_crash.txt', 'a') as f:
                 import sys
                 sys.print_exception(e, f)
             print(f"Check Decode Crash: {e}")

    def apply_scaling(self, orig_w, orig_h):
        try:
            self.loading = False
            
            # Scale to fit WIDTH (400)
            scale_w = (400 * 256) // orig_w
            scale = min(scale_w, 256)
            
            # Calculate final dimensions to center
            final_w = (orig_w * scale) // 256
            x_pos = (400 - final_w) // 2
            
            self.log(f"Applied Scale: {scale}, Pos: {x_pos},0")
            self.img_obj.set_scale(scale)
            # Use set_pos instead of align
            self.img_obj.set_pos(x_pos, 0)
            
            # Reset scroll
            self.img_cont.scroll_to(0, 0, 0)
        except Exception as e:
             with open('/tmp/xkcd_crash.txt', 'a') as f:
                 import sys
                 sys.print_exception(e, f)
             print(f"Apply Scaling Crash: {e}")

    def on_key(self, e):
        try:
            key = e.get_key()
            now = time.time()
            
            if key == lv.KEY.ESC:
                self.exit()
            elif key == lv.KEY.DOWN:
                self.log("Key DOWN")
                self.img_cont.scroll_by(0, -40, 1) # 1 = ON
            elif key == lv.KEY.UP:
                self.log("Key UP")
                self.img_cont.scroll_by(0, 40, 1) # 1 = ON
            elif key == lv.KEY.LEFT:
                self.log("Key LEFT")
                if not self.loading and (now - self.last_key_time > 0.5):
                    self.last_key_time = now
                    if self.current_id > 1:
                        self.show_message(f"Loading #{self.current_id - 1}...")
                        lv.refr_now(None)
                        lv.async_call(lambda _: self.fetch_comic(self.current_id - 1), None)
            elif key == lv.KEY.RIGHT:
                self.log("Key RIGHT")
                if not self.loading and (now - self.last_key_time > 0.5):
                    self.last_key_time = now
                    if self.current_id < self.latest_id:
                        self.show_message(f"Loading #{self.current_id + 1}...")
                        lv.refr_now(None)
                        lv.async_call(lambda _: self.fetch_comic(self.current_id + 1), None)
        except Exception as e:
             with open('/tmp/xkcd_crash.txt', 'a') as f:
                 import sys
                 sys.print_exception(e, f)
             print(f"On Key Crash: {e}")

    def exit(self):
        if self.on_exit:
            self.on_exit()
