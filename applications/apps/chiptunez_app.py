import lvgl as lv
import app
import time
import config
import sound

# -- Note Definitions --
NOTE_B0 = 31; NOTE_C1 = 33; NOTE_CS1 = 35; NOTE_D1 = 37; NOTE_DS1 = 39; NOTE_E1 = 41; NOTE_F1 = 44; NOTE_FS1 = 46; NOTE_G1 = 49; NOTE_GS1 = 52; NOTE_A1 = 55; NOTE_AS1 = 58; NOTE_B1 = 62; NOTE_C2 = 65; NOTE_CS2 = 69; NOTE_D2 = 73; NOTE_DS2 = 78; NOTE_E2 = 82; NOTE_F2 = 87; NOTE_FS2 = 93; NOTE_G2 = 98; NOTE_GS2 = 104; NOTE_A2 = 110; NOTE_AS2 = 117; NOTE_B2 = 123; NOTE_C3 = 131; NOTE_CS3 = 139; NOTE_D3 = 147; NOTE_DS3 = 156; NOTE_E3 = 165; NOTE_F3 = 175; NOTE_FS3 = 185; NOTE_G3 = 196; NOTE_GS3 = 208; NOTE_A3 = 220; NOTE_AS3 = 233; NOTE_B3 = 247; NOTE_C4 = 262; NOTE_CS4 = 277; NOTE_D4 = 294; NOTE_DS4 = 311; NOTE_E4 = 330; NOTE_F4 = 349; NOTE_FS4 = 370; NOTE_G4 = 392; NOTE_GS4 = 415; NOTE_A4 = 440; NOTE_AS4 = 466; NOTE_B4 = 494; NOTE_C5 = 523; NOTE_CS5 = 554; NOTE_D5 = 587; NOTE_DS5 = 622; NOTE_E5 = 659; NOTE_F5 = 698; NOTE_FS5 = 740; NOTE_G5 = 784; NOTE_GS5 = 831; NOTE_A5 = 880; NOTE_AS5 = 932; NOTE_B5 = 988; NOTE_C6 = 1047; NOTE_CS6 = 1109; NOTE_D6 = 1175; NOTE_DS6 = 1245; NOTE_E6 = 1319; NOTE_F6 = 1397; NOTE_FS6 = 1480; NOTE_G6 = 1568; NOTE_GS6 = 1661; NOTE_A6 = 1760; NOTE_AS6 = 1865; NOTE_B6 = 1976; NOTE_C7 = 2092; NOTE_CS7 = 2217; NOTE_D7 = 2349; NOTE_DS7 = 2489; NOTE_E7 = 2637; NOTE_F7 = 2794; NOTE_FS7 = 2960; NOTE_G7 = 3136; NOTE_GS7 = 3322; NOTE_A7 = 3520; NOTE_AS7 = 3729; NOTE_B7 = 3951; NOTE_C8 = 4186; NOTE_CS8 = 4435; NOTE_D8 = 4698; NOTE_DS8 = 4978; REST = 0

