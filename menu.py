import lvgl as lv
import badge_mode_app
import about_app
import random
import app_loader
import statusbar

# Load Assets
ti_dsc = None
beagle_dsc = None

try:
    with open('ti_logo.bin', 'rb') as f:
        ti_data = f.read()
    ti_dsc = lv.image_dsc_t()
    ti_dsc.header.magic = lv.IMAGE_HEADER_MAGIC
    ti_dsc.header.cf = lv.COLOR_FORMAT.L8
    ti_dsc.header.w = 128
    ti_dsc.header.h = 128
    ti_dsc.data_size = len(ti_data)
    ti_dsc.data = ti_data
except Exception as e:
    print(f"Failed to load TI Logo: {e}")
    ti_dsc = None

try:
    with open('beagle_logo.bin', 'rb') as f:
        beagle_data = f.read()
    beagle_dsc = lv.image_dsc_t()
    beagle_dsc.header.magic = lv.IMAGE_HEADER_MAGIC
    beagle_dsc.header.cf = lv.COLOR_FORMAT.L8
    beagle_dsc.header.w = 128
    beagle_dsc.header.h = 128
    beagle_dsc.data_size = len(beagle_data)
    beagle_dsc.data = beagle_data
except Exception as e:
    print(f"Failed to load Beagle Logo: {e}")
    beagle_dsc = None

# Styles
style_btn_rel = lv.style_t()
style_btn_rel.init()
style_btn_rel.set_radius(0)
style_btn_rel.set_border_width(1)
style_btn_rel.set_border_color(lv.color_black())
style_btn_rel.set_bg_color(lv.color_white())
style_btn_rel.set_text_color(lv.color_black())

style_btn_pr = lv.style_t()
style_btn_pr.init()
style_btn_pr.set_bg_color(lv.color_black())
style_btn_pr.set_text_color(lv.color_white())

style_btn_foc = lv.style_t()
style_btn_foc.init()
style_btn_foc.set_bg_color(lv.color_black())
style_btn_foc.set_text_color(lv.color_white())

import statusbar
import bottombar

