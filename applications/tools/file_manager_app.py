"""File Manager - Browse and manage files on the badge.

Navigate directories, view files, and perform basic file operations.
"""

import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import lvgl as lv
import os
import time

class FileManagerApp(app.App):
    def __init__(self):
        super().__init__("File Manager")
        self.screen = None
        self.list_cont = None
        self.buttons = []
        self.items = []  # List of (name, is_dir, size) tuples
        self.selected_idx = 0
        self.visible_start = 0
        self.visible_count = 5
        # Start in current working directory
        try:
            self.current_path = os.getcwd()
            self.starting_path = self.current_path
        except:
            self.current_path = "."
            self.starting_path = "."

        # UI elements for right panel
        self.desc_panel = None
        self.desc_name = None
        self.desc_type = None
        self.desc_size = None
        self.desc_path = None
        self.info_label = None
        self.sort_label = None

        # Arrows
        self.up_arrow = None
        self.down_arrow = None
        self.divider = None

        # Overlay menu
        self.menu_overlay = None
        self.menu_container = None
        self.menu_buttons = []
        self.menu_actions = []
        self.menu_selected = 0
        self.menu_visible = False

        # Text viewer overlay
        self.text_overlay = None
        self.text_bg_overlay = None

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

    def format_size(self, size):
        """Format file size in human readable format."""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size // 1024}KB"
        else:
            return f"{size // (1024 * 1024)}MB"

    def get_parent_dir(self, path):
        """Get parent directory of a path (MicroPython compatible)."""
        # Remove trailing slash if present
        path = path.rstrip('/')
        # Split and rejoin without last component
        parts = path.split('/')
        if len(parts) <= 1:
            return None
        parent = '/'.join(parts[:-1])
        # Handle root case
        if not parent:
            return '/'
        return parent

    def load_directory(self):
        """Load contents of current directory."""
        self.items = []

        try:
            entries = os.listdir(self.current_path)

            # Sort: directories first, then files, both alphabetically
            dirs = []
            files = []

            for entry in entries:
                # Skip hidden files
                if entry.startswith('.'):
                    continue

                # Build full path
                if self.current_path.endswith('/'):
                    full_path = f"{self.current_path}{entry}"
                else:
                    full_path = f"{self.current_path}/{entry}"

                try:
                    stat = os.stat(full_path)
                    is_dir = stat[0] & 0x4000  # S_IFDIR bit
                    size = stat[6] if not is_dir else 0

                    if is_dir:
                        dirs.append((entry, True, size))
                    else:
                        files.append((entry, False, size))
                except:
                    continue

            # Sort both lists
            dirs.sort(key=lambda x: x[0].lower())
            files.sort(key=lambda x: x[0].lower())

            # Add parent directory entry if not at starting directory
            # Normalize paths for comparison (remove trailing slashes)
            current_norm = self.current_path.rstrip('/')
            starting_norm = self.starting_path.rstrip('/')
            if current_norm != starting_norm:
                self.items.append(("..", True, 0))

            # Combine: directories first, then files
            self.items.extend(dirs)
            self.items.extend(files)

        except Exception as e:
            # If directory read fails, go back to starting directory
            current_norm = self.current_path.rstrip('/')
            starting_norm = self.starting_path.rstrip('/')
            if current_norm != starting_norm:
                self.current_path = self.starting_path
                self.load_directory()

    def enter(self, on_exit=None):
        """Initialize and display the file manager."""
        self.on_exit = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        # Load initial directory
        self.load_directory()

        # Create UI layout (two-panel design)
        self.create_ui()

        # Add keyboard handler
        self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        # Setup input group
        import input
        if input.driver and input.driver.group:
            input.driver.group.set_editing(False)
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        # Initial render
        self.render_list()
        self.update_description()
        lv.refr_now(None)

    def create_ui(self):
        """Create the two-panel UI layout."""
        # Left panel - File list
        self.list_cont = lv.obj(self.screen)
        self.list_cont.set_size(190, 240)
        self.list_cont.set_pos(5, 35)
        self.list_cont.set_style_bg_color(lv.color_white(), 0)
        self.list_cont.set_style_border_width(1, 0)
        self.list_cont.set_style_border_color(lv.color_black(), 0)
        self.list_cont.set_style_pad_all(5, 0)
        self.list_cont.set_style_pad_gap(5, 0)
        self.list_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list_cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
        self.list_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Up arrow
        self.up_arrow = lv.label(self.screen)
        self.up_arrow.set_text("^")
        self.up_arrow.set_pos(90, 30)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Down arrow
        self.down_arrow = lv.label(self.screen)
        self.down_arrow.set_text("v")
        self.down_arrow.set_pos(90, 275)
        self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Divider
        self.divider = lv.obj(self.screen)
        self.divider.set_size(2, 240)
        self.divider.set_pos(199, 35)
        self.divider.set_style_bg_color(lv.color_black(), 0)
        self.divider.set_style_border_width(0, 0)

        # Right panel - Details
        self.desc_panel = lv.obj(self.screen)
        self.desc_panel.set_size(190, 240)
        self.desc_panel.set_pos(205, 35)
        self.desc_panel.set_style_bg_color(lv.color_white(), 0)
        self.desc_panel.set_style_border_width(1, 0)
        self.desc_panel.set_style_border_color(lv.color_black(), 0)
        self.desc_panel.set_style_pad_all(10, 0)
        self.desc_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Name
        self.desc_name = lv.label(self.desc_panel)
        self.desc_name.set_width(170)
        self.desc_name.set_pos(0, 5)
        self.desc_name.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_name.set_style_text_font(lv.font_montserrat_14, 0)
        except:
            pass
        try:
            self.desc_name.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass

        # Type
        self.desc_type = lv.label(self.desc_panel)
        self.desc_type.set_width(170)
        self.desc_type.set_pos(0, 50)
        self.desc_type.set_style_text_color(lv.color_black(), 0)

        # Size
        self.desc_size = lv.label(self.desc_panel)
        self.desc_size.set_width(170)
        self.desc_size.set_pos(0, 75)
        self.desc_size.set_style_text_color(lv.color_black(), 0)

        # Path
        self.desc_path = lv.label(self.desc_panel)
        self.desc_path.set_width(170)
        self.desc_path.set_pos(0, 110)
        self.desc_path.set_style_text_color(lv.palette_main(lv.PALETTE.GREY), 0)
        try:
            self.desc_path.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass
        try:
            self.desc_path.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass

        # Current path label at top
        self.sort_label = lv.label(self.screen)
        self.sort_label.set_text(self.current_path)
        self.sort_label.set_pos(10, 5)
        self.sort_label.set_width(380)
        try:
            self.sort_label.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        try:
            self.sort_label.set_long_mode(lv.LABEL_LONG.DOT)
        except:
            pass

        # Instructions at bottom
        self.info_label = lv.label(self.screen)
        self.info_label.set_text("UP/DN: Select | ENTER: Open/Menu | ESC: Back")
        self.info_label.set_pos(10, 278)
        self.info_label.set_width(380)
        try:
            self.info_label.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass

    def render_list(self):
        """Render the visible portion of the file list."""
        # Clear existing buttons
        for btn in self.buttons:
            try:
                btn.delete()
            except:
                pass
        self.buttons = []

        # Calculate visible range
        end_idx = min(self.visible_start + self.visible_count, len(self.items))

        # Show/hide arrows
        if self.visible_start > 0:
            self.up_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        if end_idx < len(self.items):
            self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Create buttons for visible items
        for i in range(self.visible_start, end_idx):
            name, is_dir, size = self.items[i]

            # Show folder icon or file indicator
            prefix = "[D] " if is_dir else "[F] "
            text = f"{prefix}{name}"

            btn = lv.button(self.list_cont)
            btn.set_size(175, 35)
            btn.add_style(self.style_btn_rel, 0)

            # Highlight selected
            if i == self.selected_idx:
                btn.add_style(self.style_btn_foc, 0)

            lbl = lv.label(btn)
            lbl.set_text(text)
            lbl.set_width(160)
            try:
                lbl.set_long_mode(lv.LABEL_LONG.DOT)
            except:
                pass
            lbl.align(lv.ALIGN.LEFT_MID, 5, 0)

            self.buttons.append(btn)

        lv.refr_now(None)

    def update_description(self):
        """Update the right panel with selected item info."""
        if not self.items or self.selected_idx >= len(self.items):
            return

        name, is_dir, size = self.items[self.selected_idx]

        # Update name
        self.desc_name.set_text(name)

        # Update type
        if name == "..":
            self.desc_type.set_text("Type: Parent Directory")
        elif is_dir:
            self.desc_type.set_text("Type: Directory")
        else:
            # Try to guess file type from extension
            if "." in name:
                ext = name.split(".")[-1].upper()
                self.desc_type.set_text(f"Type: {ext} File")
            else:
                self.desc_type.set_text("Type: File")

        # Update size
        if is_dir and name != "..":
            self.desc_size.set_text("Size: -")
        else:
            self.desc_size.set_text(f"Size: {self.format_size(size)}")

        # Update path
        if self.current_path.endswith('/'):
            full_path = f"{self.current_path}{name}"
        else:
            full_path = f"{self.current_path}/{name}"
        self.desc_path.set_text(f"Path:\n{full_path}")

    def show_item_menu(self):
        """Show overlay menu with file/folder actions."""
        if not self.items or self.selected_idx >= len(self.items):
            return

        name, is_dir, size = self.items[self.selected_idx]

        # Don't show menu for parent directory
        if name == "..":
            return

        self.menu_visible = True

        # Build actions list
        self.menu_actions = []

        if is_dir:
            # Directory actions
            self.menu_actions.append(("Open", lambda: self.enter_directory()))
            self.menu_actions.append(("Delete", lambda: self.delete_item()))
        else:
            # File actions
            # Check if it's a text file
            if self.is_text_file(name):
                self.menu_actions.append(("View", lambda: self.view_text_file()))
            self.menu_actions.append(("Delete", lambda: self.delete_item()))

        self.menu_actions.append(("Cancel", lambda: self.hide_item_menu()))

        # Calculate menu height
        num_items = len(self.menu_actions)
        title_height = 30
        button_height = 40
        gap_height = 5
        padding = 25
        menu_height = title_height + (num_items * button_height) + ((num_items - 1) * gap_height) + padding

        # Create semi-transparent overlay
        self.menu_overlay = lv.obj(self.screen)
        self.menu_overlay.set_size(400, 280)
        self.menu_overlay.set_pos(0, 0)
        self.menu_overlay.set_style_bg_color(lv.color_black(), 0)
        self.menu_overlay.set_style_bg_opa(128, 0)
        self.menu_overlay.set_style_border_width(0, 0)

        # Create menu container
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
        title.set_text(name)
        title.set_style_text_color(lv.color_black(), 0)
        try:
            title.set_style_text_font(lv.font_montserrat_14, 0)
        except:
            pass
        title.set_width(220)
        try:
            title.set_long_mode(lv.LABEL_LONG.DOT)
        except:
            pass

        # Create menu buttons
        self.menu_buttons = []
        for i, (label, _) in enumerate(self.menu_actions):
            btn = lv.button(self.menu_container)
            btn.set_size(220, 40)
            btn.add_style(self.style_btn_rel, 0)
            if i == 0:
                btn.add_style(self.style_btn_foc, 0)

            lbl = lv.label(btn)
            lbl.set_text(label)
            lbl.center()

            self.menu_buttons.append(btn)

        self.menu_selected = 0
        lv.refr_now(None)

    def hide_item_menu(self):
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

    def enter_directory(self):
        """Enter the selected directory."""
        if not self.items or self.selected_idx >= len(self.items):
            return

        name, is_dir, size = self.items[self.selected_idx]

        if not is_dir:
            return

        # Hide menu if visible
        if self.menu_visible:
            self.hide_item_menu()

        # Handle parent directory
        if name == "..":
            # Go up one level
            parent = self.get_parent_dir(self.current_path)
            if parent:
                self.current_path = parent
            else:
                self.current_path = self.starting_path
        else:
            # Enter directory
            if self.current_path.endswith('/'):
                self.current_path = f"{self.current_path}{name}"
            else:
                self.current_path = f"{self.current_path}/{name}"

        # Reload directory and reset selection
        self.load_directory()
        self.selected_idx = 0
        self.visible_start = 0

        # Update UI
        self.sort_label.set_text(self.current_path)
        self.render_list()
        self.update_description()

    def is_text_file(self, filename):
        """Check if file is likely a text file based on extension."""
        text_extensions = ['.txt', '.py', '.json', '.md', '.log', '.cfg', '.conf',
                          '.ini', '.sh', '.c', '.h', '.cpp', '.hpp', '.js', '.html',
                          '.css', '.xml', '.yaml', '.yml']
        return any(filename.lower().endswith(ext) for ext in text_extensions)

    def view_text_file(self):
        """Display text file contents in an overlay."""
        if not self.items or self.selected_idx >= len(self.items):
            return

        name, is_dir, size = self.items[self.selected_idx]

        if is_dir:
            return

        # Hide menu
        self.hide_item_menu()

        # Build full path
        if self.current_path.endswith('/'):
            file_path = f"{self.current_path}{name}"
        else:
            file_path = f"{self.current_path}/{name}"

        # Read file
        try:
            with open(file_path, 'r') as f:
                content = f.read(2000)  # Limit to 2000 chars
        except Exception as e:
            content = f"Error reading file:\n{str(e)}"

        # Show overlay
        self.show_text_overlay(name, content)

    def show_text_overlay(self, filename, content):
        """Display text content in an overlay."""
        # Create semi-transparent background
        bg_overlay = lv.obj(self.screen)
        bg_overlay.set_size(400, 280)
        bg_overlay.set_pos(0, 0)
        bg_overlay.set_style_bg_color(lv.color_black(), 0)
        bg_overlay.set_style_bg_opa(128, 0)
        bg_overlay.set_style_border_width(0, 0)

        # Create text viewer container
        text_overlay = lv.obj(self.screen)
        text_overlay.set_size(360, 260)
        text_overlay.set_style_bg_color(lv.color_white(), 0)
        text_overlay.set_style_bg_opa(255, 0)
        text_overlay.set_style_border_color(lv.color_black(), 0)
        text_overlay.set_style_border_width(2, 0)
        text_overlay.set_style_pad_all(10, 0)
        text_overlay.center()

        # Title
        title = lv.label(text_overlay)
        title.set_text(filename)
        title.set_style_text_color(lv.color_black(), 0)
        try:
            title.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        title.set_width(340)
        try:
            title.set_long_mode(lv.LABEL_LONG.DOT)
        except:
            pass
        title.align(lv.ALIGN.TOP_MID, 0, 5)

        # Text area for content
        text_area = lv.textarea(text_overlay)
        text_area.set_size(340, 190)
        text_area.set_pos(0, 25)
        text_area.set_text(content)
        text_area.set_style_text_color(lv.color_black(), 0)
        try:
            text_area.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass

        # Instructions
        instructions = lv.label(text_overlay)
        instructions.set_text("Press ESC to close")
        instructions.set_style_text_color(lv.color_black(), 0)
        instructions.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        try:
            instructions.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass
        instructions.align(lv.ALIGN.BOTTOM_MID, 0, 0)

        # Store references
        self.text_overlay = text_overlay
        self.text_bg_overlay = bg_overlay

        # Keyboard handler
        def on_text_key(e):
            key = e.get_key()
            if key == lv.KEY.ESC or key == lv.KEY.ENTER:
                if hasattr(self, 'text_bg_overlay') and self.text_bg_overlay:
                    self.text_bg_overlay.delete()
                    self.text_bg_overlay = None
                if hasattr(self, 'text_overlay') and self.text_overlay:
                    self.text_overlay.delete()
                    self.text_overlay = None

                # Restore focus
                import input
                if input.driver and input.driver.group:
                    input.driver.group.remove_all_objs()
                    input.driver.group.add_obj(self.screen)
                    lv.group_focus_obj(self.screen)

                lv.refr_now(None)

        text_overlay.add_event_cb(on_text_key, lv.EVENT.KEY, None)

        # Make focusable
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(text_overlay)
            lv.group_focus_obj(text_overlay)

        lv.refr_now(None)

    def delete_item(self):
        """Delete the selected file or directory."""
        if not self.items or self.selected_idx >= len(self.items):
            return

        name, is_dir, size = self.items[self.selected_idx]

        # Hide menu
        self.hide_item_menu()

        # Build full path
        if self.current_path.endswith('/'):
            item_path = f"{self.current_path}{name}"
        else:
            item_path = f"{self.current_path}/{name}"

        # Delete item
        try:
            if is_dir:
                # Try to remove directory
                os.rmdir(item_path)
            else:
                # Remove file
                os.remove(item_path)

            # Reload directory
            self.load_directory()

            # Adjust selection if needed
            if self.selected_idx >= len(self.items):
                self.selected_idx = max(0, len(self.items) - 1)

            # Re-render
            self.render_list()
            self.update_description()
        except Exception as e:
            # Show error - just ignore for now
            pass

    def on_key(self, e):
        """Handle keyboard input."""
        key = e.get_key()

        if self.menu_visible:
            # Handle menu navigation
            if key == lv.KEY.UP:
                self.menu_selected = (self.menu_selected - 1) % len(self.menu_actions)
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
                for i, btn in enumerate(self.menu_buttons):
                    try:
                        btn.remove_style(self.style_btn_foc, 0)
                    except:
                        pass
                    if i == self.menu_selected:
                        btn.add_style(self.style_btn_foc, 0)
                lv.refr_now(None)
            elif key == lv.KEY.ENTER:
                # Execute selected action
                if self.menu_selected < len(self.menu_actions):
                    _, action = self.menu_actions[self.menu_selected]
                    action()
            elif key == lv.KEY.ESC:
                self.hide_item_menu()
        else:
            # Handle list navigation
            if key == lv.KEY.ESC:
                # Go back - check if we're at starting directory
                current_norm = self.current_path.rstrip('/')
                starting_norm = self.starting_path.rstrip('/')
                if current_norm == starting_norm:
                    # Exit app
                    self.exit()
                    if self.on_exit:
                        self.on_exit()
                else:
                    # Go to parent directory
                    parent = self.get_parent_dir(self.current_path)
                    if parent:
                        self.current_path = parent
                    else:
                        self.current_path = self.starting_path
                    self.load_directory()
                    self.selected_idx = 0
                    self.visible_start = 0
                    self.sort_label.set_text(self.current_path)
                    self.render_list()
                    self.update_description()
            elif key == lv.KEY.UP:
                if self.selected_idx > 0:
                    self.selected_idx -= 1
                    if self.selected_idx < self.visible_start:
                        self.visible_start = self.selected_idx
                    self.render_list()
                    self.update_description()
            elif key == lv.KEY.DOWN:
                if self.selected_idx < len(self.items) - 1:
                    self.selected_idx += 1
                    if self.selected_idx >= self.visible_start + self.visible_count:
                        self.visible_start = self.selected_idx - self.visible_count + 1
                    self.render_list()
                    self.update_description()
            elif key == lv.KEY.ENTER:
                # Open directory or show menu
                if not self.items:
                    return

                name, is_dir, size = self.items[self.selected_idx]

                if is_dir:
                    # Enter directory directly
                    self.enter_directory()
                else:
                    # Show menu for files
                    self.show_item_menu()

    def exit(self):
        """Cleanup and exit the file manager."""
        # Clean up overlays
        if self.menu_visible:
            self.hide_item_menu()

        if self.text_bg_overlay:
            try:
                self.text_bg_overlay.delete()
            except:
                pass
            self.text_bg_overlay = None

        if self.text_overlay:
            try:
                self.text_overlay.delete()
            except:
                pass
            self.text_overlay = None

        if self.screen:
            self.screen.delete()
            self.screen = None

        # Clear references
        self.buttons = []
        self.items = []
        self.list_cont = None
        self.desc_panel = None