SONG_IMPERIAL = [
    (NOTE_A4, 500), (NOTE_A4, 500), (NOTE_A4, 500), (NOTE_F4, 350), (NOTE_C5, 150), (NOTE_A4, 500), (NOTE_F4, 350), (NOTE_C5, 150), (NOTE_A4, 1000), (NOTE_E5, 500), (NOTE_E5, 500), (NOTE_E5, 500), (NOTE_F5, 350), (NOTE_C5, 150), (NOTE_GS4, 500), (NOTE_F4, 350), (NOTE_C5, 150), (NOTE_A4, 1000), (NOTE_A5, 500), (NOTE_A4, 350), (NOTE_A4, 150), (NOTE_A5, 500), (NOTE_GS5, 250), (NOTE_G5, 250), (NOTE_FS5, 125), (NOTE_F5, 125), (NOTE_FS5, 250), (REST, 250), (NOTE_AS4, 250), (NOTE_DS5, 500), (NOTE_D5, 250), (NOTE_CS5, 250), (NOTE_C5, 125), (NOTE_B4, 125), (NOTE_C5, 250), (REST, 250), (NOTE_F4, 250), (NOTE_GS4, 500), (NOTE_F4, 375), (NOTE_A4, 125), (NOTE_C5, 500), (NOTE_A4, 375), (NOTE_C5, 125), (NOTE_E5, 1000)
]
SONG_MARIO = [
    (NOTE_E5, 150), (NOTE_E5, 150), (REST, 150), (NOTE_E5, 150), (REST, 150), (NOTE_C5, 150), (NOTE_E5, 150), (REST, 150), (NOTE_G5, 150), (REST, 450), (NOTE_G4, 150), (REST, 450),
    (NOTE_C5, 450), (NOTE_G4, 150), (REST, 300), (NOTE_E4, 450), (NOTE_A4, 150), (REST, 150), (NOTE_B4, 150), (REST, 150), (NOTE_AS4, 150), (NOTE_A4, 150), (REST, 150),
    (NOTE_G4, 200), (NOTE_E5, 200), (NOTE_G5, 200), (NOTE_A5, 200), (REST, 100), (NOTE_F5, 150), (NOTE_G5, 150), (REST, 150), (NOTE_E5, 150), (REST, 150), (NOTE_C5, 150), (NOTE_D5, 150), (NOTE_B4, 150), (REST, 300),
    (NOTE_C5, 450), (NOTE_G4, 150), (REST, 300), (NOTE_E4, 450), (NOTE_A4, 150), (REST, 150), (NOTE_B4, 150), (REST, 150), (NOTE_AS4, 150), (NOTE_A4, 150), (REST, 150)
]
SONG_DOOM = [
    (NOTE_E2, 100), (NOTE_E2, 100), (NOTE_E3, 100), (NOTE_E2, 100), (NOTE_E2, 100), (NOTE_D3, 100), (NOTE_E2, 100), (NOTE_E2, 100), (NOTE_C3, 100), (NOTE_E2, 100), (NOTE_E2, 100), (NOTE_AS2, 100), (NOTE_E2, 100), (NOTE_E2, 100), (NOTE_B2, 100), (NOTE_C3, 100)
] * 4
SONG_NOKIA = [
    (NOTE_E5, 150), (NOTE_D5, 150), (NOTE_FS4, 300), (NOTE_GS4, 300), (NOTE_CS5, 150), (NOTE_B4, 150), (NOTE_D4, 300), (NOTE_E4, 300), (NOTE_B4, 150), (NOTE_A4, 150), (NOTE_CS4, 300), (NOTE_E4, 300), (NOTE_A4, 600), (REST, 600)
] * 4
SONG_BIRTHDAY = [
    (NOTE_C4, 250), (NOTE_C4, 250), (NOTE_D4, 500), (NOTE_C4, 500), (NOTE_F4, 500), (NOTE_E4, 1000), (NOTE_C4, 250), (NOTE_C4, 250), (NOTE_D4, 500), (NOTE_C4, 500), (NOTE_G4, 500), (NOTE_F4, 1000), (NOTE_C4, 250), (NOTE_C4, 250), (NOTE_C5, 500), (NOTE_A4, 500), (NOTE_F4, 500), (NOTE_E4, 500), (NOTE_D4, 1000), (NOTE_AS4, 250), (NOTE_AS4, 250), (NOTE_A4, 500), (NOTE_F4, 500), (NOTE_G4, 500), (NOTE_F4, 1000)
]
SONG_GOT = [
    (NOTE_G4, 500), (NOTE_C4, 500), (NOTE_DS4, 250), (NOTE_F4, 250), (NOTE_G4, 500), (NOTE_C4, 500), (NOTE_DS4, 250), (NOTE_F4, 250), (NOTE_D4, 1000), (NOTE_F4, 500), (NOTE_AS3, 500), (NOTE_DS4, 250), (NOTE_D4, 250), (NOTE_F4, 500), (NOTE_AS3, 500), (NOTE_DS4, 250), (NOTE_D4, 250), (NOTE_C4, 1000),
    (NOTE_G4, 500), (NOTE_C4, 500), (NOTE_DS4, 250), (NOTE_F4, 250), (NOTE_G4, 500), (NOTE_C4, 500), (NOTE_DS4, 250), (NOTE_F4, 250), (NOTE_D4, 1000)
]
SONG_MII = [
    (NOTE_FS4, 200), (NOTE_A4, 200), (NOTE_CS5, 200), (NOTE_A4, 200), (NOTE_FS4, 200), (NOTE_D4, 150), (NOTE_D4, 150), (NOTE_D4, 150), (NOTE_CS4, 200), (NOTE_D4, 200), (NOTE_FS4, 200), (NOTE_A4, 200), (NOTE_CS5, 200), (NOTE_A4, 200), (NOTE_FS4, 200), (NOTE_E5, 250), (NOTE_DS5, 250), (NOTE_D5, 250), (NOTE_GS4, 200), (NOTE_CS5, 200), (NOTE_FS4, 200), (NOTE_CS5, 200), (NOTE_GS4, 200), (NOTE_CS5, 200), (NOTE_G4, 200), (NOTE_FS4, 200), (NOTE_E4, 200)
]
SONG_RICK = [
    (NOTE_G4, 200), (NOTE_A4, 200), (NOTE_C5, 200), (NOTE_A4, 200), (NOTE_E5, 400), (NOTE_E5, 400), (NOTE_D5, 600), (REST, 200), (NOTE_G4, 200), (NOTE_A4, 200), (NOTE_C5, 200), (NOTE_A4, 200), (NOTE_D5, 400), (NOTE_D5, 400), (NOTE_C5, 200), (NOTE_B4, 200), (NOTE_A4, 400), (REST, 200), (NOTE_G4, 200), (NOTE_A4, 200), (NOTE_C5, 200), (NOTE_A4, 200), (NOTE_C5, 400), (NOTE_D5, 200), (NOTE_B4, 200), (NOTE_A4, 200), (NOTE_G4, 200), (NOTE_E5, 400),
    (NOTE_G4, 200), (NOTE_A4, 200), (NOTE_C5, 200), (NOTE_A4, 200), (NOTE_E5, 400), (NOTE_E5, 400), (NOTE_D5, 600)
]
SONG_FURELISE = [
    (NOTE_E5, 150), (NOTE_DS5, 150), (NOTE_E5, 150), (NOTE_DS5, 150), (NOTE_E5, 150), (NOTE_B4, 150), (NOTE_D5, 150), (NOTE_C5, 150), (NOTE_A4, 400), (REST, 150), (NOTE_C4, 150), (NOTE_E4, 150), (NOTE_A4, 150), (NOTE_B4, 400), (REST, 150), (NOTE_E4, 150), (NOTE_GS4, 150), (NOTE_B4, 150), (NOTE_C5, 400),
    (NOTE_E4, 150), (NOTE_E5, 150), (NOTE_DS5, 150), (NOTE_E5, 150), (NOTE_DS5, 150), (NOTE_E5, 150), (NOTE_B4, 150), (NOTE_D5, 150), (NOTE_C5, 150), (NOTE_A4, 400)
]

