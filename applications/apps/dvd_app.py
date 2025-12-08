import lvgl as lv
import app
import time
import random

class DVDApp(app.App):
    def __init__(self):
        super().__init__("DVD Screensaver")
        self.screen = None
        self.img_dvd = None
        
        # Navigation
        self.asset_files = ['dvd.bin', 'sleeping.bin', 'ti_logo.bin', 'beagle_logo.bin']
        self.current_asset_idx = 0
        self.dvd_dsc = None # Current Descriptor
        
        # Physics
        self.x_speed = 2 # Initial speed slower (was 3)
        self.y_speed = 2
        
        self.anim_timer = None

    def load_current_asset(self):
        filename = self.asset_files[self.current_asset_idx]
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            
            # Create new descriptor
            dsc = lv.image_dsc_t()
            dsc.header.magic = lv.IMAGE_HEADER_MAGIC
            dsc.header.cf = lv.COLOR_FORMAT.L8
            dsc.header.w = 128
            dsc.header.h = 128
            dsc.data_size = len(data)
            dsc.data = data # Python keeps reference if dsc kept? 
            # Note: micropython lvgl might need explicit reference to data buffer
            self.dvd_data_ref = data 
            
            self.dvd_dsc = dsc
            
            # Apply to image if exists
            if self.img_dvd:
                self.img_dvd.set_src(self.dvd_dsc)
                
        except Exception as e:
            print(f"Failed loading {filename}: {e}")
            self.dvd_dsc = None

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        
        lv.screen_load(self.screen)
        
        # Initial Load
        self.load_current_asset()
        
        # Image Widget
        self.img_dvd = lv.image(self.screen)
        if self.dvd_dsc:
            self.img_dvd.set_src(self.dvd_dsc)
        else:
            # Fallback text if no assets found ever
            self.img_dvd = lv.label(self.screen)
            self.img_dvd.set_text("?")
            
        self.img_dvd.set_size(128, 128)
        self.colorize()

        # Random Pos
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        w = 128
        h = 128
        self.img_dvd.set_pos(random.randint(0, sw - w), random.randint(0, sh - h))

        # Input
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs() # Isolate input
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        
        self.anim_timer = lv.timer_create(self.animate, 33, None)

    def colorize(self):
        # Random dark colors
        colors = [
            lv.palette_main(lv.PALETTE.RED),
            lv.palette_main(lv.PALETTE.GREEN),
            lv.palette_main(lv.PALETTE.BLUE),
            lv.palette_main(lv.PALETTE.ORANGE),
            lv.palette_main(lv.PALETTE.PURPLE),
            lv.palette_main(lv.PALETTE.TEAL)
        ]
        col = random.choice(colors)
        self.img_dvd.set_style_image_recolor(col, 0)
        self.img_dvd.set_style_image_recolor_opa(lv.OPA.COVER, 0)

    def change_speed(self, delta):
        mag_x = abs(self.x_speed)
        mag_y = abs(self.y_speed)
        
        # Change magnitude, clamp between 1 and 10
        mag_x = max(1, min(10, mag_x + delta))
        mag_y = max(1, min(10, mag_y + delta))
        
        # Apply back with original sign
        self.x_speed = mag_x * (1 if self.x_speed >= 0 else -1)
        self.y_speed = mag_y * (1 if self.y_speed >= 0 else -1)
        print(f"Speed: {mag_x}")

    def change_asset(self, delta):
        self.current_asset_idx = (self.current_asset_idx + delta) % len(self.asset_files)
        self.load_current_asset()
        # Reset color maybe? or keep it.
        self.colorize()

    def animate(self, t):
        if not self.img_dvd:
            return
            
        x = self.img_dvd.get_x()
        y = self.img_dvd.get_y()
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        w, h = 128, 128
        
        new_x = x + self.x_speed
        new_y = y + self.y_speed
        
        bounced = False
        
        if new_x <= 0: 
            self.x_speed = abs(self.x_speed)
            new_x = 0
            bounced = True
        elif new_x + w >= sw:
            self.x_speed = -abs(self.x_speed)
            new_x = sw - w
            bounced = True
            
        if new_y <= 0:
            self.y_speed = abs(self.y_speed)
            new_y = 0
            bounced = True
        elif new_y + h >= sh:
            self.y_speed = -abs(self.y_speed)
            new_y = sh - h
            bounced = True
            
        self.img_dvd.set_pos(int(new_x), int(new_y))
        
        if bounced:
            self.colorize()

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb:
                self.on_exit_cb()
        elif key == lv.KEY.LEFT:
            self.change_asset(-1)
        elif key == lv.KEY.RIGHT:
            self.change_asset(1)
        elif key == lv.KEY.UP:
            self.change_speed(1)
        elif key == lv.KEY.DOWN:
            self.change_speed(-1)

    def exit(self):
        if self.anim_timer:
            self.anim_timer.delete()
            self.anim_timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
