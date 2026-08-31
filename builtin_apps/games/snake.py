"""Monochrome Snake rendered through the portable Canvas component."""

from __future__ import annotations

import random

from badge_sdk import Action, App, Canvas, InputEvent, RefreshMode, Screen


class SnakeApp(App):
    app_id = "snake"
    name = "Snake"
    category = "games"
    description = "Eat food, grow, and avoid colliding with yourself"

    COLS = 20
    ROWS = 15
    STEP_SECONDS = 1.0
    DIRECTIONS = {
        Action.UP: (0, -1),
        Action.DOWN: (0, 1),
        Action.LEFT: (-1, 0),
        Action.RIGHT: (1, 0),
    }

    def __init__(self, *, rng: random.Random | None = None) -> None:
        super().__init__()
        self.rng = rng or random.Random()
        self.snake: list[tuple[int, int]] = []
        self.food = (0, 0)
        self.direction = (0, -1)
        self.next_direction = (0, -1)
        self.score = 0
        self.game_over = False
        self.won = False
        self.timer = None
        self.reset()

    def on_start(self) -> None:
        if self.context:
            self.timer = self.context.call_every(self.STEP_SECONDS, self.step)

    def on_stop(self) -> None:
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def reset(self) -> None:
        center_x = self.COLS // 2
        center_y = self.ROWS // 2
        self.snake = [(center_x, center_y), (center_x, center_y + 1), (center_x, center_y + 2)]
        self.direction = (0, -1)
        self.next_direction = (0, -1)
        self.score = 0
        self.game_over = False
        self.won = False
        self._spawn_food()
        self.invalidate(RefreshMode.FULL)

    def _spawn_food(self) -> None:
        free = [(x, y) for y in range(self.ROWS) for x in range(self.COLS) if (x, y) not in self.snake]
        if not free:
            self.won = True
            self.game_over = True
            return
        self.food = free[self.rng.randrange(len(free))]

    def _beep(self, duration: float, frequency: int) -> None:
        if self.context:
            self.context.run_background(self.context.services.sound.beep, duration, frequency)

    def step(self) -> None:
        if self.game_over:
            return
        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = ((head_x + dx) % self.COLS, (head_y + dy) % self.ROWS)
        if new_head in self.snake[:-1]:
            self.game_over = True
            self._beep(0.4, 300)
            self.invalidate(RefreshMode.FULL)
            return
        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 10
            self._spawn_food()
            self._beep(0.05, 2000)
        else:
            self.snake.pop()
        self.invalidate(RefreshMode.PARTIAL)

    def handle(self, event: InputEvent) -> bool:
        if event.action in self.DIRECTIONS:
            proposed = self.DIRECTIONS[event.action]
            if proposed != (-self.next_direction[0], -self.next_direction[1]):
                self.next_direction = proposed
            return True
        if event.action == Action.SELECT and self.game_over:
            self.reset()
            return True
        if event.action == Action.BACK:
            self.close()
            return True
        return False

    def _draw(self, draw, bounds: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = bounds
        cell = max(1, min((x1 - x0) // self.COLS, (y1 - y0) // self.ROWS))
        board_w, board_h = cell * self.COLS, cell * self.ROWS
        left = x0 + ((x1 - x0) - board_w) // 2
        top = y0 + ((y1 - y0) - board_h) // 2
        draw.rectangle((left, top, left + board_w - 1, top + board_h - 1), outline=0, width=1)

        def cell_bounds(point: tuple[int, int], inset: int = 2) -> tuple[int, int, int, int]:
            px, py = point
            return (
                left + px * cell + inset,
                top + py * cell + inset,
                left + (px + 1) * cell - inset - 1,
                top + (py + 1) * cell - inset - 1,
            )

        for index, point in enumerate(self.snake):
            draw.rectangle(cell_bounds(point, 1 if index == 0 else 2), fill=0)
        draw.ellipse(cell_bounds(self.food, 3), fill=0)
        draw.rectangle((left + 2, top + 2, left + 78, top + 20), fill=255)
        draw.text((left + 5, top + 5), f"Score: {self.score}", fill=0)
        if self.game_over:
            width, height = min(260, board_w - 20), 78
            bx = left + (board_w - width) // 2
            by = top + (board_h - height) // 2
            draw.rectangle((bx, by, bx + width, by + height), fill=255, outline=0, width=2)
            message = "YOU WIN" if self.won else "GAME OVER"
            draw.text((bx + max(10, width // 2 - 35), by + 18), message, fill=0)
            draw.text((bx + max(10, width // 2 - 55), by + 45), "SELECT to restart", fill=0)

    def view(self) -> Screen:
        return Screen(Canvas(self._draw, key="snake-canvas"))