SONGS = [
    {"title": "Imperial March", "notes": SONG_IMPERIAL},
    {"title": "Super Mario", "notes": SONG_MARIO},
    {"title": "Doom E1M1", "notes": SONG_DOOM},
    {"title": "Nokia Tune", "notes": SONG_NOKIA},
    {"title": "Happy Birthday", "notes": SONG_BIRTHDAY},
    {"title": "Game of Thrones", "notes": SONG_GOT},
    {"title": "Mii Channel", "notes": SONG_MII},
    {"title": "Rick Roll", "notes": SONG_RICK},
    {"title": "Fur Elise", "notes": SONG_FURELISE},
]

class ChipTunezApp(app.App):
    def __init__(self):
        super().__init__("ChipTunez")
        self.screen = None
        self.playing = False
        self.song_timer = None
        self.current_song_notes = []
        self.note_idx = 0
        
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
        
        # Up Arrow (Using LV_SYMBOL)
        self.up_arrow = lv.label(self.screen)
        self.up_arrow.set_text(lv.SYMBOL.UP)
        self.up_arrow.align(lv.ALIGN.TOP_MID, 0, 35)
        self.up_arrow.set_style_text_color(lv.color_black(), 0)
        self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
        
        # Viewport for buttons (400x300 screen)
        # 3 items @ 60px = 180px
        self.cont = lv.obj(self.screen)
        self.cont.set_size(360, 180) 
        self.cont.align(lv.ALIGN.CENTER, 0, 0)
        self.cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.cont.set_style_bg_opa(0, 0)
        self.cont.set_style_border_width(0, 0)
        self.cont.set_style_pad_all(0, 0)
        self.cont.set_style_pad_gap(0, 0)
        self.cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        
        # Down Arrow (Using LV_SYMBOL)
        self.down_arrow = lv.label(self.screen)
        self.down_arrow.set_text(lv.SYMBOL.DOWN)
        self.down_arrow.align(lv.ALIGN.BOTTOM_MID, 0, -45)
        self.down_arrow.set_style_text_color(lv.color_black(), 0)
        
        # Status Label
        self.status = lv.label(self.screen)
        self.status.set_text("UP/DOWN to Select | ENTER to Play")
        self.status.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        self.status.set_style_text_color(lv.color_black(), 0)
        
        self.render_list()
        
    def render_list(self):
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.set_editing(False)

        first_btn = None
        for i, song in enumerate(SONGS):
            btn = lv.button(self.cont)
            btn.set_size(lv.pct(100), 60) # High contrast 60px height
            
            # High Contrast E-ink Styling
            btn.set_style_bg_color(lv.color_white(), 0)
            btn.set_style_bg_color(lv.color_black(), lv.STATE.FOCUSED)
            btn.set_style_bg_opa(255, 0)
            btn.set_style_border_width(1, 0)
            btn.set_style_border_color(lv.color_black(), 0)
            btn.set_style_radius(0, 0)
            
            lbl = lv.label(btn)
            lbl.set_text(song["title"])
            lbl.center()
            lbl.set_style_text_color(lv.color_black(), 0)
            lbl.set_style_text_color(lv.color_white(), lv.STATE.FOCUSED)
            
            # Events
            btn.add_event_cb(lambda e, id=i: self.on_btn_click(id), lv.EVENT.CLICKED, None)
            btn.add_event_cb(self.on_key, lv.EVENT.KEY, None)
            btn.add_event_cb(self.on_focus, lv.EVENT.FOCUSED, None)
            btn.add_event_cb(self.on_blur, lv.EVENT.DEFOCUSED, None)
            
            if input.driver and input.driver.group:
                input.driver.group.add_obj(btn)
                if not first_btn:
                    first_btn = btn
        
        if first_btn:
            lv.group_focus_obj(first_btn)

    def on_btn_click(self, idx):
        if self.playing: self.stop_song()
        else: self.play_song(idx)

    def on_focus(self, e):
        try:
            target = e.get_target()
            obj = lv.obj.__cast__(target)
            if not obj: return
            
            # Instant transition
            obj.scroll_to_view(lv.ANIM.OFF)
            
            # FORCE COLOR UPDATES
            obj.set_style_bg_color(lv.color_black(), 0)
            label = lv.label.__cast__(obj.get_child(0))
            if label:
                label.set_style_text_color(lv.color_white(), 0)
                
            # Update Arrow Visibility
            idx = obj.get_index()
            if idx == 0: self.up_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else: self.up_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
            
            if idx == len(SONGS) - 1: self.down_arrow.add_flag(lv.obj.FLAG.HIDDEN)
            else: self.down_arrow.remove_flag(lv.obj.FLAG.HIDDEN)
            
            lv.refr_now(None)
        except:
            pass

    def on_blur(self, e):
        try:
            target = e.get_target()
            obj = lv.obj.__cast__(target)
            if not obj: return
            
            # RESET COLORS
            obj.set_style_bg_color(lv.color_white(), 0)
            label = lv.label.__cast__(obj.get_child(0))
            if label:
                label.set_style_text_color(lv.color_black(), 0)
        except:
            pass

    def on_key(self, e):
        key = e.get_key()
        if key == lv.KEY.ESC:
            if self.playing: self.stop_song()
            else:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()

    def play_song(self, idx):
        self.stop_song()
        self.playing = True
        song = SONGS[idx]
        self.current_song_notes = song["notes"]
        self.note_idx = 0
        self.status.set_text(f"PLAYING: {song['title']}")
        # Using a slightly slower timer for E-ink stability
        self.song_timer = lv.timer_create(self.next_note_cb, 60, None)

    def next_note_cb(self, tmr):
        sound.stop_tone()
        if not self.playing:
            tmr.delete()
            return

        if self.note_idx < len(self.current_song_notes):
            freq, dur = self.current_song_notes[self.note_idx]
            if freq != REST:
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
        self.status.set_text("UP/DOWN to Select | ENTER to Play")

    def exit(self):
        self.stop_song()
        if self.screen:
            self.screen.delete()
            self.screen = None
