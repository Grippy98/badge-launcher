"""Battlesnake front-end for the Badge Launcher.

This first pass keeps the full game loop local to the launcher so it can run
immediately on BeagleBadge. The UI and board model are structured so a later
revision can swap the move-selection logic for a BadgeSnake backend.
"""

import lvgl as lv
import random
import sys
import time

if "core" not in sys.path:
    sys.path.append("core")

from core import app


class BattlesnakeApp(app.App):
    BOARD_SIZE = 11
    HEADER_HEIGHT = 54
    FOOTER_HEIGHT = 40
    DEFAULT_STEP_MS = 900
    MIN_STEP_MS = 250
    MAX_STEP_MS = 1800

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
        self.last_tick = 0
        self.step_ms = self.DEFAULT_STEP_MS
        self.cell_size = 20
        self.board_px = 220
        self.board_origin_x = 0
        self.board_origin_y = 0
        self.cell_objs = []
        self.snakes = []
        self.food = None
        self.turn = 0
        self.paused = False
        self.winner_text = ""

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
        self.reset_match()

        self.last_tick = time.ticks_ms()
        self.timer = lv.timer_create(self.game_loop, 100, None)

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

    def reset_match(self):
        self.turn = 0
        self.paused = False
        self.winner_text = ""
        self.step_ms = self.DEFAULT_STEP_MS
        self.banner_label.add_flag(lv.obj.FLAG.HIDDEN)

        self.snakes = [
            {
                "name": "ALPHA",
                "body": [(2, 5), (1, 5), (0, 5)],
                "dir": (1, 0),
                "health": 100,
                "alive": True,
                "score": 0,
                "bias": [(0, -1), (0, 1)],
            },
            {
                "name": "BETA",
                "body": [(8, 5), (9, 5), (10, 5)],
                "dir": (-1, 0),
                "health": 100,
                "alive": True,
                "score": 0,
                "bias": [(0, 1), (0, -1)],
            },
        ]

        self.spawn_food()
        self.update_labels()
        self.render_board()

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
            self.paused = not self.paused
            self.update_labels()
            self.render_banner()
            return

        if key == lv.KEY.UP or key == 11:
            self.reset_match()
            return

        if key == lv.KEY.LEFT or key == 20:
            self.step_ms = min(self.MAX_STEP_MS, self.step_ms + 150)
            self.update_labels()
            return

        if key == lv.KEY.RIGHT or key == 19:
            self.step_ms = max(self.MIN_STEP_MS, self.step_ms - 150)
            self.update_labels()

    def game_loop(self, _timer):
        self.poll_input()
        if not self.screen:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_tick) < self.step_ms:
            return
        self.last_tick = now

        if self.paused or self.winner_text:
            return

        self.advance_turn()

    def advance_turn(self):
        self.turn += 1
        decisions = []
        occupied = {}
        ate_food = False

        for snake in self.snakes:
            if not snake["alive"]:
                continue
            for segment in snake["body"]:
                occupied[segment] = snake["name"]

        for snake in self.snakes:
            if not snake["alive"]:
                decisions.append(None)
                continue
            decisions.append(self.choose_move(snake, occupied))

        next_heads = []
        for index, snake in enumerate(self.snakes):
            if not snake["alive"]:
                next_heads.append(None)
                continue
            dx, dy = decisions[index]
            head_x, head_y = snake["body"][0]
            next_heads.append((head_x + dx, head_y + dy))

        eliminations = set()
        head_counts = {}

        for head in next_heads:
            if head is None:
                continue
            head_counts[head] = head_counts.get(head, 0) + 1

        for index, snake in enumerate(self.snakes):
            if not snake["alive"]:
                continue

            head = next_heads[index]
            if head_counts.get(head, 0) > 1:
                eliminations.add(index)
                continue

            x, y = head
            if x < 0 or x >= self.BOARD_SIZE or y < 0 or y >= self.BOARD_SIZE:
                eliminations.add(index)
                continue

            occupied_by = occupied.get(head)
            tail = snake["body"][-1]
            if occupied_by and head != tail:
                eliminations.add(index)

        for index, snake in enumerate(self.snakes):
            if not snake["alive"]:
                continue

            if index in eliminations:
                snake["alive"] = False
                continue

            head = next_heads[index]
            snake["body"].insert(0, head)
            snake["dir"] = decisions[index]
            snake["health"] -= 1

            if head == self.food:
                snake["health"] = 100
                snake["score"] += 1
                ate_food = True
                self._beep(40, 1500)
            else:
                snake["body"].pop()

            if snake["health"] <= 0:
                snake["alive"] = False

        if ate_food:
            self.spawn_food()

        self.finish_match_if_needed()
        self.update_labels()
        self.render_board()
        self.render_banner()

    def choose_move(self, snake, occupied):
        head_x, head_y = snake["body"][0]
        current_dir = snake["dir"]
        opposite = (-current_dir[0], -current_dir[1])
        candidates = [
            current_dir,
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1),
        ]

        ranked = []
        for move in candidates:
            if move == opposite:
                continue
            next_pos = (head_x + move[0], head_y + move[1])
            safe = self.is_safe_target(next_pos, occupied, snake)
            distance = self.distance_to_food(next_pos)
            bias_penalty = self.bias_penalty(move, snake["bias"])
            ranked.append((0 if safe else 1, distance, bias_penalty, random.getrandbits(4), move))

        ranked.sort()
        for entry in ranked:
            if entry[0] == 0:
                return entry[4]

        return current_dir

    def is_safe_target(self, pos, occupied, snake):
        x, y = pos
        if x < 0 or x >= self.BOARD_SIZE or y < 0 or y >= self.BOARD_SIZE:
            return False

        occupant = occupied.get(pos)
        if not occupant:
            return True

        return pos == snake["body"][-1]

    def distance_to_food(self, pos):
        return abs(pos[0] - self.food[0]) + abs(pos[1] - self.food[1])

    def bias_penalty(self, move, bias_moves):
        if move == bias_moves[0]:
            return 0
        if move == bias_moves[1]:
            return 1
        return 2

    def spawn_food(self):
        occupied = {}
        for snake in self.snakes:
            if not snake["alive"]:
                continue
            for segment in snake["body"]:
                occupied[segment] = True

        free_cells = []
        for y in range(self.BOARD_SIZE):
            for x in range(self.BOARD_SIZE):
                if (x, y) not in occupied:
                    free_cells.append((x, y))

        if free_cells:
            self.food = free_cells[random.getrandbits(16) % len(free_cells)]
        else:
            self.food = None

    def finish_match_if_needed(self):
        alive = []
        for snake in self.snakes:
            if snake["alive"]:
                alive.append(snake)

        if len(alive) > 1 and self.food is not None:
            return

        if len(alive) == 1:
            self.winner_text = alive[0]["name"] + " wins"
            self._beep(120, 1000)
        elif len(alive) == 0:
            self.winner_text = "Draw"
            self._beep(180, 500)
        else:
            leader = self.leading_snake()
            self.winner_text = leader["name"] + " survives"
            self._beep(120, 1000)

    def leading_snake(self):
        best = self.snakes[0]
        for snake in self.snakes[1:]:
            if snake["score"] > best["score"]:
                best = snake
            elif snake["score"] == best["score"] and len(snake["body"]) > len(best["body"]):
                best = snake
        return best

    def update_labels(self):
        lead = self.leading_snake()
        alpha = self.snakes[0]
        beta = self.snakes[1]
        mode = "PAUSED" if self.paused else "LIVE"
        if self.winner_text:
            mode = "DONE"

        self.status_label.set_text(
            "A H:%d L:%d S:%d\nB H:%d L:%d S:%d" % (
                alpha["health"] if alpha["alive"] else 0,
                len(alpha["body"]),
                alpha["score"],
                beta["health"] if beta["alive"] else 0,
                len(beta["body"]),
                beta["score"],
            )
        )
        self.turn_label.set_text(
            "%s\nT:%d\n%0.1fs\nLead:%s" % (
                mode,
                self.turn,
                self.step_ms / 1000.0,
                lead["name"],
            )
        )

    def render_board(self):
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                self.cell_objs[row][col].set_style_bg_color(lv.color_white(), 0)

        if self.food is not None:
            self._paint_cell(self.food, lv.color_black())

        for index, snake in enumerate(self.snakes):
            if not snake["alive"] and not snake["body"]:
                continue

            for segment_index, segment in enumerate(snake["body"]):
                if not self._segment_on_board(segment):
                    continue
                if index == 0:
                    color = lv.color_black() if segment_index == 0 else lv.color_make(96, 96, 96)
                else:
                    color = lv.color_make(160, 160, 160) if segment_index == 0 else lv.color_make(208, 208, 208)
                self._paint_cell(segment, color)

    def render_banner(self):
        if self.winner_text:
            self.banner_label.set_text(self.winner_text + "\nUP reset")
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        if self.paused:
            self.banner_label.set_text("Paused")
            self.banner_label.remove_flag(lv.obj.FLAG.HIDDEN)
            return

        self.banner_label.add_flag(lv.obj.FLAG.HIDDEN)

    def _segment_on_board(self, segment):
        return 0 <= segment[0] < self.BOARD_SIZE and 0 <= segment[1] < self.BOARD_SIZE

    def _paint_cell(self, coord, color):
        x, y = coord
        self.cell_objs[y][x].set_style_bg_color(color, 0)

    def _beep(self, duration_ms, freq):
        try:
            import sound

            sound.beep(duration_ms, freq)
        except Exception:
            pass

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
