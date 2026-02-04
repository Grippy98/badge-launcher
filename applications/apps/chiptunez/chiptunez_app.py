"""ChipTunez music player application.

Play classic chiptune melodies using the system beeper. Includes songs like
Imperial March, Super Mario, Doom, Nokia Tune, and more.

Add your own songs by placing JSON files in the songs/ directory!
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import time
import config
import sound
import json
import os

# Icon name to symbol mapping
ICON_MAP = {
    "AUDIO": lv.SYMBOL.AUDIO,
    "VIDEO": lv.SYMBOL.VIDEO,
    "LIST": lv.SYMBOL.LIST,
    "OK": lv.SYMBOL.OK,
    "CLOSE": lv.SYMBOL.CLOSE,
    "POWER": lv.SYMBOL.POWER,
    "SETTINGS": lv.SYMBOL.SETTINGS,
    "HOME": lv.SYMBOL.HOME,
    "DOWNLOAD": lv.SYMBOL.DOWNLOAD,
    "DRIVE": lv.SYMBOL.DRIVE,
    "REFRESH": lv.SYMBOL.REFRESH,
    "MUTE": lv.SYMBOL.MUTE,
    "VOLUME_MID": lv.SYMBOL.VOLUME_MID,
    "VOLUME_MAX": lv.SYMBOL.VOLUME_MAX,
    "IMAGE": lv.SYMBOL.IMAGE,
    "EDIT": lv.SYMBOL.EDIT,
    "PREV": lv.SYMBOL.PREV,
    "PLAY": lv.SYMBOL.PLAY,
    "PAUSE": lv.SYMBOL.PAUSE,
    "STOP": lv.SYMBOL.STOP,
    "NEXT": lv.SYMBOL.NEXT,
    "EJECT": lv.SYMBOL.EJECT,
    "LEFT": lv.SYMBOL.LEFT,
    "RIGHT": lv.SYMBOL.RIGHT,
    "PLUS": lv.SYMBOL.PLUS,
    "MINUS": lv.SYMBOL.MINUS,
    "WARNING": lv.SYMBOL.WARNING,
    "SHUFFLE": lv.SYMBOL.SHUFFLE,
    "UP": lv.SYMBOL.UP,
    "DOWN": lv.SYMBOL.DOWN,
    "LOOP": lv.SYMBOL.LOOP,
    "DIRECTORY": lv.SYMBOL.DIRECTORY,
    "UPLOAD": lv.SYMBOL.UPLOAD,
    "CALL": lv.SYMBOL.CALL,
    "CUT": lv.SYMBOL.CUT,
    "COPY": lv.SYMBOL.COPY,
    "SAVE": lv.SYMBOL.SAVE,
    "CHARGE": lv.SYMBOL.CHARGE,
    "BLUETOOTH": lv.SYMBOL.BLUETOOTH,
    "GPS": lv.SYMBOL.GPS,
    "USB": lv.SYMBOL.USB,
    "SD_CARD": lv.SYMBOL.SD_CARD,
    "WIFI": lv.SYMBOL.WIFI,
}

def load_songs_from_json():
    """Load songs from JSON files in the songs/ subdirectory"""
    songs = []
    # Use relative path from the app directory
    songs_dir = "applications/apps/chiptunez/songs"

    try:
        files = os.listdir(songs_dir)
    except:
        # Directory doesn't exist, return empty list
        print("Warning: Could not find songs directory")
        return []

    try:
        for filename in files:
            if not filename.endswith('.json'):
                continue

            filepath = f"{songs_dir}/{filename}"
            try:
                with open(filepath, 'r') as f:
                    song_data = json.load(f)

                # Validate required fields
                if not all(key in song_data for key in ['title', 'notes', 'desc']):
                    print(f"Skipping {filename}: missing required fields")
                    continue

                # Convert notes from list to tuples
                notes = [tuple(note) for note in song_data['notes']]

                # Get icon from map or use default
                icon_name = song_data.get('icon', 'AUDIO')
                icon = ICON_MAP.get(icon_name, lv.SYMBOL.AUDIO)

                songs.append({
                    "title": song_data['title'],
                    "notes": notes,
                    "desc": song_data['desc'],
                    "icon": icon
                })
                print(f"Loaded song: {song_data['title']}")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    except Exception as e:
        print(f"Error reading songs directory: {e}")

    # Sort songs alphabetically by title
    songs.sort(key=lambda x: x['title'])
    return songs

class ChipTunezApp(app.App):
    def __init__(self):
        super().__init__("ChipTunez")
        self.screen = None
        self.playing = False
        self.song_timer = None
        self.current_song_notes = []
        self.note_idx = 0
        self.songs = None  # Lazy load songs when entering app

        # Create button styles
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

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        lv.screen_load(self.screen)

        # Title
        title = lv.label(self.screen)
        title.set_text("ChipTunez")
        title.align(lv.ALIGN.TOP_MID, 0, 10)
        title.set_style_text_color(lv.color_black(), 0)

        # Load songs on first entry (lazy loading)
        if self.songs is None:
            self.songs = load_songs_from_json()

        # Check if we have songs
        if not self.songs:
            error_lbl = lv.label(self.screen)
            error_lbl.set_text("No songs found!\nAdd JSON files to\napplications/apps/chiptunez/songs/")
            error_lbl.center()
            error_lbl.set_style_text_color(lv.color_black(), 0)
            return

        # Up Arrow (left side, near list)
        self.up_arrow = lv.label(self.screen)
        self.up_arrow.set_text(lv.SYMBOL.UP)
        self.up_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.up_arrow.set_style_text_font(lv.font_montserrat_20, 0)
        except:
            pass
        self.up_arrow.set_pos(10, 48)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)

        # Left panel - Song list container
        # Screen is 400x300. Divider at 200px (middle), showing exactly 5 songs
        self.cont = lv.obj(self.screen)
        self.cont.set_size(180, 170)  # 5 songs * 34px each = 170px
        self.cont.set_pos(10, 70)
        self.cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.cont.set_style_bg_opa(0, 0)
        self.cont.set_style_border_width(0, 0)
        self.cont.set_style_pad_all(0, 0)
        self.cont.set_style_pad_gap(2, 0)  # 2px gap between buttons
        self.cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Down Arrow (left side, below list)
        self.down_arrow = lv.label(self.screen)
        self.down_arrow.set_text(lv.SYMBOL.DOWN)
        self.down_arrow.set_style_text_color(lv.color_black(), 0)
        try:
            self.down_arrow.set_style_text_font(lv.font_montserrat_20, 0)
        except:
            pass
        self.down_arrow.set_pos(10, 245)

        # Vertical divider line (middle of screen)
        self.divider = lv.obj(self.screen)
        self.divider.set_size(2, 210)
        self.divider.set_pos(199, 50)  # Centered at x=200
        self.divider.set_style_bg_color(lv.color_black(), 0)
        self.divider.set_style_border_width(0, 0)

        # Right panel - Description area
        self.desc_panel = lv.obj(self.screen)
        self.desc_panel.set_size(190, 210)  # More room for descriptions
        self.desc_panel.set_pos(205, 50)
        self.desc_panel.set_style_bg_opa(0, 0)
        self.desc_panel.set_style_border_width(0, 0)
        self.desc_panel.set_style_pad_all(5, 0)
        self.desc_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Description icon
        self.desc_icon = lv.label(self.desc_panel)
        self.desc_icon.set_text(lv.SYMBOL.AUDIO)
        self.desc_icon.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_icon.set_style_text_font(lv.font_montserrat_28, 0)
        except:
            pass
        self.desc_icon.align(lv.ALIGN.TOP_MID, 0, 10)

        # Description title
        self.desc_title = lv.label(self.desc_panel)
        self.desc_title.set_text("")
        self.desc_title.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_title.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass
        self.desc_title.set_width(180)
        try:
            self.desc_title.set_style_text_font(lv.font_montserrat_12, 0)
        except:
            pass
        self.desc_title.align(lv.ALIGN.TOP_MID, 0, 50)

        # Description text
        self.desc_text = lv.label(self.desc_panel)
        self.desc_text.set_text("Select a song to play")
        self.desc_text.set_style_text_color(lv.color_black(), 0)
        try:
            self.desc_text.set_long_mode(lv.LABEL_LONG.WRAP)
        except:
            pass
        self.desc_text.set_width(180)
        try:
            self.desc_text.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass
        self.desc_text.align(lv.ALIGN.TOP_MID, 0, 80)

        # Status Label
        self.status = lv.label(self.screen)
        self.status.set_text("UP/DN: Select | ENTER: Play | ESC: Exit")
        self.status.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        self.status.set_style_text_color(lv.color_black(), 0)
        try:
            self.status.set_style_text_font(lv.font_montserrat_10, 0)
        except:
            pass

        self.render_list()

    def render_list(self):
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.set_editing(False)

        first_btn = None
        for i, song in enumerate(self.songs):
            btn = lv.button(self.cont)
            btn.set_size(170, 32)  # Fit to container width
            btn.align(lv.ALIGN.LEFT_MID, 0, 0)

            # Apply styles
            btn.add_style(self.style_btn_rel, 0)
            btn.add_style(self.style_btn_foc, lv.STATE.FOCUSED)

            lbl = lv.label(btn)
            lbl.set_text(song["title"])
            lbl.center()  # Centered within button

            # Events
            btn.add_event_cb(lambda e, id=i: self.on_btn_click(id), lv.EVENT.CLICKED, None)
            btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            btn.add_event_cb(lambda e, id=i: self.on_focus(e, id), lv.EVENT.FOCUSED, None)

            if input.driver and input.driver.group:
                input.driver.group.add_obj(btn)
                if not first_btn:
                    first_btn = btn

        if first_btn:
            lv.group_focus_obj(first_btn)
            # Update arrows and description for initial state
            self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            if len(self.songs) > 1:
                self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            # Update description for first song
            self.update_description(0)
            lv.refr_now(None)

    def on_btn_click(self, idx):
        if self.playing: self.stop_song()
        else: self.play_song(idx)

    def on_focus(self, e, idx):
        try:
            # Check if objects are still valid
            if not self.screen or not self.up_arrow or not self.down_arrow:
                return

            # Update arrows
            if idx == 0:
                self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.up_arrow.remove_flag(lv.obj.FLAG.HIDDEN)

            if idx == len(self.songs) - 1:
                self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)

            # Update description panel
            self.update_description(idx)

            lv.refr_now(None)
        except Exception as ex:
            pass  # Silently ignore if objects were deleted

    def update_description(self, idx):
        try:
            if not self.screen or not self.desc_icon or not self.desc_title or not self.desc_text:
                return
            song = self.songs[idx]
            self.desc_icon.set_text(song["icon"])
            self.desc_title.set_text(song["title"])
            self.desc_text.set_text(song["desc"])
        except Exception as ex:
            pass  # Silently ignore if objects were deleted

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            if self.playing: self.stop_song()
            else:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()
        elif key == lv.KEY.UP:
            import input
            if input.driver and input.driver.group:
                input.driver.group.focus_prev()
                lv.refr_now(None)
        elif key == lv.KEY.DOWN:
            import input
            if input.driver and input.driver.group:
                input.driver.group.focus_next()
                lv.refr_now(None)

    def play_song(self, idx):
        self.stop_song()
        self.playing = True
        song = self.songs[idx]
        self.current_song_notes = song["notes"]
        self.note_idx = 0
        self.status.set_text(f"PLAYING... | ESC: Stop")
        # Using a slightly slower timer for E-ink stability
        self.song_timer = lv.timer_create(self.next_note_cb, 60, None)

    def next_note_cb(self, tmr):
        sound.stop_tone()
        if not self.playing:
            tmr.delete()
            return

        if self.note_idx < len(self.current_song_notes):
            freq, dur = self.current_song_notes[self.note_idx]
            if freq != 0:  # 0 = REST
                sound.start_tone(freq)
            tmr.set_period(dur + 10)
            self.note_idx += 1
        else:
            self.stop_song()

    def stop_song(self):
        self.playing = False
        sound.stop_tone()
        if self.song_timer:
            self.song_timer.delete()
            self.song_timer = None
        self.status.set_text("UP/DN: Select | ENTER: Play | ESC: Exit")

    def exit(self):
        self.stop_song()
        if self.screen:
            self.screen.delete()
            self.screen = None
