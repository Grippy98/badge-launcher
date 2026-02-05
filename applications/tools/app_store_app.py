"""App Store - Download and manage community apps.

Browse and install apps from the badge app store repository.
Uses git submodules for proper version control.
"""

import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import lvgl as lv
import os
import json
import time

class AppStoreApp(app.App):
    def __init__(self):
        super().__init__("App Store")
        self.screen = None
        self.list_cont = None
        self.buttons = []
        self.apps = []
        self.selected_idx = 0
        self.visible_start = 0  # First visible item index
        self.visible_count = 5  # Show 5 items at a time
        self.status_label = None
        self.loading = False
        self.log_file = "/tmp/appstore_debug.log"
        self.star_counts = {}  # Cache for GitHub star counts
        self.last_updated = {}  # Cache for last commit timestamps
        self.sort_mode = 0  # 0=alphabetical, 1=stars, 2=recent
        self.sort_modes = ["A-Z", "Stars", "Recent"]

        # Category filtering
        self.current_view = "menu"  # "menu" or "list"
        self.selected_category = None  # None = All, or "demo", "tools", "media", "games"
        self.categories = [
            {"id": None, "name": "All Apps"},
            {"id": "demo", "name": "Demos"},
            {"id": "tools", "name": "Tools"},
            {"id": "media", "name": "Media"},
            {"id": "games", "name": "Games"}
        ]
        self.category_selected_idx = 0

        # UI elements for right panel
        self.desc_panel = None
        self.desc_name = None
        self.desc_author = None
        self.desc_category = None
        self.desc_version = None
        self.desc_text = None
        self.desc_status = None

        # Arrows
        self.up_arrow = None
        self.down_arrow = None

        # Overlay menu
        self.menu_overlay = None
        self.menu_container = None
        self.menu_buttons = []
        self.menu_actions = []
        self.menu_selected = 0
        self.menu_visible = False

        # QR code overlay
        self.qr_overlay = None
        self.qr_bg_overlay = None

        # Category menu
        self.category_container = None
        self.category_buttons = []

        # App store configuration
        self.store_repo = "https://github.com/Grippy98/badge-app-store.git"
        self.store_path = "/tmp/badge-app-store"

        # Styles
        self.style_btn_rel = lv.style_t()
        self.style_btn_rel.init()
        self.style_btn_rel.set_radius(0)
        self.style_btn_rel.set_border_width(1)
        self.style_btn_rel.set_border_color(lv.color_black())
        self.style_btn_rel.set_bg_color(lv.color_white())
        self.style_btn_rel.set_text_color(lv.color_black())

        self.style_btn_foc = lv.style_t()
        self.style_btn_foc.init()
        self.style_btn_foc.set_bg_color(lv.color_black())
        self.style_btn_foc.set_text_color(lv.color_white())

    def log(self, msg):
        """Log debug messages to file."""
        try:
            with open(self.log_file, 'a') as f:
                f.write(f"{time.time()}: {msg}\n")
        except:
            pass

    def run_command(self, cmd):
        """Execute shell command and return output."""
        try:
            tmp_file = "/tmp/appstore_cmd.out"
            result = os.system(f"{cmd} > {tmp_file} 2>&1")
            output = ""
            try:
                with open(tmp_file, 'r') as f:
                    output = f.read()
            except:
                pass
            return (result == 0, output)
        except Exception as e:
            print(f"Command error: {e}")
            return (False, str(e))

    def enter(self, on_exit=None):
        self.on_exit = on_exit

        # Clear old logs
        try:
            with open(self.log_file, 'w') as f:
                f.write("=== App Store Starting ===\n")
        except:
            pass

        self.log(f"Store URL: {self.store_repo}")

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        # Title
        title = lv.label(self.screen)
        title.set_text("App Store")
        title.set_style_text_color(lv.color_black(), 0)
        title.align(lv.ALIGN.TOP_MID, 0, 10)
        try:
            title.set_style_text_font(lv.font_montserrat_18, 0)
        except:
            pass

        # Sort mode indicator
        self.sort_label = lv.label(self.screen)
        self.sort_label.set_text(f"Sort: {self.sort_modes[self.sort_mode]}")
        self.sort_label.set_style_text_color(lv.color_black(), 0)
        self.sort_label.set_pos(10, 10)
        try:
            self.sort_label.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass

        # Status label (for loading/errors - full screen)
        self.status_label = lv.label(self.screen)
        self.status_label.set_width(380)
        self.status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.status_label.set_style_text_color(lv.color_black(), 0)
        self.status_label.align(lv.ALIGN.CENTER, 0, 0)
        try:
            self.status_label.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass

        # Up Arrow (left side, above list)
        self.up_arrow = lv.label(self.screen)
        self.up_arrow.set_text("^")
        self.up_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.up_arrow.set_style_text_font(lv.font_montserrat_20, 0)
        except:
            pass
        self.up_arrow.set_pos(10, 48)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Left panel - App list container
        self.list_cont = lv.obj(self.screen)
        self.list_cont.set_size(180, 170)  # 5 apps * 34px = 170px
        self.list_cont.set_pos(10, 70)
        self.list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list_cont.set_style_bg_opa(0, 0)
        self.list_cont.set_style_border_width(0, 0)
        self.list_cont.set_style_pad_all(0, 0)
        self.list_cont.set_style_pad_gap(2, 0)
        self.list_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.list_cont.add_flag(lv.obj.FLAG.HIDDEN)

        # Down Arrow (left side, below list)
        self.down_arrow = lv.label(self.screen)
        self.down_arrow.set_text("v")
        self.down_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.down_arrow.set_style_text_font(lv.font_montserrat_20, 0)
        except:
            pass
        self.down_arrow.set_pos(10, 245)
        self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Vertical divider line
        divider = lv.obj(self.screen)
        divider.set_size(2, 210)
        divider.set_pos(199, 50)
        divider.set_style_bg_color(lv.color_black(), 0)
        divider.set_style_border_width(0, 0)
        divider.add_flag(lv.obj.FLAG.HIDDEN)
        self.divider = divider

        # Right panel - Description area
        self.desc_panel = lv.obj(self.screen)
        self.desc_panel.set_size(190, 210)
        self.desc_panel.set_pos(205, 50)
        self.desc_panel.set_style_bg_opa(0, 0)
        self.desc_panel.set_style_border_width(0, 0)
        self.desc_panel.set_style_pad_all(5, 0)
        self.desc_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.desc_panel.add_flag(lv.obj.FLAG.HIDDEN)

        # App name
        self.desc_name = lv.label(self.desc_panel)
        self.desc_name.set_width(180)
        self.desc_name.set_text("")
        self.desc_name.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_name.set_long_mode(lv.LABEL_LONG.WRAP)
            self.desc_name.set_style_text_font(lv.font_montserrat_16, 0)
        except:
            pass
        self.desc_name.align(lv.ALIGN.TOP_LEFT, 5, 5)

        # Version and Category
        self.desc_version = lv.label(self.desc_panel)
        self.desc_version.set_width(180)
        self.desc_version.set_text("")
        self.desc_version.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_version.set_long_mode(lv.LABEL_LONG.WRAP)
            self.desc_version.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        self.desc_version.align(lv.ALIGN.TOP_LEFT, 5, 30)

        # Author
        self.desc_author = lv.label(self.desc_panel)
        self.desc_author.set_width(180)
        self.desc_author.set_text("")
        self.desc_author.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_author.set_long_mode(lv.LABEL_LONG.WRAP)
            self.desc_author.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        self.desc_author.align(lv.ALIGN.TOP_LEFT, 5, 50)

        # Description
        self.desc_text = lv.label(self.desc_panel)
        self.desc_text.set_width(180)
        self.desc_text.set_text("")
        self.desc_text.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_text.set_long_mode(lv.LABEL_LONG.WRAP)
            self.desc_text.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        self.desc_text.align(lv.ALIGN.TOP_LEFT, 5, 70)

        # Install status
        self.desc_status = lv.label(self.desc_panel)
        self.desc_status.set_width(180)
        self.desc_status.set_text("")
        self.desc_status.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_status.set_long_mode(lv.LABEL_LONG.WRAP)
            self.desc_status.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        self.desc_status.align(lv.ALIGN.BOTTOM_LEFT, 5, -5)

        # Bottom instructions
        info_label = lv.label(self.screen)
        info_label.set_text("UP/DN: Select | L/R: Sort | ENTER: Menu | ESC: Exit")
        info_label.set_style_text_color(lv.color_black(), 0)
        info_label.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        try:
            info_label.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass
        info_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.info_label = info_label

        # Setup input
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        # Start loading apps
        self.status_label.set_text("Fetching app list...")
        lv.refr_now(None)
        lv.async_call(lambda _: self.fetch_manifest(), None)

    def show_category_menu(self):
        """Show the category selection menu."""
        self.current_view = "menu"

        # Hide list UI elements
        self.list_cont.add_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.add_flag(lv.obj.FLAG.HIDDEN)
        self.divider.add_flag(lv.obj.FLAG.HIDDEN)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.sort_label.add_flag(lv.obj.FLAG.HIDDEN)

        # Clear any cached installed status checks by re-rendering when we come back
        # (This ensures fresh filesystem checks when returning from install/delete)

        # Show category buttons
        if self.category_container is None:
            self.category_container = lv.obj(self.screen)
            self.category_container.set_size(160, 215)
            self.category_container.set_pos(120, 35)
            self.category_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
            self.category_container.set_style_bg_opa(0, 0)
            self.category_container.set_style_border_width(0, 0)
            self.category_container.set_style_pad_all(5, 0)
            self.category_container.set_style_pad_gap(5, 0)
            self.category_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

            self.category_buttons = []
            for i, cat in enumerate(self.categories):
                btn = lv.button(self.category_container)
                btn.set_size(140, 36)
                btn.add_style(self.style_btn_rel, 0)

                if i == self.category_selected_idx:
                    btn.add_style(self.style_btn_foc, 0)

                lbl = lv.label(btn)
                lbl.set_text(cat["name"])
                lbl.center()

                self.category_buttons.append(btn)
        else:
            self.category_container.remove_flag(lv.obj.FLAG.HIDDEN)
            # Update selection highlight
            for i, btn in enumerate(self.category_buttons):
                try:
                    btn.remove_style(self.style_btn_foc, 0)
                except:
                    pass
                if i == self.category_selected_idx:
                    btn.add_style(self.style_btn_foc, 0)

        # Update instructions
        self.info_label.set_text("UP/DN: Select | ENTER: View | ESC: Exit")
        self.info_label.remove_flag(lv.obj.FLAG.HIDDEN)
        lv.refr_now(None)

    def get_filtered_apps(self):
        """Get apps filtered by current category."""
        if self.selected_category is None:
            return self.apps  # All apps
        return [app for app in self.apps if app.get("category") == self.selected_category]

    def show_app_list(self):
        """Show the app list for the selected category."""
        self.current_view = "list"

        # Hide category menu
        if self.category_container is not None:
            self.category_container.add_flag(lv.obj.FLAG.HIDDEN)

        # Show list UI elements
        self.list_cont.remove_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.remove_flag(lv.obj.FLAG.HIDDEN)
        self.divider.remove_flag(lv.obj.FLAG.HIDDEN)
        self.sort_label.remove_flag(lv.obj.FLAG.HIDDEN)

        # Reset selection
        self.selected_idx = 0
        self.visible_start = 0

        # Update instructions
        self.info_label.set_text("UP/DN: Select | L/R: Sort | ENTER: Menu | ESC: Back")

        # Check if category has apps
        filtered_apps = self.get_filtered_apps()
        if not filtered_apps:
            # Clear description panel if no apps
            self.desc_name.set_text("")
            self.desc_version.set_text("")
            self.desc_author.set_text("")
            self.desc_text.set_text("No apps in this category")
            self.desc_status.set_text("")

        # Force a fresh render to update installed status
        self.render_list()
        if filtered_apps:
            self.update_description()
        lv.refr_now(None)

    def fetch_manifest(self):
        """Fetch the app list by reading metadata from store repository."""
        if self.loading:
            self.log("Already loading, skipping")
            return
        self.loading = True

        self.log(f"Fetching app store from: {self.store_repo}")

        # Ensure store repo is cloned/updated
        try:
            os.stat(self.store_path)
            # Update existing
            self.status_label.set_text("Updating app store...")
            lv.refr_now(None)
            self.log("Updating existing store repo")
            success, output = self.run_command(f"cd {self.store_path} && git pull")
            if not success:
                self.log(f"Git pull failed: {output}")
                self.status_label.set_text("Failed to update store.\nUsing cached version.")
                # Continue with cached version
        except:
            # Clone fresh
            self.status_label.set_text("Downloading app store...")
            lv.refr_now(None)
            self.log("Cloning fresh store repo")
            success, output = self.run_command(f"git clone {self.store_repo} {self.store_path}")
            if not success:
                self.log(f"Git clone failed: {output}")
                self.status_label.set_text("Failed to download store.\nCheck network connection.")
                self.loading = False
                return

        # Read metadata from each app folder
        self.status_label.set_text("Loading apps...")
        lv.refr_now(None)

        try:
            self.log("Reading app metadata from folders")
            self.apps = []
            apps_dir = f"{self.store_path}/apps"

            # Check if apps directory exists
            try:
                os.stat(apps_dir)
            except:
                self.log(f"Apps directory not found: {apps_dir}")
                self.status_label.set_text("No apps directory in store.")
                self.loading = False
                return

            # Iterate through each subdirectory in apps/
            for entry in os.listdir(apps_dir):
                app_path = f"{apps_dir}/{entry}"
                metadata_path = f"{app_path}/metadata.json"

                # Check if this is a directory with metadata.json
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        self.apps.append(metadata)
                        self.log(f"Loaded app: {metadata.get('name', entry)}")
                except Exception as e:
                    self.log(f"Skipping {entry}: {e}")
                    continue

            self.log(f"Found {len(self.apps)} apps")

            if not self.apps:
                self.status_label.set_text("No apps available in store.")
                self.loading = False
                return

            # Hide status, show category menu
            self.log("Showing category menu")
            self.status_label.add_flag(lv.obj.FLAG.HIDDEN)

            # Sort apps initially
            self.sort_apps()

            # Show category selection menu
            self.show_category_menu()
            self.loading = False

        except Exception as e:
            self.log(f"Exception: {e}")
            self.status_label.set_text(f"Error: {str(e)}\nSee /tmp/appstore_debug.log")
            self.loading = False

    def render_list(self):
        """Render the visible portion of the app list."""
        self.log(f"render_list: selected={self.selected_idx}, visible_start={self.visible_start}")

        # Clear existing buttons
        for btn in self.buttons:
            try:
                btn.delete()
            except:
                pass  # Already deleted
        self.buttons = []

        # Get filtered apps for current category
        filtered_apps = self.get_filtered_apps()

        # Calculate visible range
        end_idx = min(self.visible_start + self.visible_count, len(filtered_apps))

        # Show/hide arrows
        if self.visible_start > 0:
            self.up_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        if end_idx < len(filtered_apps):
            self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Create buttons for visible items
        for i in range(self.visible_start, end_idx):
            app_info = filtered_apps[i]
            name = app_info.get("name", "Unknown")

            # Check if installed
            installed = self.is_installed(app_info.get("id"))
            status_icon = "[*] " if installed else ""

            text = f"{status_icon}{name}"

            btn = lv.button(self.list_cont)
            btn.set_size(180, 32)
            btn.add_style(self.style_btn_rel, 0)

            # Highlight selected
            if i == self.selected_idx:
                btn.add_style(self.style_btn_foc, 0)

            lbl = lv.label(btn)
            lbl.set_text(text)
            lbl.center()

            self.buttons.append(btn)

        self.log(f"Rendered {len(self.buttons)} buttons")
        lv.refr_now(None)

    def update_description(self):
        """Update the right panel with selected app info."""
        filtered_apps = self.get_filtered_apps()
        if not filtered_apps or self.selected_idx >= len(filtered_apps):
            return

        app_info = filtered_apps[self.selected_idx]

        name = app_info.get("name", "Unknown")
        available_version = app_info.get("version", "?.?")
        author = app_info.get("author", "Unknown")
        category = app_info.get("category", "other")
        desc = app_info.get("description", "No description available.")
        app_id = app_info.get("id", "")
        repo_url = app_info.get("repo", "")

        self.desc_name.set_text(name)
        self.desc_text.set_text(desc)

        # Fetch star count in background
        star_count = self.fetch_star_count(app_id, repo_url)
        if star_count is not None:
            star_text = "star" if star_count == 1 else "stars"
            self.desc_author.set_text(f"by {author} • {star_count} {star_text}")
        else:
            self.desc_author.set_text(f"by {author}")

        # Check if installed and compare versions
        if self.is_installed(app_id):
            installed_version = self.get_installed_version(app_id)

            # Show version comparison only if versions differ and are known
            if installed_version != "unknown" and installed_version != available_version:
                self.desc_version.set_text(f"v{installed_version} -> v{available_version} • {category}")
                self.desc_status.set_text("[UPDATE AVAILABLE]\nPress ENTER for options")
            else:
                # Same version or unknown - just show available version
                self.desc_version.set_text(f"v{available_version} • {category}")
                self.desc_status.set_text("[INSTALLED]\nPress ENTER for options")
        else:
            self.desc_version.set_text(f"v{available_version} • {category}")
            self.desc_status.set_text("Press ENTER to install")

        self.log(f"Updated description for: {name}")

    def get_category_dir(self, category):
        """Map category ID to installation directory name."""
        # Map category IDs to their corresponding directory names
        category_map = {
            "demo": "demos",
            "tools": "tools",
            "media": "apps",  # Media apps go to apps/
            "games": "games",
            "apps": "apps"
        }
        return category_map.get(category, "apps")

    def find_installed_app(self, app_id):
        """Find where an app is installed, if anywhere.

        Returns:
            Tuple of (category_dir, app_path) if found, else (None, None)
        """
        # Check all possible category directories
        for category_dir in ["apps", "demos", "games", "tools"]:
            # Check for directory-based installation
            dir_path = f"applications/{category_dir}/{app_id}"
            try:
                os.stat(dir_path)
                return (category_dir, dir_path)
            except:
                pass

            # Check for file-based installation (old-style apps)
            file_path = f"applications/{category_dir}/{app_id}_app.py"
            try:
                os.stat(file_path)
                return (category_dir, file_path)
            except:
                pass

        return (None, None)

    def is_installed(self, app_id):
        """Check if an app is already installed (directory or file-based)."""
        category_dir, app_path = self.find_installed_app(app_id)
        return app_path is not None

    def get_installed_version(self, app_id):
        """Get the version of an installed app from its metadata."""
        category_dir, app_path = self.find_installed_app(app_id)
        if not app_path:
            return "unknown"

        # Try to read metadata.json from the app directory
        metadata_path = f"{app_path}/metadata.json"
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                return metadata.get("version", "unknown")
        except:
            return "unknown"

    def parse_github_repo(self, repo_url):
        """Extract owner/repo from GitHub URL."""
        if not repo_url:
            return None

        # Handle various GitHub URL formats
        # https://github.com/owner/repo.git
        # https://github.com/owner/repo
        # git@github.com:owner/repo.git

        try:
            if "github.com/" in repo_url:
                parts = repo_url.split("github.com/")[1]
                parts = parts.replace(".git", "")
                parts = parts.strip("/")
                return parts
            elif "github.com:" in repo_url:
                parts = repo_url.split("github.com:")[1]
                parts = parts.replace(".git", "")
                parts = parts.strip("/")
                return parts
        except:
            pass

        return None

    def fetch_star_count(self, app_id, repo_url):
        """Fetch GitHub star count and last updated timestamp for a repository."""
        if app_id in self.star_counts:
            return self.star_counts[app_id]

        repo_path = self.parse_github_repo(repo_url)
        if not repo_path:
            self.star_counts[app_id] = None
            self.last_updated[app_id] = None
            return None

        try:
            # Fetch from GitHub API
            api_url = f"https://api.github.com/repos/{repo_path}"
            success, output = self.run_command(f"curl -s {api_url}")

            if success and output:
                data = json.loads(output)
                stars = data.get("stargazers_count", 0)
                pushed_at = data.get("pushed_at", "")

                self.star_counts[app_id] = stars
                self.last_updated[app_id] = pushed_at
                self.log(f"Fetched {stars} stars and last push {pushed_at} for {repo_path}")
                return stars
        except Exception as e:
            self.log(f"Failed to fetch repo info for {repo_path}: {e}")

        self.star_counts[app_id] = None
        self.last_updated[app_id] = None
        return None

    def sort_apps(self):
        """Sort the apps list based on current sort mode."""
        if not self.apps:
            return

        if self.sort_mode == 0:  # Alphabetical
            self.apps.sort(key=lambda x: x.get("name", "").lower())
        elif self.sort_mode == 1:  # Stars
            # First fetch all star counts
            for app in self.apps:
                app_id = app.get("id")
                repo_url = app.get("repo", "")
                self.fetch_star_count(app_id, repo_url)

            # Sort by stars (highest first), with None/0 at the end
            def star_sort_key(app):
                app_id = app.get("id")
                stars = self.star_counts.get(app_id)
                if stars is None:
                    return -1
                return stars

            self.apps.sort(key=star_sort_key, reverse=True)
        elif self.sort_mode == 2:  # Recent (by last commit)
            # First fetch all repo info (includes last push timestamp)
            for app in self.apps:
                app_id = app.get("id")
                repo_url = app.get("repo", "")
                self.fetch_star_count(app_id, repo_url)

            # Sort by last updated timestamp (most recent first)
            def recent_sort_key(app):
                app_id = app.get("id")
                timestamp = self.last_updated.get(app_id)
                if timestamp is None or timestamp == "":
                    return ""  # Empty string sorts to end
                return timestamp

            self.apps.sort(key=recent_sort_key, reverse=True)

        self.log(f"Sorted apps by {self.sort_modes[self.sort_mode]}")

    def show_app_menu(self, app_info):
        """Show overlay menu with app actions."""
        self.menu_visible = True
        app_id = app_info.get("id")
        app_name = app_info.get("name")
        is_installed = self.is_installed(app_id)

        # Build actions list first to calculate menu height
        self.menu_actions = []
        if is_installed:
            self.menu_actions.append(("Launch", lambda: self.launch_app(app_info)))
            self.menu_actions.append(("Update", lambda: self.install_app(app_info)))
            self.menu_actions.append(("Delete", lambda: self.delete_app(app_info)))
        else:
            self.menu_actions.append(("Install", lambda: self.install_app(app_info)))

        # Add Project Page action (shows QR code)
        self.menu_actions.append(("Project Page", lambda: self.show_project_qr(app_info)))
        self.menu_actions.append(("Cancel", lambda: self.hide_app_menu()))

        # Calculate menu height dynamically based on number of items
        # Title: ~25px, Button: 35px each, Gap: 5px between buttons, Padding: 20px total
        num_items = len(self.menu_actions)
        title_height = 25
        button_height = 35
        gap_height = 5
        padding = 20
        menu_height = title_height + (num_items * button_height) + ((num_items - 1) * gap_height) + padding

        # Create semi-transparent overlay
        self.menu_overlay = lv.obj(self.screen)
        self.menu_overlay.set_size(400, 280)
        self.menu_overlay.set_pos(0, 0)
        self.menu_overlay.set_style_bg_color(lv.color_black(), 0)
        self.menu_overlay.set_style_bg_opa(128, 0)  # 50% transparent
        self.menu_overlay.set_style_border_width(0, 0)

        # Create menu container with dynamic height
        self.menu_container = lv.obj(self.screen)
        self.menu_container.set_size(240, menu_height)
        self.menu_container.set_style_bg_color(lv.color_white(), 0)
        self.menu_container.set_style_border_color(lv.color_black(), 0)
        self.menu_container.set_style_border_width(2, 0)
        self.menu_container.set_style_pad_all(10, 0)
        self.menu_container.set_style_pad_gap(5, 0)
        self.menu_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.menu_container.center()

        # Title
        title = lv.label(self.menu_container)
        title.set_text(app_name)
        title.set_style_text_color(lv.color_black(), 0)
        try:
            title.set_style_text_font(lv.font_montserrat_14, 0)
        except:
            pass
        title.set_width(220)
        try:
            title.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass

        # Create menu buttons
        self.menu_buttons = []
        for i, (label, _) in enumerate(self.menu_actions):
            btn = lv.button(self.menu_container)
            btn.set_size(220, 35)
            btn.add_style(self.style_btn_rel, 0)
            if i == 0:
                btn.add_style(self.style_btn_foc, 0)

            lbl = lv.label(btn)
            lbl.set_text(label)
            lbl.center()

            self.menu_buttons.append(btn)

        self.menu_selected = 0
        lv.refr_now(None)

    def hide_app_menu(self):
        """Hide and cleanup the overlay menu."""
        if self.menu_overlay:
            self.menu_overlay.delete()
            self.menu_overlay = None

        if self.menu_container:
            self.menu_container.delete()
            self.menu_container = None

        self.menu_buttons = []
        self.menu_actions = []
        self.menu_selected = 0
        self.menu_visible = False
        lv.refr_now(None)

    def show_project_qr(self, app_info):
        """Show QR code for the app's project page."""
        repo_url = app_info.get("repo", "")
        app_name = app_info.get("name", "App")

        if not repo_url:
            self.hide_app_menu()
            self.show_error("No repository URL")
            return

        # Hide the app menu first
        self.hide_app_menu()

        # Display QR code overlay using LVGL's built-in QR code widget
        self.show_qr_overlay(repo_url, app_name)

    def show_qr_overlay(self, url, app_name):
        """Display QR code in an overlay with instructions."""
        # Create semi-transparent background overlay
        bg_overlay = lv.obj(self.screen)
        bg_overlay.set_size(400, 280)
        bg_overlay.set_pos(0, 0)
        bg_overlay.set_style_bg_color(lv.color_black(), 0)
        bg_overlay.set_style_bg_opa(128, 0)  # 50% transparent
        bg_overlay.set_style_border_width(0, 0)

        # Create QR code container (centered, smaller overlay)
        qr_overlay = lv.obj(self.screen)
        qr_overlay.set_size(240, 260)
        qr_overlay.set_style_bg_color(lv.color_white(), 0)
        qr_overlay.set_style_bg_opa(255, 0)
        qr_overlay.set_style_border_color(lv.color_black(), 0)
        qr_overlay.set_style_border_width(2, 0)
        qr_overlay.set_style_pad_all(10, 0)
        qr_overlay.center()

        # Title
        title = lv.label(qr_overlay)
        title.set_text(f"{app_name}")
        title.set_style_text_color(lv.color_black(), 0)
        try:
            title.set_style_text_font(lv.font_montserrat_14, 0)
        except:
            pass
        title.align(lv.ALIGN.TOP_MID, 0, 5)

        # QR code container
        qr_container = lv.obj(qr_overlay)
        qr_container.set_size(180, 180)
        qr_container.set_style_bg_color(lv.color_white(), 0)
        qr_container.set_style_border_width(1, 0)
        qr_container.set_style_border_color(lv.color_black(), 0)
        qr_container.set_style_pad_all(5, 0)
        qr_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        qr_container.align(lv.ALIGN.CENTER, 0, 0)

        # Generate QR code using LVGL's built-in QR code widget
        try:
            qr_code = lv.qrcode(qr_container)
            qr_code.set_size(170)  # Slightly smaller to fit with padding
            qr_code.set_dark_color(lv.color_black())
            qr_code.set_light_color(lv.color_white())
            qr_code.align(lv.ALIGN.CENTER, 0, 0)
            qr_code.update(url, len(url))
        except Exception as e:
            self.log(f"QR code generation failed: {e}")
            # Show error instead
            error_label = lv.label(qr_container)
            error_label.set_text(f"QR code\nerror")
            error_label.set_style_text_color(lv.color_black(), 0)
            error_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            error_label.align(lv.ALIGN.CENTER, 0, 0)

        # Instructions at bottom
        instructions = lv.label(qr_overlay)
        instructions.set_text("Press ESC to close")
        instructions.set_style_text_color(lv.color_black(), 0)
        instructions.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            instructions.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass
        instructions.align(lv.ALIGN.BOTTOM_MID, 0, -5)

        # Store references to overlays for cleanup
        self.qr_overlay = qr_overlay
        self.qr_bg_overlay = bg_overlay

        # Add keyboard handler for dismissing
        def on_qr_key(e):
            key = e.get_key()
            if key == lv.KEY.ESC or key == lv.KEY.ENTER:
                if hasattr(self, 'qr_bg_overlay') and self.qr_bg_overlay:
                    self.qr_bg_overlay.delete()
                    self.qr_bg_overlay = None
                if hasattr(self, 'qr_overlay') and self.qr_overlay:
                    self.qr_overlay.delete()
                    self.qr_overlay = None

                # Restore input focus to the screen
                import input
                if input.driver and input.driver.group:
                    input.driver.group.remove_all_objs()
                    input.driver.group.add_obj(self.screen)
                    lv.group_focus_obj(self.screen)

                lv.refr_now(None)

        qr_overlay.add_event_cb(on_qr_key, lv.EVENT.KEY, None)

        # Make overlay focusable to receive keyboard events
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(qr_overlay)
            lv.group_focus_obj(qr_overlay)

        lv.refr_now(None)

    def launch_app(self, app_info):
        """Launch an installed app."""
        app_id = app_info.get("id")
        app_name = app_info.get("name")

        if not self.is_installed(app_id):
            self.hide_app_menu()
            self.show_error("App not installed")
            return

        # Find where the app is installed
        category_dir, app_path = self.find_installed_app(app_id)
        if not app_path:
            self.hide_app_menu()
            self.show_error("App not found")
            return

        # Hide menu
        self.hide_app_menu()

        # Try to load and launch the app
        try:
            if app_path not in sys.path:
                sys.path.append(app_path)

            # Try to find the main app file
            main_file = app_info.get("main_file", f"{app_id}_app.py")
            mod_name = main_file[:-3] if main_file.endswith(".py") else main_file

            # Import the module
            if mod_name in sys.modules:
                del sys.modules[mod_name]

            mod = __import__(mod_name)

            # Find the App class
            app_instance = None
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                try:
                    if (isinstance(attr, type) and
                        issubclass(attr, app.App) and
                        attr is not app.App):
                        app_instance = attr()
                        break
                except:
                    continue

            if not app_instance:
                self.show_error(f"Could not load {app_name}")
                return

            # Save callback
            saved_callback = self.on_exit

            # Exit app store cleanly
            self.exit()

            # Launch the app
            def on_app_exit():
                # Re-enter app store
                self.enter(on_exit=saved_callback)

            app_instance.enter(on_exit=on_app_exit)

        except Exception as e:
            self.log(f"Launch error: {e}")
            self.show_error(f"Failed to launch: {str(e)}")

    def install_app(self, app_info):
        """Install or update the selected app."""
        app_id = app_info.get("id")
        app_name = app_info.get("name")

        if not app_id:
            self.show_error("Invalid app metadata")
            return

        # Check if updating or installing
        is_update = self.is_installed(app_id)
        action = "Updating" if is_update else "Installing"

        # Show status
        self.list_cont.add_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.add_flag(lv.obj.FLAG.HIDDEN)
        self.divider.add_flag(lv.obj.FLAG.HIDDEN)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.info_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.status_label.remove_flag(lv.obj.FLAG.HIDDEN)
        self.status_label.set_text(f"{action} {app_name}...")
        lv.refr_now(None)

        # Ensure store repo is cloned
        try:
            os.stat(self.store_path)
            # Update existing
            self.status_label.set_text(f"Updating store repo...")
            lv.refr_now(None)
            success, output = self.run_command(f"cd {self.store_path} && git pull")
            if not success:
                self.show_error(f"Failed to update store")
                return
        except:
            # Clone fresh
            self.status_label.set_text(f"Cloning store repo...")
            lv.refr_now(None)
            success, output = self.run_command(f"git clone {self.store_repo} {self.store_path}")
            if not success:
                self.show_error(f"Failed to clone store")
                return

        # Initialize and update the specific submodule
        submodule_path = f"apps/{app_id}/app"
        self.status_label.set_text(f"Fetching {app_name}...")
        lv.refr_now(None)

        success, output = self.run_command(
            f"cd {self.store_path} && git submodule update --init --recursive {submodule_path}"
        )

        if not success:
            self.show_error(f"Failed to fetch app")
            return

        # Copy app to applications directory
        self.status_label.set_text(f"Installing {app_name}...")
        lv.refr_now(None)

        # Determine target directory based on category
        category = app_info.get("category", "apps")
        category_dir = self.get_category_dir(category)

        # Ensure category directory exists
        category_path = f"applications/{category_dir}"
        try:
            os.stat(category_path)
        except:
            # Create directory if it doesn't exist
            try:
                os.mkdir(category_path)
                self.log(f"Created category directory: {category_path}")
            except Exception as e:
                self.log(f"Failed to create category directory: {e}")
                self.show_error(f"Failed to create category dir")
                return

        src = f"{self.store_path}/{submodule_path}"
        dest = f"{category_path}/{app_id}"

        # Remove old version if exists (check all categories)
        old_category_dir, old_app_path = self.find_installed_app(app_id)
        if old_app_path:
            self.run_command(f"rm -rf {old_app_path}")
            self.log(f"Removed old version at {old_app_path}")

        # Copy new version
        success, output = self.run_command(f"cp -r {src} {dest}")

        if not success:
            self.show_error(f"Failed to install")
            return

        # Copy metadata.json to track installed version
        metadata_src = f"{self.store_path}/apps/{app_id}/metadata.json"
        metadata_dest = f"{dest}/metadata.json"
        self.run_command(f"cp {metadata_src} {metadata_dest}")

        # Success!
        action_past = "updated" if is_update else "installed"
        self.status_label.set_text(f"SUCCESS: {app_name} {action_past}!")
        time.sleep(2)

        # Return to list with fresh status
        self.status_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.list_cont.remove_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.remove_flag(lv.obj.FLAG.HIDDEN)
        self.divider.remove_flag(lv.obj.FLAG.HIDDEN)
        self.info_label.remove_flag(lv.obj.FLAG.HIDDEN)
        self.render_list()
        self.update_description()
        lv.refr_now(None)

    def delete_app(self, app_info):
        """Delete the selected app."""
        app_id = app_info.get("id")
        app_name = app_info.get("name")

        if not app_id:
            self.show_error("Invalid app metadata")
            return

        if not self.is_installed(app_id):
            self.show_error("App not installed")
            return

        # Show status
        self.list_cont.add_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.add_flag(lv.obj.FLAG.HIDDEN)
        self.divider.add_flag(lv.obj.FLAG.HIDDEN)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        self.info_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.status_label.remove_flag(lv.obj.FLAG.HIDDEN)
        self.status_label.set_text(f"Deleting {app_name}...")
        lv.refr_now(None)

        # Find and delete app from wherever it's installed
        category_dir, app_path = self.find_installed_app(app_id)

        if not app_path:
            self.show_error("App not found")
            return

        # Delete the app
        success, output = self.run_command(f"rm -rf {app_path}")

        if not success:
            self.show_error(f"Failed to delete")
            self.log(f"Delete failed: {output}")
            return

        self.log(f"Deleted {app_path}")

        # Success!
        self.status_label.set_text(f"SUCCESS: {app_name} deleted!")
        time.sleep(2)

        # Return to list with fresh status
        self.status_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.list_cont.remove_flag(lv.obj.FLAG.HIDDEN)
        self.desc_panel.remove_flag(lv.obj.FLAG.HIDDEN)
        self.divider.remove_flag(lv.obj.FLAG.HIDDEN)
        self.info_label.remove_flag(lv.obj.FLAG.HIDDEN)
        self.render_list()
        self.update_description()
        lv.refr_now(None)

    def show_error(self, message):
        """Show error message."""
        self.status_label.set_text(f"Error: {message}\n\nPress ESC to return")
        lv.refr_now(None)

    def on_key(self, e):
        if self.loading:
            return

        key = e.get_key()

        # Handle category menu navigation
        if self.current_view == "menu":
            if key == lv.KEY.ESC:
                self.exit()
                if self.on_exit:
                    self.on_exit()
            elif key == lv.KEY.UP:
                self.category_selected_idx = (self.category_selected_idx - 1) % len(self.categories)
                # Update button styles
                for i, btn in enumerate(self.category_buttons):
                    try:
                        btn.remove_style(self.style_btn_foc, 0)
                    except:
                        pass
                    if i == self.category_selected_idx:
                        btn.add_style(self.style_btn_foc, 0)
                lv.refr_now(None)
            elif key == lv.KEY.DOWN:
                self.category_selected_idx = (self.category_selected_idx + 1) % len(self.categories)
                # Update button styles
                for i, btn in enumerate(self.category_buttons):
                    try:
                        btn.remove_style(self.style_btn_foc, 0)
                    except:
                        pass
                    if i == self.category_selected_idx:
                        btn.add_style(self.style_btn_foc, 0)
                lv.refr_now(None)
            elif key == lv.KEY.ENTER:
                # Select category and show app list
                self.selected_category = self.categories[self.category_selected_idx]["id"]
                self.show_app_list()
            return

        # Handle app menu navigation (overlay menu when viewing app details)
        if self.menu_visible:
            if key == lv.KEY.ESC:
                self.hide_app_menu()
            elif key == lv.KEY.UP:
                self.menu_selected = (self.menu_selected - 1) % len(self.menu_actions)

                # Update button styles
                for i, btn in enumerate(self.menu_buttons):
                    try:
                        btn.remove_style(self.style_btn_foc, 0)
                    except:
                        pass
                    if i == self.menu_selected:
                        btn.add_style(self.style_btn_foc, 0)
                lv.refr_now(None)

            elif key == lv.KEY.DOWN:
                self.menu_selected = (self.menu_selected + 1) % len(self.menu_actions)

                # Update button styles
                for i, btn in enumerate(self.menu_buttons):
                    try:
                        btn.remove_style(self.style_btn_foc, 0)
                    except:
                        pass
                    if i == self.menu_selected:
                        btn.add_style(self.style_btn_foc, 0)
                lv.refr_now(None)

            elif key == lv.KEY.ENTER:
                if 0 <= self.menu_selected < len(self.menu_actions):
                    action = self.menu_actions[self.menu_selected][1]
                    self.hide_app_menu()
                    lv.async_call(lambda _: action(), None)
            return

        # Handle app list navigation
        if key == lv.KEY.ESC:
            # Go back to category menu
            self.show_category_menu()

        elif key == lv.KEY.UP:
            filtered_apps = self.get_filtered_apps()
            if filtered_apps and not self.list_cont.has_flag(lv.obj.FLAG.HIDDEN):
                self.selected_idx = (self.selected_idx - 1) % len(filtered_apps)

                # Scroll window if needed
                if self.selected_idx < self.visible_start:
                    self.visible_start = self.selected_idx
                elif self.selected_idx >= self.visible_start + self.visible_count:
                    self.visible_start = self.selected_idx - self.visible_count + 1

                self.render_list()
                self.update_description()

        elif key == lv.KEY.DOWN:
            filtered_apps = self.get_filtered_apps()
            if filtered_apps and not self.list_cont.has_flag(lv.obj.FLAG.HIDDEN):
                self.selected_idx = (self.selected_idx + 1) % len(filtered_apps)

                # Scroll window if needed
                if self.selected_idx < self.visible_start:
                    self.visible_start = self.selected_idx
                elif self.selected_idx >= self.visible_start + self.visible_count:
                    self.visible_start = self.selected_idx - self.visible_count + 1

                self.render_list()
                self.update_description()

        elif key == lv.KEY.ENTER:
            filtered_apps = self.get_filtered_apps()
            if filtered_apps and not self.list_cont.has_flag(lv.obj.FLAG.HIDDEN):
                selected_app = filtered_apps[self.selected_idx]
                self.show_app_menu(selected_app)

        elif key == lv.KEY.LEFT or key == lv.KEY.RIGHT:
            filtered_apps = self.get_filtered_apps()
            if filtered_apps and not self.list_cont.has_flag(lv.obj.FLAG.HIDDEN):
                # Cycle sort mode
                if key == lv.KEY.RIGHT:
                    self.sort_mode = (self.sort_mode + 1) % len(self.sort_modes)
                else:
                    self.sort_mode = (self.sort_mode - 1) % len(self.sort_modes)

                # Update label
                self.sort_label.set_text(f"Sort: {self.sort_modes[self.sort_mode]}")

                # Re-sort and render
                self.sort_apps()
                self.selected_idx = 0
                self.visible_start = 0
                self.render_list()
                self.update_description()

    def exit(self):
        # Clean up menu if visible
        if self.menu_visible:
            self.hide_app_menu()

        # Clean up QR overlay if visible
        if self.qr_bg_overlay:
            try:
                self.qr_bg_overlay.delete()
            except:
                pass
            self.qr_bg_overlay = None
        if self.qr_overlay:
            try:
                self.qr_overlay.delete()
            except:
                pass
            self.qr_overlay = None

        if self.screen:
            self.screen.delete()
            self.screen = None

        # Clear all object references to avoid issues on re-entry
        self.buttons = []
        self.list_cont = None
        self.desc_panel = None
        self.desc_name = None
        self.desc_author = None
        self.desc_version = None
        self.desc_text = None
        self.desc_status = None
        self.up_arrow = None
        self.down_arrow = None
        self.divider = None
        self.status_label = None
        self.info_label = None
        self.sort_label = None
        self.menu_overlay = None
        self.menu_container = None
        self.menu_buttons = []
        self.menu_actions = []
        self.category_container = None
        self.category_buttons = []
        self.loading = False
        self.menu_visible = False
        self.current_view = "menu"
        # Keep star_counts, sort_mode, and category selection cached across sessions
