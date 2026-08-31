"""Monochrome Brick Breaker rendered through the portable Canvas API."""

from __future__ import annotations

import random

from badge_sdk import Action, App, Canvas, InputEvent, RefreshMode, Screen


class BrickBreakerApp(App):
    app_id = "brick-breaker"
    name = "Brick Breaker"
    category = "games"
    description = "Move the paddle, launch the ball, and clear the wall"

    COLS = 20
    ROWS = 15
    PADDLE_WIDTH = 3
    STEP_SECONDS = 0.8

    def __init__(self, *, rng: random.Random | None = None) -> None:
        super().__init__()
        self.rng = rng or random.Random()
        self.score = 0
        self.game_over = False
        self.won = False
        self.waiting = True
        self.paddle_x = self.COLS // 2
        self.ball_x = self.paddle_x
        self.ball_y = self.ROWS - 3
        self.ball_dx = 1
        self.ball_dy = -1
        self.bricks: set[tuple[int, int]] = set()
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
        self.score = 0
        self.game_over = False
        self.won = False
        self.waiting = True
        self.paddle_x = self.COLS // 2
        self.ball_x = self.paddle_x
        self.ball_y = self.ROWS - 3
        self.ball_dx = 1 if self.rng.random() > 0.5 else -1
        self.ball_dy = -1
        self.bricks = {(x, y) for y in range(1, 6) for x in range(1, self.COLS - 1)}
        self.invalidate(RefreshMode.FULL)

    def _beep(self, duration: float, frequency: int) -> None:
        if self.context:
            self.context.run_background(self.context.services.sound.beep, duration, frequency)

    def step(self) -> None:
        if self.game_over:
            return
        if self.waiting:
            self.ball_x = self.paddle_x
            self.ball_y = self.ROWS - 3
            self.invalidate(RefreshMode.PARTIAL)
            return

        next_x = self.ball_x + self.ball_dx
        next_y = self.ball_y + self.ball_dy
        if next_x < 0 or next_x >= self.COLS:
            self.ball_dx = -self.ball_dx
            next_x = self.ball_x + self.ball_dx
            self._beep(0.01, 1200)
        if next_y < 0:
            self.ball_dy = -self.ball_dy
            next_y = self.ball_y + self.ball_dy
            self._beep(0.01, 1200)

        paddle_row = self.ROWS - 2
        paddle_half = self.PADDLE_WIDTH // 2
        if next_y >= paddle_row:
            on_paddle = next_y == paddle_row and self.paddle_x - paddle_half <= next_x <= self.paddle_x + paddle_half
            if on_paddle:
                self.ball_dy = -self.ball_dy
                next_y = self.ball_y + self.ball_dy
                self._beep(0.01, 1000)
            elif next_y > paddle_row:
                self.game_over = True
                self._beep(0.4, 500)
                self.invalidate(RefreshMode.FULL)
                return

        if (next_x, next_y) in self.bricks:
            self.bricks.remove((next_x, next_y))
            self.ball_dy = -self.ball_dy
            next_y = self.ball_y + self.ball_dy
            self.score += 10
            self._beep(0.03, 1800)
            if not self.bricks:
                self.won = True
                self.game_over = True

        self.ball_x = next_x
        self.ball_y = next_y
        self.invalidate(RefreshMode.FULL if self.game_over else RefreshMode.PARTIAL)

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.LEFT:
            if self.paddle_x > self.PADDLE_WIDTH // 2:
                self.paddle_x -= 1
        elif event.action == Action.RIGHT:
            if self.paddle_x < self.COLS - 1 - self.PADDLE_WIDTH // 2:
                self.paddle_x += 1
        elif event.action == Action.SELECT:
            if self.game_over:
                self.reset()
            else:
                self.waiting = False
        elif event.action == Action.UP and self.game_over:
            self.reset()
        elif event.action == Action.BACK:
            self.close()
            return True
        else:
            return False
        if self.waiting and not self.game_over:
            self.ball_x = self.paddle_x
        self.invalidate(RefreshMode.PARTIAL)
        return True

    def _draw(self, draw, bounds: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = bounds
        cell = max(1, min((x1 - x0) // self.COLS, (y1 - y0) // self.ROWS))
        board_w, board_h = cell * self.COLS, cell * self.ROWS
        left = x0 + ((x1 - x0) - board_w) // 2
        top = y0 + ((y1 - y0) - board_h) // 2
        draw.rectangle((left, top, left + board_w - 1, top + board_h - 1), outline=0, width=1)

        def cell_bounds(x: int, y: int, inset: int = 2) -> tuple[int, int, int, int]:
            return (
                left + x * cell + inset,
                top + y * cell + inset,
                left + (x + 1) * cell - inset - 1,
                top + (y + 1) * cell - inset - 1,
            )

        for brick_x, brick_y in self.bricks:
            draw.rectangle(cell_bounds(brick_x, brick_y, 1), fill=0)
        paddle_y = self.ROWS - 2
        for offset in range(-(self.PADDLE_WIDTH // 2), self.PADDLE_WIDTH // 2 + 1):
            draw.rectangle(cell_bounds(self.paddle_x + offset, paddle_y, 1), fill=0)
        draw.ellipse(cell_bounds(self.ball_x, self.ball_y, 3), fill=0)
        draw.rectangle((left + board_w - 85, top + 2, left + board_w - 2, top + 20), fill=255)
        draw.text((left + board_w - 80, top + 5), f"Score: {self.score}", fill=0)
        if self.waiting and not self.game_over:
            draw.text((left + max(4, board_w // 2 - 48), top + board_h // 2), "SELECT to launch", fill=0)
        if self.game_over:
            width, height = min(260, board_w - 20), 78
            bx = left + (board_w - width) // 2
            by = top + (board_h - height) // 2
            draw.rectangle((bx, by, bx + width, by + height), fill=255, outline=0, width=2)
            message = "YOU WIN" if self.won else "GAME OVER"
            draw.text((bx + max(10, width // 2 - 35), by + 18), message, fill=0)
            draw.text((bx + max(10, width // 2 - 55), by + 45), "SELECT to restart", fill=0)

    def view(self) -> Screen:
        return Screen(Canvas(self._draw, key="brick-canvas"))
