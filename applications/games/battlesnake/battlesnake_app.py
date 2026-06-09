"""Battlesnake front-end for the Badge Launcher.

This UI renders a host-published JSON state snapshot and sends simple control
commands back to the host simulator. That keeps the launcher focused on
presentation while BadgeSnake owns the game loop.
"""

import json
import lvgl as lv
import sys
import time

if "core" not in sys.path:
    sys.path.append("core")

from core import app


class BattlesnakeApp(app.App):
    STATE_PATH = "/tmp/badgesnake/state.json"
    COMMAND_PATH = "/tmp/badgesnake/command.json"
    BOARD_SIZE = 11
    HEADER_HEIGHT = 54
    FOOTER_HEIGHT = 40

    def __init__(self):
        super().__init__("Battlesnake")
        self.screen = None
        self.board_cont = None
        self.status_label = None
        self.turn_label = None
        self.help_label = None
        self.banner_label = None
        self.timer = None
        self.current_key = 0
        self.key_state = lv.INDEV_STATE.RELEASED
        self.cell_size = 20
        self.board_px = 220
        self.board_origin_x = 0
        self.board_origin_y = 0
        self.cell_objs = []
        self.snapshot = None
        self.last_snapshot_raw = ""
        self.command_seq = 0

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        self.screen.set_style_border_width(0, 0)
        self.screen.set_style_pad_all(0, 0)
        self.screen.add_event_cb(self.on_key_event, lv.EVENT.KEY, None)
        lv.screen_load(self.screen)

        self._configure_input_focus()
        self._build_layout()
        self.update_labels()
        self.render_board()
        self.render_banner()

        self.timer = lv.timer_create(self.refresh_loop, 100, None)

    def _configure_input_focus(self):
        import input

        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            input.driver.group.set_editing(True)

    def _build_layout(self):
        disp = lv.display_get_default()
        width = disp.get_horizontal_resolution()
        height = disp.get_vertical_resolution()

        usable_height = height - self.HEADER_HEIGHT - self.FOOTER_HEIGHT
        self.board_px = min(width - 24, usable_height - 8)
        self.cell_size = self.board_px // self.BOARD_SIZE
        self.board_px = self.cell_size * self.BOARD_SIZE
        self.board_origin_x = (width - self.board_px) // 2
        self.board_origin_y = self.HEADER_HEIGHT + ((usable_height - self.board_px) // 2)

        title = lv.label(self.screen)
        title.set_text("BATTLESNAKE")
        title.set_style_text_color(lv.color_black(), 0)
        title.align(lv.ALIGN.TOP_MID, 0, 4)

        self.status_label = lv.label(self.screen)
        self.status_label.set_style_text_color(lv.color_black(), 0)
        self.status_label.align(lv.ALIGN.TOP_LEFT, 8, 22)

        self.turn_label = lv.label(self.screen)
        self.turn_label.set_style_text_color(lv.color_black(), 0)
        self.turn_label.align(lv.ALIGN.TOP_RIGHT, -8, 22)

        self.board_cont = lv.obj(self.screen)
        self.board_cont.set_pos(self.board_origin_x, self.board_origin_y)
        self.board_cont.set_size(self.board_px, self.board_px)
        self.board_cont.set_style_bg_color(lv.color_white(), 0)
        self.board_cont.set_style_border_width(2, 0)
        self.board_cont.set_style_border_color(lv.color_black(), 0)
        self.board_cont.set_style_pad_all(0, 0)
        self.board_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

        self._build_board_cells()

        self.help_label = lv.label(self.screen)
        self.help_label.set_style_text_color(lv.color_black(), 0)
        self.help_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.help_label.set_text("ENTER pause  UP reset  LEFT/RIGHT speed  ESC exit")
        self.help_label.set_width(width - 16)
        self.help_label.align(lv.ALIGN.BOTTOM_MID, 0, -8)

        self.banner_label = lv.label(self.screen)
        self.banner_label.set_style_text_color(lv.color_black(), 0)
        self.banner_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.banner_label.center()
        self.banner_label.add_flag(lv.obj.FLAG.HIDDEN)

    def _build_board_cells(self):
        self.cell_objs = []
        for row in range(self.BOARD_SIZE):
            row_objs = []
            for col in range(self.BOARD_SIZE):
                obj = lv.obj(self.board_cont)
                obj.set_pos(col * self.cell_size, row * self.cell_size)
                obj.set_size(self.cell_size, self.cell_size)
                obj.set_style_radius(0, 0)
                obj.set_style_border_width(1, 0)
                obj.set_style_border_color(lv.color_black(), 0)
                obj.set_style_bg_color(lv.color_white(), 0)
                row_objs.append(obj)
            self.cell_objs.append(row_objs)

    def on_key_event(self, e):
        self.current_key = e.get_key()
        self.key_state = lv.INDEV_STATE.PRESSED

    def poll_input(self):
        import input

        key = self.current_key
        state = self.key_state

        if state != lv.INDEV_STATE.PRESSED and input.driver:
            key = input.driver.last_key
            state = input.driver.state

        if state != lv.INDEV_STATE.PRESSED:
            return

        self.key_state = lv.INDEV_STATE.RELEASED

        if key == lv.KEY.ESC:
            self.exit()
            if self.on_exit_cb:
                self.on_exit_cb()
            return

        if key == lv.KEY.ENTER:
            self.write_command("pause_toggle")
            return

        if key == lv.KEY.UP or key == 11:
            self.write_command("reset")
            return

        if key == lv.KEY.LEFT or key == 20:
            self.write_command("slower")
            return

        if key == lv.KEY.RIGHT or key == 19:
            self.write_command("faster")

    def refresh_loop(self, _timer):
        self.poll_input()
        if not self.screen:
            return

        self.load_snapshot()
        self.update_labels()
        self.render_board()
        self.render_banner()

    def load_snapshot(self):
        try:
            with open(self.STATE_PATH, "r") as handle:
                raw = handle.read()
        except Exception:
            self.snapshot = None
            self.last_snapshot_raw = ""
            return

        if raw == self.last_snapshot_raw:
            return

        try:
            self.snapshot = json.loads(raw)
            self.last_snapshot_raw = raw
        except Exception:
            self.snapshot = None
            self.last_snapshot_raw = ""

    def write_command(self, command):
        self.command_seq += 1
        payload = '{"seq":%d,"command":"%s"}\n' % (self.command_seq, command)
        try:
            with open(self.COMMAND_PATH, "w") as handle:
                handle.write(payload)
        except Exception:
            pass

    def snapshot_snakes(self):
        if not self.snapshot:
            return []
        snakes = self.snapshot.get("snakes", [])
        if snakes:
            return snakes
        return []

    def leading_snake(self):
        snakes = self.snapshot_snakes()
        if not snakes:
            return None

        best = snakes[0]
        for snake in snakes[1:]:
            if snake.get("score", 0) > best.get("score", 0):
                best = snake
                continue
            if snake.get("score", 0) == best.get("score", 0) and snake.get("length", 0) > best.get("length", 0):
                best = snake
        return best

    def foods(self):
        if not self.snapshot:
            return []
        foods = self.snapshot.get("foods", [])
        if foods:
            return foods
        food = self.snapshot.get("food")
        if food:
            return [food]
        return []

    def update_labels(self):
        snakes = self.snapshot_snakes()
        if len(snakes) < 2:
            self.status_label.set_text("Waiting for backend")
            self.turn_label.set_text("BOOT")
            return

        alpha = snakes[0]
        beta = snakes[1]
        lead = self.leading_snake()
        mode = self.snapshot.get("mode", "LIVE")
        turn = self.snapshot.get("turn", 0)
        step_ms = self.snapshot.get("step_ms", 0)
        title = self.snapshot.get("title", "")
        match_number = self.snapshot.get("match_number", 0)

        self.status_label.set_text(
            "%s %s %d/%d/%d\n%s %s %d/%d/%d" % (
                alpha.get("name", "A")[:5],
                alpha.get("archetype", "")[:5],
                alpha.get("health", 0),
                alpha.get("length", 0),
                alpha.get("score", 0),
                beta.get("name", "B")[:5],
                beta.get("archetype", "")[:5],
                beta.get("health", 0),
                beta.get("length", 0),
                beta.get("score", 0),
            )
        )

        lead_name = "?"
        if lead:
            lead_name = lead.get("name", "?")

        self.turn_label.set_text(
            "#%d %s\n%s\nT:%d %0.1fs\nLead:%s" % (
                match_number,
                mode,
                title[:14],
                turn,
                step_ms / 1000.0,
                lead_name,
            )
        )

    def render_board(self):
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                self.cell_objs[row][col].set_style_bg_color(lv.color_white(), 0)

        if not self.snapshot:
            return

        foods = self.foods()
        for food in foods:
            self._paint_cell(food, lv.color_black())

        snakes = self.snapshot_snakes()
        for index in range(len(snakes)):
            snake = snakes[index]
            body = snake.get("body", [])
            for segment_index in range(len(body)):
                segment = body[segment_index]
                if not self._segment_on_board(segment):
                    continue
                if index == 0:
                    color = lv.color_black() if segment_index == 0 else lv.color_make(96, 96, 96)
                else:
                    color = lv.color_make(160, 160, 160) if segment_index == 0 else lv.color_make(208, 208, 208)
                self._paint_cell(segment, color)

    def render_banner(self):
        if not self.snapshot:
            self.banner_label.set_text("Waiting for backend")
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        winner_text = self.snapshot.get("winner_text", "")
        mode = self.snapshot.get("mode", "LIVE")

        if winner_text:
            self.banner_label.set_text(winner_text + "\nUP reset")
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        if mode == "PAUSED":
            self.banner_label.set_text("Paused")
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        event_text = self.snapshot.get("event_text", "")
        if event_text:
            self.banner_label.set_text(event_text[:28])
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        self.banner_label.add_flag(lv.obj.FLAG.HIDDEN)

    def _segment_on_board(self, segment):
        x = segment.get("x", -1)
        y = segment.get("y", -1)
        return x >= 0 and x < self.BOARD_SIZE and y >= 0 and y < self.BOARD_SIZE

    def _paint_cell(self, coord, color):
        x = coord.get("x", -1)
        y = coord.get("y", -1)
        if x < 0 or x >= self.BOARD_SIZE or y < 0 or y >= self.BOARD_SIZE:
            return
        self.cell_objs[y][x].set_style_bg_color(color, 0)

    def exit(self):
        if self.timer:
            try:
                self.timer.delete()
            except Exception:
                pass
            self.timer = None

        if self.screen:
            try:
                self.screen.delete()
            except Exception:
                pass
            self.screen = None
