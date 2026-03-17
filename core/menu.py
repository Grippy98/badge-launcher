"""Main menu application for Badge Launcher.

Provides a two-panel menu interface with category navigation,
dynamic app loading, and status bars.
"""

import lvgl as lv
import sys
import random
import time
from . import app_loader
from . import statusbar
from . import bottombar
import config

sys.path.append('applications')


def full_refresh():
    """Performs a full black->white sweep to clear E-Ink ghosting."""
    refresh_scr = lv.obj()
    refresh_scr.set_style_bg_opa(lv.OPA.COVER, 0)

    # Fill Black
    refresh_scr.set_style_bg_color(lv.color_black(), 0)
    lv.screen_load(refresh_scr)
    lv.refr_now(None)
    time.sleep(0.3)

    # Fill White
    refresh_scr.set_style_bg_color(lv.color_white(), 0)
    lv.refr_now(None)
    time.sleep(0.3)


class MenuApp:
    """Main menu application with category-based navigation.

    Manages the primary UI, status bars, and app launching.
    """

    def __init__(self):
        self.name = "Menu"
        self.screen = None
        self.menu_list_cont = None

        # Status and bottom bars
        self.statusbar = statusbar.StatusBar()
        self.bottombar = bottombar.BottomBar()

        # Load logo assets
        self.ti_logo = self._load_logo_asset('assets/ti_logo.bin')
        self.beagle_logo = self._load_logo_asset('assets/beagle_logo.bin')

        # Create button styles
        self.style_btn_rel, self.style_btn_pr, self.style_btn_foc = self._create_button_styles()

        # Load Badge Mode app
        self.badge_mode = None
        self._load_badge_mode_app()

        # Initialize cache for loaded apps
        self.cached_apps = {}  # Cache loaded apps {category: [apps]}

        # Build category list - only include categories with apps
        raw_cats = [c[0].upper() + c[1:] for c in app_loader.load_categories()]

        # Filter out empty categories by checking if they have apps
        non_empty_cats = []
        has_settings = False
        for cat in raw_cats:
            cat_lower = cat.lower()
            # Load apps for this category to check if it's empty
            apps = app_loader.load_apps_from_category(cat_lower)
            if apps:  # Only include if it has at least one app
                if cat_lower == "settings":
                    has_settings = True
                else:
                    non_empty_cats.append(cat)
                # Cache the loaded apps
                self.cached_apps[cat_lower] = apps

        # Filter and order: Badge Mode first, Settings last
        main_cats = sorted(non_empty_cats)

        self.categories = ["Badge Mode"] + main_cats
        if has_settings:
            self.categories.append("Settings")

        # Navigation state
        self.state = "ROOT"  # ROOT or SUBMENU
        self.selected_category_idx = 0
        self.current_list = []

    def _load_logo_asset(self, path):
        """Load a logo asset from binary file.

        Args:
            path: Path to .bin logo file

        Returns:
            lv.image_dsc_t or None if loading fails
        """
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
        except Exception as e:
            print(f"Warning: Failed to load logo {path}: {e}")
            return None

    def _create_button_styles(self):
        """Create LVGL styles for menu buttons.

        Returns:
            Tuple of (released, pressed, focused) styles
        """
        # Released state style
        style_rel = lv.style_t()
        style_rel.init()
        style_rel.set_radius(0)
        style_rel.set_border_width(1)
        style_rel.set_border_color(lv.color_black())
        style_rel.set_bg_color(lv.color_white())
        style_rel.set_text_color(lv.color_black())

        # Pressed state style
        style_pr = lv.style_t()
        style_pr.init()
        style_pr.set_bg_color(lv.color_black())
        style_pr.set_text_color(lv.color_white())

        # Focused state style
        style_foc = lv.style_t()
        style_foc.init()
        style_foc.set_bg_color(lv.color_black())
        style_foc.set_text_color(lv.color_white())

        return style_rel, style_pr, style_foc

    def _load_badge_mode_app(self):
        """Dynamically load Badge Mode app from applications/."""
        try:
            import badge_mode_app
            self.badge_mode = badge_mode_app.BadgeModeApp()
        except Exception as e:
            print(f"Warning: Failed to load Badge Mode: {e}")
            self.badge_mode = None

    def enter(self, on_exit=None):
        """Display the main menu.

        Args:
            on_exit: Ignored for main menu (always stays active)
        """
        # Full refresh when returning from an app
        full_refresh()

        # Clear app cache to rescan for newly installed apps
        self.cached_apps = {}

        # Rebuild category list to reflect any new/removed apps
        raw_cats = [c[0].upper() + c[1:] for c in app_loader.load_categories()]

        # Filter out empty categories by checking if they have apps
        non_empty_cats = []
        has_settings = False
        for cat in raw_cats:
            cat_lower = cat.lower()
            # Load apps for this category to check if it's empty
            apps = app_loader.load_apps_from_category(cat_lower)
            if apps:  # Only include if it has at least one app
                if cat_lower == "settings":
                    has_settings = True
                else:
                    non_empty_cats.append(cat)
                # Cache the loaded apps
                self.cached_apps[cat_lower] = apps

        # Filter and order: Badge Mode first, Settings last
        main_cats = sorted(non_empty_cats)

        self.categories = ["Badge Mode"] + main_cats
        if has_settings:
            self.categories.append("Settings")

        if not self.screen:
            self.screen = lv.obj()
        lv.screen_load(self.screen)
        self.statusbar.show()
        self.bottombar.show()

        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)

        # Clear input group
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()

        # Create main layout
        self._create_layout()
        self.render_menu()

    def _create_layout(self):
        """Create the two-panel menu layout."""
        # Main flex container (Row layout)
        main_flex = lv.obj(self.screen)
        main_flex.set_size(lv.pct(100), lv.pct(100))
        main_flex.set_flex_flow(lv.FLEX_FLOW.ROW)
        main_flex.set_style_pad_all(0, 0)
        main_flex.set_style_border_width(0, 0)

        # Left Panel (40%) - Logo and title
        self._create_left_panel(main_flex)

        # Divider
        line = lv.obj(main_flex)
        line.set_size(2, lv.pct(90))
        line.set_style_bg_color(lv.color_black(), 0)
        line.set_style_bg_opa(lv.OPA.COVER, 0)

        # Right Panel (55%) - Menu items
        self._create_right_panel(main_flex)

    def _create_left_panel(self, parent):
        """Create left panel with logo and title.

        Args:
            parent: Parent LVGL object
        """
        left_panel = lv.obj(parent)
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
        if self.ti_logo and self.beagle_logo:
            logo = lv.image(left_panel)
            # Randomly select logo
            if random.random() > 0.5:
                logo.set_src(self.ti_logo)
            else:
                logo.set_src(self.beagle_logo)
        else:
            # Fallback circle logo
            logo_cont = lv.obj(left_panel)
            logo_cont.set_size(60, 60)
            logo_cont.set_style_radius(30, 0)
            logo_cont.set_style_bg_color(lv.color_black(), 0)

            logo_lbl = lv.label(logo_cont)
            logo_lbl.set_text("B")
            logo_lbl.center()
            logo_lbl.set_style_text_color(lv.color_white(), 0)

        # Version info
        ver = lv.label(left_panel)
        ver.set_text(f"Linux Port\nv{config.version}")
        ver.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            ver.set_style_text_font(lv.font_montserrat_14, 0)
        except:
            pass

    def _create_right_panel(self, parent):
        """Create right panel for menu items.

        Args:
            parent: Parent LVGL object
        """
        right_panel = lv.obj(parent)
        right_panel.set_size(lv.pct(55), lv.pct(100))
        right_panel.set_style_pad_all(0, 0)
        right_panel.set_style_border_width(0, 0)

        # Up Arrow (absolute positioning with balanced padding and larger font)
        self.up_arrow = lv.label(right_panel)
        self.up_arrow.set_text(lv.SYMBOL.UP)
        self.up_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.up_arrow.set_style_text_font(lv.font_montserrat_28, 0)
        except:
            try:
                self.up_arrow.set_style_text_font(lv.font_montserrat_24, 0)
            except:
                pass
        self.up_arrow.align(lv.ALIGN.TOP_MID, 0, 32)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Menu list container (slightly larger viewport to reduce scrolling)
        # Explicitly positioned at center with absolute pixel coordinates
        right_panel_width = int(400 * 0.55)  # 55% of 400px screen width
        self.menu_list_cont = lv.obj(right_panel)
        self.menu_list_cont.set_width(int(right_panel_width * 0.9))
        self.menu_list_cont.set_height(185)
        self.menu_list_cont.set_pos(int(right_panel_width * 0.05), 57)  # Fixed Y position
        self.menu_list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.menu_list_cont.set_style_pad_all(5, 0)
        self.menu_list_cont.set_style_pad_gap(5, 0)
        self.menu_list_cont.set_style_border_width(0, 0)
        self.menu_list_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.AUTO)
        self.menu_list_cont.add_flag(lv.obj.FLAG.SCROLLABLE)
        self.menu_list_cont.add_flag(lv.obj.FLAG.SCROLL_ON_FOCUS)

        # Down Arrow (absolute positioning with balanced padding and larger font)
        self.down_arrow = lv.label(right_panel)
        self.down_arrow.set_text(lv.SYMBOL.DOWN)
        self.down_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.down_arrow.set_style_text_font(lv.font_montserrat_28, 0)
        except:
            try:
                self.down_arrow.set_style_text_font(lv.font_montserrat_24, 0)
            except:
                pass
        self.down_arrow.align(lv.ALIGN.BOTTOM_MID, 0, -25)

    def render_menu(self):
        """Render current menu items based on navigation state."""
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()

        self.menu_list_cont.clean()

        # Determine what items to display
        items = []
        if self.state == "ROOT":
            items = self.categories
        else:
            # Submenu - load apps from category
            cat_title = self.categories[self.selected_category_idx]
            if cat_title == "Badge Mode":
                # Badge Mode has no submenu
                items = []
            else:
                cat_lower = cat_title.lower()
                if cat_lower not in self.cached_apps:
                    self.cached_apps[cat_lower] = app_loader.load_apps_from_category(cat_lower)
                items = self.cached_apps[cat_lower]

        self.current_list = items

        # Create menu buttons
        first_btn = None
        for item in items:
            name = item.name if hasattr(item, 'name') else item

            btn = lv.button(self.menu_list_cont)
            btn.set_width(lv.pct(100))
            btn.set_height(40)

            # Apply styles
            btn.add_style(self.style_btn_rel, 0)
            btn.add_style(self.style_btn_pr, lv.STATE.PRESSED)
            btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)

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
            btn.add_event_cb(self.on_focus, lv.EVENT.FOCUSED, None)

            if input.driver and input.driver.group:
                input.driver.group.add_obj(btn)

            if not first_btn:
                first_btn = btn

        # Focus first button and update arrows
        if first_btn:
            lv.group_focus_obj(first_btn)
            self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            if len(items) > 1:
                self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            lv.refr_now(None)
        else:
            # No items in this category - show message and allow navigation back
            self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)

            # Create empty state message
            empty_label = lv.label(self.menu_list_cont)
            empty_label.set_text("No apps in this category.\nPress ESC to go back.")
            empty_label.set_style_text_color(lv.color_black(), 0)
            try:
                empty_label.set_style_text_font(lv.font_montserrat_14, 0)
            except:
                pass
            empty_label.set_width(lv.pct(90))
            empty_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            empty_label.align(lv.ALIGN.CENTER, 0, 0)

            # Make the screen itself receive keyboard events for navigation
            self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            if input.driver and input.driver.group:
                # Add screen to group so it can receive ESC key
                self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
                input.driver.group.add_obj(self.screen)
                lv.group_focus_obj(self.screen)

            lv.refr_now(None)

    def on_focus(self, e):
        """Handle button focus event to update arrow indicators.

        Args:
            e: LVGL event object
        """
        try:
            target = e.get_target()
            obj = lv.obj.__cast__(target)
            if not obj: return

            idx = obj.get_index()
            total_items = len(self.current_list)

            if idx == 0:
                self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.up_arrow.remove_flag(lv.obj.FLAG.HIDDEN)

            if idx == total_items - 1:
                self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)

            lv.refr_now(None)
        except Exception as ex:
            pass

    def on_item_click(self, item):
        """Handle menu item click.

        Args:
            item: Either a string (category name) or App instance
        """
        if self.state == "ROOT":
            # Root menu - handle categories
            if item == "Badge Mode":
                if self.badge_mode:
                    self.statusbar.hide()
                    self.bottombar.hide()
                    self.badge_mode.enter(on_exit=self.enter)
            elif isinstance(item, str):
                # Navigate to category submenu
                try:
                    self.selected_category_idx = self.categories.index(item)
                    self.state = "SUBMENU"
                    lv.async_call(lambda _: self.render_menu(), None)
                except:
                    pass
        else:
            # Submenu - launch app
            if hasattr(item, 'enter'):
                full_refresh()
                self.statusbar.hide()
                self.bottombar.hide()
                item.enter(on_exit=self.enter)

    def on_key(self, e):
        """Handle keyboard input.

        Args:
            e: LVGL event object
        """
        key = e.get_key()

        # Back/Escape - return to root menu
        if key == lv.KEY.LEFT or key == lv.KEY.BACKSPACE or key == 14 or key == lv.KEY.ESC:
            if self.state == "SUBMENU":
                self.state = "ROOT"
                lv.async_call(lambda _: self.render_menu(), None)

        # Right/Enter - activate button
        elif key == lv.KEY.RIGHT:
            target_blob = e.get_target()
            if target_blob:
                try:
                    obj = lv.obj.__cast__(target_blob)
                    obj.send_event(lv.EVENT.CLICKED, None)
                except:
                    pass

        # UP/DOWN - manual focus navigation (SDL and Physical buttons)
        elif key == lv.KEY.UP or key == lv.KEY.PREV:
            import input
            if input.driver and input.driver.group:
                input.driver.group.focus_prev()
                lv.refr_now(None)

        elif key == lv.KEY.DOWN or key == lv.KEY.NEXT:
            import input
            if input.driver and input.driver.group:
                input.driver.group.focus_next()
                lv.refr_now(None)
