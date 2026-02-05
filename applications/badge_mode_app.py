"""Badge Mode application for displaying badge information.

Shows the user's name, info text, and logo. Allows editing badge details
and cycling through logo options (Random, Beagle, TI).
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import random
import config
import time

class BadgeModeApp(app.App):
    def __init__(self):
        super().__init__("Badge Mode")
        self.screen = None
        self.on_exit_cb = None
        self.ti_dsc = self.load_logo("assets/ti_logo.bin")
        self.beagle_dsc = self.load_logo("assets/beagle_logo.bin")
        self.profile_images = []  # List of profile image descriptors
        self.profile_index = 0    # Current profile image index

        self.editing = False
        self.edit_target = "name" # "name", "info", or "qr_link"
        self.ta = None
        self.qr_code = None

        # Load profile images if available
        self.scan_profile_images()
        
    def load_logo(self, path):
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
            return dsc
        except:
            return None

    def scan_profile_images(self):
        """Scan and load ALL profile images from profile_img folder.

        Scans for image files (.jpg, .png, .bmp, .bin) and converts them
        on-the-fly using img2bin if needed, similar to Photos app.
        Loads all images so user can cycle through them with L/R keys.
        """
        import os
        self.profile_images = []

        try:
            # Check if profile_img directory exists
            files = sorted(os.listdir("profile_img"))

            # Support various formats
            exts = [".jpg", ".jpeg", ".png", ".bmp", ".bin"]

            # Find all image files
            profile_files = []
            for fname in files:
                for ext in exts:
                    if fname.lower().endswith(ext):
                        profile_files.append(fname)
                        break

            if not profile_files:
                return  # No profile images found

            # Check if img2bin is available (needed for non-.bin files)
            has_img2bin = False
            try:
                os.stat("./img2bin")
                has_img2bin = True
            except:
                pass

            # Load each image
            for profile_file in profile_files:
                src_path = f"profile_img/{profile_file}"

                # If it's already a .bin file, load it directly
                if profile_file.endswith(".bin"):
                    dsc = self.load_logo(src_path)
                    if dsc:
                        self.profile_images.append(dsc)
                    continue

                # Need to convert - skip if img2bin not available
                if not has_img2bin:
                    continue

                # Create cache path in /tmp
                safe_fname = profile_file.replace("/", "_").replace(" ", "_")
                cache_name = f"badge_profile_{safe_fname}.bin"
                cache_path = f"/tmp/{cache_name}"

                # Check if already cached
                try:
                    os.stat(cache_path)
                    # Cache exists, load it
                    dsc = self.load_logo(cache_path)
                    if dsc:
                        self.profile_images.append(dsc)
                    continue
                except:
                    pass

                # Convert the image
                # Use 'cover' mode to crop to fill the space
                cmd = f"./img2bin \"{src_path}\" \"{cache_path}\" 128 128 cover"
                res = os.system(cmd)

                if res == 0:
                    # Load the converted image
                    dsc = self.load_logo(cache_path)
                    if dsc:
                        self.profile_images.append(dsc)

        except:
            # Directory doesn't exist or other error
            pass

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Add to input group
        import input
        if input.driver and input.driver.group:
            input.driver.group.set_editing(False)
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
        self.render()

    def render(self):
        self.screen.clean()

        if self.editing:
            self.render_editor()
            return

        # Badge View - Main container
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        cont.set_style_border_width(0, 0)
        cont.set_style_pad_all(10, 0)

        # Horizontal container for logo and QR code
        logo_qr_container = lv.obj(cont)
        logo_qr_container.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
        logo_qr_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        logo_qr_container.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        logo_qr_container.set_style_border_width(0, 0)
        logo_qr_container.set_style_bg_opa(0, 0)
        logo_qr_container.set_style_pad_all(5, 0)
        logo_qr_container.set_style_pad_column(15, 0)  # Space between logo and QR code

        # Logo or Profile Image
        logo_img = lv.image(logo_qr_container)

        # Use profile image if available, otherwise use logo selection
        if self.profile_images:
            logo_img.set_src(self.profile_images[self.profile_index])
        else:
            # Determine which logo to show
            show_beagle = False
            if config.badge_logo == 0: # Random
                show_beagle = random.random() > 0.5
            elif config.badge_logo == 1: # Force Beagle
                show_beagle = True
            else: # Force TI
                show_beagle = False

            if show_beagle:
                if self.beagle_dsc: logo_img.set_src(self.beagle_dsc)
            else:
                if self.ti_dsc: logo_img.set_src(self.ti_dsc)

        # QR Code container
        qr_container = lv.obj(logo_qr_container)
        qr_container.set_size(128, 128)  # Match logo size
        qr_container.set_style_bg_color(lv.color_white(), 0)
        qr_container.set_style_border_width(1, 0)
        qr_container.set_style_border_color(lv.color_black(), 0)
        qr_container.set_style_pad_all(5, 0)
        qr_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # Disable scrollbars

        try:
            self.qr_code = lv.qrcode(qr_container)
            self.qr_code.set_size(118)  # Slightly smaller to fit with padding
            self.qr_code.set_dark_color(lv.color_black())
            self.qr_code.set_light_color(lv.color_white())
            self.qr_code.align(lv.ALIGN.CENTER, 0, 0)

            # Update with link
            link = config.badge_qr_link if config.badge_qr_link else "https://beagleboard.org"
            self.qr_code.update(link, len(link))
        except Exception as e:
            # If QR code fails, show small error
            error_label = lv.label(qr_container)
            error_label.set_text("QR\nerror")
            error_label.set_style_text_color(lv.color_black(), 0)
            error_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            error_label.align(lv.ALIGN.CENTER, 0, 0)
            try:
                error_label.set_style_text_font(lv.font_montserrat_10, 0)
            except:
                pass

        # Name
        self.lbl_name = lv.label(cont)
        self.lbl_name.set_text(config.badge_name)
        self.lbl_name.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            self.lbl_name.set_style_text_font(lv.font_montserrat_24, 0)
        except: pass

        # Info
        self.lbl_info = lv.label(cont)
        self.lbl_info.set_text(config.badge_info)
        self.lbl_info.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        # Hint
        hint = lv.label(self.screen)
        if self.profile_images:
            hint_text = "ENTER: Edit | L/R: Profile" if len(self.profile_images) > 1 else "ENTER: Edit"
        else:
            hint_text = "ENTER: Edit | L/R: Logo"
        hint.set_text(hint_text)
        try:
            hint.set_style_text_font(lv.font_montserrat_12, 0)
        except: pass
        hint.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        hint.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)

        # Top hint - logo mode or profile image indicator
        if self.profile_images:
            # Show profile image indicator
            profile_hint = lv.label(self.screen)
            if len(self.profile_images) > 1:
                profile_hint.set_text(f"Profile {self.profile_index + 1}/{len(self.profile_images)}")
            else:
                profile_hint.set_text("Profile Image")
            try:
                profile_hint.set_style_text_font(lv.font_montserrat_14, 0)
            except: pass
            profile_hint.align(lv.ALIGN.TOP_MID, 0, 5)
            profile_hint.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)
        else:
            # Show logo mode
            mode_hint = lv.label(self.screen)
            modes = ["Random", "Force Beagle", "Force TI"]
            mode_hint.set_text(f"Logo: {modes[config.badge_logo]}")
            try:
                mode_hint.set_style_text_font(lv.font_montserrat_14, 0)
            except: pass
            mode_hint.align(lv.ALIGN.TOP_MID, 0, 5)
            mode_hint.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)

    def render_editor(self):
        cont = lv.obj(self.screen)
        cont.set_size(lv.pct(100), lv.pct(100))
        cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        cont.set_style_pad_all(10, 0)

        title = lv.label(cont)
        if self.edit_target == "name":
            title.set_text("Edit Name")
            current_text = config.badge_name
        elif self.edit_target == "info":
            title.set_text("Edit Info")
            current_text = config.badge_info
        else:  # qr_link
            title.set_text("Edit QR Link")
            current_text = config.badge_qr_link

        self.ta = lv.textarea(cont)
        self.ta.set_size(lv.pct(90), 80)
        self.ta.set_text(current_text)
        self.ta.set_one_line(False)
        
        import input
        if input.driver and input.driver.group:
            input.driver.group.add_obj(self.ta)
            lv.group_focus_obj(self.ta)
            input.driver.group.set_editing(True) 
            
        self.ta.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            
        hint = lv.label(cont)
        hint.set_text("ESC: Save & Next | BACKSPACE: Clear")
        try:
            hint.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass

    def on_key(self, e):
        key = e.get_key()
        if not self.editing:
            if key == lv.KEY.ESC:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()
            elif key == lv.KEY.ENTER:
                self.editing = True
                self.edit_target = "name"
                self.render()
            elif key == lv.KEY.LEFT:
                if self.profile_images:
                    # Cycle through profile images
                    self.profile_index = (self.profile_index - 1) % len(self.profile_images)
                    self.render()
                else:
                    # Cycle through logos
                    config.badge_logo = (config.badge_logo - 1) % 3
                    config.save()
                    self.render()
            elif key == lv.KEY.RIGHT:
                if self.profile_images:
                    # Cycle through profile images
                    self.profile_index = (self.profile_index + 1) % len(self.profile_images)
                    self.render()
                else:
                    # Cycle through logos
                    config.badge_logo = (config.badge_logo + 1) % 3
                    config.save()
                    self.render()
        else:
            # Editing mode
            if key == lv.KEY.ESC:
                # Save current
                val = self.ta.get_text()
                # Strip control characters (like ESC key which might get inserted)
                clean_val = "".join([c for c in val if ord(c) >= 32 or c == "\n"])

                if self.edit_target == "name":
                    config.badge_name = clean_val
                    self.edit_target = "info"
                    self.render()
                elif self.edit_target == "info":
                    config.badge_info = clean_val
                    self.edit_target = "qr_link"
                    self.render()
                else:  # qr_link
                    config.badge_qr_link = clean_val
                    config.save()
                    self.editing = False
                    self.render()
                    # Restore focus
                    import input
                    if input.driver and input.driver.group:
                        input.driver.group.set_editing(False)
                        input.driver.group.remove_all_objs()
                        input.driver.group.add_obj(self.screen)
                        lv.group_focus_obj(self.screen)
            elif key == lv.KEY.ENTER:
                # Enter is handled by textarea for newlines automatically
                # unless we override it. We want it to be a newline.
                pass
                
    def exit(self):
        if self.screen:
            self.screen.delete()
            self.screen = None
        self.qr_code = None