class MenuApp:
    def __init__(self):
        self.name = "Menu"
        self.screen = None
        self.menu_list_cont = None
        self.statusbar = statusbar.StatusBar() # Managed by Menu
        self.bottombar = bottombar.BottomBar() # Managed by Menu
        
        # Dynamic Load
        # 1. Load Categories
        raw_cats = [c[0].upper() + c[1:] for c in app_loader.load_categories()]
        
        # 2. Filter "Settings" to move it to end
        main_cats = [c for c in raw_cats if c != "Settings"]
        has_settings = "Settings" in raw_cats
        
        # 3. Construct Final List: ["Badge Mode"] + Apps/Games/Tools + ["Settings"]
        self.categories = ["Badge Mode"] + sorted(main_cats)
        if has_settings:
            self.categories.append("Settings")
            
        self.badge_mode = badge_mode_app.BadgeModeApp()
        # self.about_app = about_app.AboutApp()

        self.state = "ROOT" # ROOT or SUBMENU
        self.selected_category_idx = 0
        self.current_list = []
        self.cached_apps = {} # Cache loaded apps {category: [apps]}
        
    def enter(self, on_exit=None): # on_exit ignored for Main Menu
        if not self.screen:
            self.screen = lv.obj()
        lv.screen_load(self.screen)
        self.statusbar.show()
        self.bottombar.show()
        
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        
        # Ensure Input Group has Menu Buttons
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            if self.menu_list_cont:
                cnt = self.menu_list_cont.get_child_count()
                for i in range(cnt):
                    btn = self.menu_list_cont.get_child(i)
                    input.driver.group.add_obj(btn)
        
        # Main Flex (Row)
        main_flex = lv.obj(self.screen)
        main_flex.set_size(lv.pct(100), lv.pct(100))
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        
        # Ensure Input Group has Menu Buttons
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
        
        # Main Flex (Row)
        main_flex = lv.obj(self.screen)
        main_flex.set_size(lv.pct(100), lv.pct(100))
        main_flex.set_flex_flow(lv.FLEX_FLOW.ROW)
        main_flex.set_style_pad_all(0, 0)
        main_flex.set_style_border_width(0, 0)
        
        # --- Left Panel (40%) ---
        left_panel = lv.obj(main_flex)
        left_panel.set_size(lv.pct(40), lv.pct(100))
        left_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        left_panel.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        left_panel.set_style_border_width(0, 0)
        
        # Title
        title = lv.label(left_panel)
        title.set_text("Beagle\nBadge")
        title.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            title.set_style_text_font(lv.font_montserrat_24, 0)
        except:
            pass
        
        # Logo
        if ti_dsc and beagle_dsc:
            logo = lv.image(left_panel)
            if random.random() > 0.5:
                logo.set_src(ti_dsc)
            else:
                logo.set_src(beagle_dsc)
        else:
             # Fallback
             logo_cont = lv.obj(left_panel)
             logo_cont.set_size(60, 60)
             logo_cont.set_style_radius(30, 0)
             logo_cont.set_style_bg_color(lv.color_black(), 0)
             
             logo_lbl = lv.label(logo_cont)
             logo_lbl.set_text("B")
             logo_lbl.center()
             logo_lbl.set_style_text_color(lv.color_white(), 0)

        ver = lv.label(left_panel)
        ver.set_text("Linux Port\nv0.2")
        ver.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            ver.set_style_text_font(lv.font_montserrat_14, 0)
        except: pass
        
        # Divider
        line = lv.obj(main_flex)
        line.set_size(2, lv.pct(90))
        line.set_style_bg_color(lv.color_black(), 0)
        line.set_style_bg_opa(lv.OPA.COVER, 0)
        
        # --- Right Panel (55%) ---
        right_panel = lv.obj(main_flex)
        right_panel.set_size(lv.pct(55), lv.pct(100))
        right_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        right_panel.set_style_pad_top(25, 0) 
        right_panel.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        right_panel.set_style_border_width(0, 0)
        
        # Menu List Container
        self.menu_list_cont = lv.obj(right_panel)
        self.menu_list_cont.set_width(lv.pct(100))
        self.menu_list_cont.set_height(lv.pct(100))
        self.menu_list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.menu_list_cont.set_style_pad_all(5, 0)
        self.menu_list_cont.set_style_pad_gap(5, 0)
        self.menu_list_cont.set_style_border_width(0, 0)
        
        self.render_menu()

    def render_menu(self):
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            
        self.menu_list_cont.clean()
        
        items = []
        if self.state == "ROOT":
            items = self.categories
        else:
            # Submenu
            cat_title = self.categories[self.selected_category_idx]
            if cat_title in ["Badge Mode", "About"]:
                items = []
            else:
                cat_lower = cat_title.lower()
                if cat_lower not in self.cached_apps:
                    self.cached_apps[cat_lower] = app_loader.load_apps_from_category(cat_lower)
                items = self.cached_apps[cat_lower]
            
        self.current_list = items
        
        # print(f"Rendering {len(items)} items")
        
        first_btn = None
        for item in items:
            name = item.name if hasattr(item, 'name') else item
            
            btn = lv.button(self.menu_list_cont)
            btn.set_width(lv.pct(100))
            btn.set_height(40)
            
            # Apply Styles
            btn.add_style(style_btn_rel, 0)
            btn.add_style(style_btn_pr, lv.STATE.PRESSED)
            btn.add_style(style_btn_foc, lv.STATE.FOCUSED)
            
            label = lv.label(btn)
            label.set_text(name)
            label.center()
            try:
                label.set_style_text_font(lv.font_montserrat_16, 0)
            except:
                pass
            
            # Events
            btn.add_event_cb(lambda e, item=item: self.on_item_click(item), lv.EVENT.CLICKED, None)
            btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            
            if input.driver and input.driver.group:
                input.driver.group.add_obj(btn)
                
            if not first_btn:
                first_btn = btn
                
        # Focus first
        if first_btn:
            lv.group_focus_obj(first_btn)

    def on_item_click(self, item):
        if self.state == "ROOT":
            if item == "Badge Mode":
                self.statusbar.hide()
                self.bottombar.hide()
                self.badge_mode.enter(on_exit=self.enter)
            elif item == "About": # Should be unreachable but good to keep
                self.statusbar.hide()
                self.bottombar.hide()
                self.about_app.enter(on_exit=self.enter)
            elif isinstance(item, str):
                try:
                    self.selected_category_idx = self.categories.index(item)
                    self.state = "SUBMENU"
                    self.render_menu()
                except: pass
        else:
            if hasattr(item, 'enter'):
                self.statusbar.hide()
                self.bottombar.hide()
                item.enter(on_exit=self.enter)
            else:
                print(f"Placeholder for {item}")

    def on_key(self, e):
        key = e.get_key()
        # print(f"Menu Key: {key}")
        
        if key == lv.KEY.LEFT or key == lv.KEY.BACKSPACE or key == 14 or key == lv.KEY.ESC:
            if self.state == "SUBMENU":
                self.state = "ROOT"
                self.render_menu()
                
        elif key == lv.KEY.RIGHT:
            target_blob = e.get_target()
            if target_blob:
                try:
                    # Cast and click
                    obj = lv.obj.__cast__(target_blob)
                    obj.send_event(lv.EVENT.CLICKED, None)
                except Exception as e:
                    print(f"Event Send Error: {e}") 
            else:
                print("No target for RIGHT key")

    def update(self):
        pass
    def exit(self):
        pass
