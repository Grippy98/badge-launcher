"""Brick Breaker game for the Badge Launcher.

Classic breakout-style game where you control a paddle to bounce a ball
and destroy bricks. Use left/right arrows to move, ENTER to launch.
"""

import lvgl as lv
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import random
import time

class BrickApp(app.App):
    def __init__(self):
        super().__init__("Brick Breaker")
        self.screen = None
        self.game_cont = None
        self.score_label = None
        self.game_over_label = None
        
        self.CELL_SIZE = 20
        self.paddle_w = 3 # cells
        
        self.game_over = False
        self.waiting = True
        self.score = 0
        self.timer = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.screen.set_style_pad_all(0, 0)
        self.screen.set_style_border_width(0, 0)
        
        disp = lv.display_get_default()
        self.width = disp.get_horizontal_resolution()
        self.height = disp.get_vertical_resolution()

        self.cols_count = self.width // self.CELL_SIZE
        self.rows_count = self.height // self.CELL_SIZE
        
        self.game_cont = lv.obj(self.screen)
        self.game_cont.set_size(self.width, self.height)
        self.game_cont.set_style_pad_all(0, 0)
        self.game_cont.set_style_border_width(0, 0)
        self.game_cont.align(lv.ALIGN.CENTER, 0, 0)
        
        # Labels
        self.score_label = lv.label(self.screen)
        self.score_label.set_text("Score: 0")
        self.score_label.set_style_text_color(lv.color_black(), 0)
        self.score_label.align(lv.ALIGN.TOP_RIGHT, -5, 5)
        self.score_label.move_foreground() # Ensure on top
        
        self.game_over_label = lv.label(self.screen)
        self.game_over_label.set_text("GAME OVER\nPress UP to Restart")
        self.game_over_label.set_style_text_color(lv.color_black(), 0)
        self.game_over_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.game_over_label.center()
        self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)
        self.game_over_label.move_foreground()

        # Keyboard event support for SDL mode
        self.current_key = 0
        self.key_state = lv.INDEV_STATE.RELEASED
        self.screen.add_event_cb(self.on_key_event, lv.EVENT.KEY, None)

        # Add to input group for keyboard focus
        import input
        if input.driver and input.driver.group:
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.reset_game()

        self.last_tick = time.ticks_ms()
        self.timer = lv.timer_create(self.game_loop, 50, None)

    def reset_game(self):
        self.game_cont.clean()
        
        # Reset State
        self.score = 0
        if self.score_label:
            self.score_label.set_text("Score: 0")
        if self.game_over_label:
            self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)
            
        # Shift Paddle Up (rows - 2)
        self.paddle_x = self.cols_count // 2
        self.ball_x = self.paddle_x
        self.ball_y = self.rows_count - 3 # Ball above paddle
        self.ball_dx = 1 if random.random() > 0.5 else -1
        self.ball_dy = -1
        
        self.waiting = True
        self.game_over = False
        
        # Create Bricks
        self.bricks = []
        for y in range(1, 6): # 5 rows
            for x in range(1, self.cols_count - 1):
                obj = lv.obj(self.game_cont)
                obj.set_size(self.CELL_SIZE - 2, self.CELL_SIZE - 2)
                obj.set_pos(x * self.CELL_SIZE + 1, y * self.CELL_SIZE + 1)
                obj.set_style_bg_color(lv.color_black(), 0)
                obj.set_style_radius(0, 0)
                obj.set_style_border_width(0, 0)
                self.bricks.append({'obj': obj, 'x': x, 'y': y, 'active': True})
                
        # Create Paddle
        self.paddle_objs = []
        for i in range(self.paddle_w):
            obj = lv.obj(self.game_cont)
            obj.set_size(self.CELL_SIZE - 2, self.CELL_SIZE - 2)
            obj.set_style_bg_color(lv.color_black(), 0)
            obj.set_style_radius(0, 0)
            self.paddle_objs.append(obj)
            
        # Create Ball
        self.ball_obj = lv.obj(self.game_cont)
        self.ball_obj.set_size(self.CELL_SIZE - 2, self.CELL_SIZE - 2)
        self.ball_obj.set_style_bg_color(lv.color_black(), 0)
        self.ball_obj.set_style_radius(lv.RADIUS_CIRCLE, 0)
        
        self.render()

    def on_key_event(self, e):
        """Handle LVGL keyboard events (for SDL mode)."""
        key = e.get_key()
        self.current_key = key
        self.key_state = lv.INDEV_STATE.PRESSED

    def poll_input(self):
        import input

        # Try SDL/LVGL keyboard first
        key = self.current_key
        state = self.key_state

        # Fall back to hardware input driver if no SDL key
        if state != lv.INDEV_STATE.PRESSED and input.driver:
            key = input.driver.last_key
            state = input.driver.state

        if state == lv.INDEV_STATE.PRESSED:
            # Reset key state after processing
            self.key_state = lv.INDEV_STATE.RELEASED
            if key == lv.KEY.ESC:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()
            elif key == lv.KEY.UP or key == 11:
                if self.game_over:
                    self.reset_game()
            elif key == lv.KEY.ENTER:
                if self.waiting:
                    self.waiting = False
            elif key == lv.KEY.LEFT or key == 20: # 20 is LeftBtn
                if self.paddle_x > self.paddle_w // 2:
                    self.paddle_x -= 1
            elif key == lv.KEY.RIGHT or key == 19: # 19 is RightBtn
                if self.paddle_x < self.cols_count - 1 - (self.paddle_w // 2):
                    self.paddle_x += 1

    def game_loop(self, t):
        self.poll_input()
        if not self.screen: return
        
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_tick) < 800:
            return
        self.last_tick = now
        
        if self.game_over:
            return
            
        self.render_paddle()
        
        # Ball Logic
        if self.waiting:
            self.ball_x = self.paddle_x
            self.ball_y = self.rows_count - 3
            self.render_ball()
            return
            
        # Move Ball
        nx = self.ball_x + self.ball_dx
        ny = self.ball_y + self.ball_dy
        
        # Walls
        if nx < 0 or nx >= self.cols_count:
            self.ball_dx = -self.ball_dx
            nx = self.ball_x + self.ball_dx 
            import sound
            sound.beep(10, 1200) # Wall hit
            
        if ny < 0:
            self.ball_dy = -self.ball_dy
            ny = self.ball_y + self.ball_dy
            import sound
            sound.beep(10, 1200) # Wall hit
            
        # Paddle/Bottom
        # Check against paddle row 
        paddle_row = self.rows_count - 2
        
        if ny >= paddle_row:
            # Check Paddle
            p_center = self.paddle_x
            offset = self.paddle_w // 2
            
            # Simple check if entered paddle zone
            if (ny == paddle_row) and (nx >= p_center - offset and nx <= p_center + offset):
                self.ball_dy = -self.ball_dy
                ny = self.ball_y + self.ball_dy # bounce up
                import sound
                sound.beep(10, 1000) # Paddle hit
            elif ny > paddle_row: # Missed
                self.game_over = True
                self.game_over_label.remove_flag(lv.obj.FLAG.HIDDEN)
                import sound
                sound.beep(400, 500) # Game Over
                return
        
        # Bricks
        hit_idx = -1
        for i, b in enumerate(self.bricks):
            if b['active'] and b['x'] == nx and b['y'] == ny:
                hit_idx = i
                break
        
        if hit_idx != -1:
            self.bricks[hit_idx]['active'] = False
            self.bricks[hit_idx]['obj'].add_flag(lv.obj.FLAG.HIDDEN)
            self.ball_dy = -self.ball_dy # Simple bounce
            ny = self.ball_y + self.ball_dy
            self.score += 10
            self.score_label.set_text(f"Score: {self.score}")
            import sound
            sound.beep(30, 1800) # Brick hit
            
        self.ball_x = nx
        self.ball_y = ny
        self.render_ball()

    def render(self):
        self.render_paddle()
        self.render_ball()
        
    def render_paddle(self):
        offset = self.paddle_w // 2
        start_x = self.paddle_x - offset
        y = self.rows_count - 2
        for i, obj in enumerate(self.paddle_objs):
            obj.set_pos((start_x + i) * self.CELL_SIZE + 1, y * self.CELL_SIZE + 1)
            
    def render_ball(self):
        self.ball_obj.set_pos(self.ball_x * self.CELL_SIZE + 1, self.ball_y * self.CELL_SIZE + 1)

    def exit(self):
        if self.timer:
            self.timer.delete()
            self.timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None