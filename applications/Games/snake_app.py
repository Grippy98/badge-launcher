import lvgl as lv
import app
import random
import time

class SnakeApp(app.App):
    def __init__(self):
        super().__init__("Snake")
        self.screen = None
        self.game_cont = None
        self.score_label = None
        self.game_over_label = None
        self.paused_label = None
        
        # Grid settings
        self.BLOCK_SIZE = 20
        self.cols = 0
        self.rows = 0
        self.grid_objs = [] # List of lists
        
        # Game State
        self.snake = []
        self.snake_len = 3
        self.food = None
        self.direction = 0 # 0:Up, 1:Down, 2:Left, 3:Right
        self.next_dir = 0
        self.game_over = False
        self.paused = False
        self.score = 0
        self.timer = None
        
    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        lv.screen_load(self.screen)
        
        # Input Isolation
        import input
        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)
            input.driver.group.set_editing(True) # Force keys to widget
        
        # self.screen.add_event_cb(self.on_key, lv.EVENT.KEY, None) # Removed
        
        # Determine Grid Size
        disp = lv.display_get_default()
        width = disp.get_horizontal_resolution()
        height = disp.get_vertical_resolution()
        
        self.cols = width // self.BLOCK_SIZE
        self.rows = height // self.BLOCK_SIZE
        
        # Init Objects (Lazy or full? Full grid is safer for updates)
        # However, creating 480/20 * 320/20 = 24 * 16 = 384 objects is fine.
        # But if res is higher (800x480), objects count grows.
        # Let's try dynamic sprites (moving objects) instead of static grid for Python performance?
        # Static grid requires looping all 384 objects to clear them.
        # Moving objects simply updates pos.
        # BUT C code used static grid. Let's try dynamic for Python efficiency.
        # Wait, clearing static grid is O(N) where N=GridSize.
        # Moving objects: O(SnakeLen). SnakeLen < GridSize usually.
        # Dynamic is better for Python (less calls to C-bind).
        
        # Container
        self.game_cont = lv.obj(self.screen)
        self.game_cont.set_size(width, height)
        self.game_cont.set_style_bg_opa(lv.OPA.TRANSP, 0)
        self.game_cont.set_style_border_width(0, 0)
        self.game_cont.center()
        
        # Labels
        self.score_label = lv.label(self.screen)
        self.score_label.set_text("Score: 0")
        self.score_label.set_style_text_color(lv.color_black(), 0)
        self.score_label.align(lv.ALIGN.TOP_LEFT, 5, 5)
        
        self.game_over_label = lv.label(self.screen)
        self.game_over_label.set_text("GAME OVER\nPress ENTER to Restart")
        self.game_over_label.set_style_text_color(lv.color_black(), 0)
        self.game_over_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.game_over_label.center()
        self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)
        
        self.reset_game()
        
        self.reset_game()
        
        self.last_tick = time.ticks_ms()
        # Timer (Fast for input polling)
        self.timer = lv.timer_create(self.game_loop, 50, None)

    def reset_game(self):
        # Clear existing snake visuals if any
        self.game_cont.clean()
        
        self.snake = []
        center_x = self.cols // 2
        center_y = self.rows // 2
        self.snake.append((center_x, center_y))
        self.snake.append((center_x, center_y + 1))
        self.snake.append((center_x, center_y + 2))
        
        self.direction = 0 # UP
        self.next_dir = 0
        self.game_over = False
        self.score = 0
        if self.score_label:
            self.score_label.set_text(f"Score: {self.score}")
        if self.game_over_label:
            self.game_over_label.add_flag(lv.obj.FLAG.HIDDEN)
            
        self.snake_objs = [] # List of lv.obj
        for _ in self.snake:
            obj = self.create_block(lv.color_black())
            self.snake_objs.append(obj)
            
        self.food_obj = self.create_block(lv.color_black())
        self.spawn_food()
        self.render()

    def create_block(self, color):
        obj = lv.obj(self.game_cont)
        obj.set_size(self.BLOCK_SIZE - 2, self.BLOCK_SIZE - 2) # padding
        obj.set_style_bg_color(color, 0)
        obj.set_style_radius(0, 0)
        obj.set_style_border_width(0, 0)
        return obj

    def spawn_food(self):
        while True:
            fx = random.randint(0, self.cols - 1)
            fy = random.randint(0, self.rows - 1)
            if (fx, fy) not in self.snake:
                self.food = (fx, fy)
                break
        # Position updated in render

    def poll_input(self):
        import input
        if not input.driver: return
        
        key = input.driver.last_key
        state = input.driver.state
        
        if state == lv.INDEV_STATE.PRESSED:
            print(f"Poll: {key}")
            # Directions
        if state == lv.INDEV_STATE.PRESSED:
            # Directions
            # Handle standard UP/DOWN and legacy PREV(11)/NEXT(9) maps
            if (key == lv.KEY.UP or key == 11) and self.direction != 1:
                self.next_dir = 0
            elif (key == lv.KEY.DOWN or key == 9) and self.direction != 0:
                self.next_dir = 1
            elif (key == lv.KEY.LEFT or key == 20) and self.direction != 3:
                self.next_dir = 2
            elif (key == lv.KEY.RIGHT or key == 19) and self.direction != 2:
                self.next_dir = 3
            elif key == lv.KEY.ENTER and self.game_over:
                self.reset_game()
            elif key == lv.KEY.ESC:
                self.exit()
                if self.on_exit_cb: self.on_exit_cb()

    def game_loop(self, t):
        self.poll_input()
        if not self.screen: return # Check if exited
        
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_tick) < 1000:
            return
        self.last_tick = now
        
        if self.game_over or self.paused:
            return
            
        self.direction = self.next_dir
        
        head_x, head_y = self.snake[0]
        
        if self.direction == 0: head_y -= 1
        elif self.direction == 1: head_y += 1
        elif self.direction == 2: head_x -= 1
        elif self.direction == 3: head_x += 1
        
        # Wrap
        if head_x < 0: head_x = self.cols - 1
        elif head_x >= self.cols: head_x = 0
        if head_y < 0: head_y = self.rows - 1
        elif head_y >= self.rows: head_y = 0
        
        # Collision
        if (head_x, head_y) in self.snake[:-1]: # Ignore tail which moves
            self.game_over = True
            self.game_over_label.remove_flag(lv.obj.FLAG.HIDDEN)
            import sound
            sound.beep(400, 300) # Game Over
            return
            
        new_head = (head_x, head_y)
        self.snake.insert(0, new_head)
        
        # Eat Food
        if new_head == self.food:
            self.score += 10
            self.score_label.set_text(f"Score: {self.score}")
            # Grow: don't pop tail
            # Add visual block
            self.snake_objs.append(self.create_block(lv.color_black()))
            self.spawn_food()
            import sound
            sound.beep(50, 2000) # Eat food
        else:
            self.snake.pop()
            
        self.render()

    def render(self):
        # Update Snake Positions
        for i, pos in enumerate(self.snake):
            if i < len(self.snake_objs):
                x, y = pos
                self.snake_objs[i].set_pos(x * self.BLOCK_SIZE + 1, y * self.BLOCK_SIZE + 1)
        
        # Food
        fx, fy = self.food
        self.food_obj.set_pos(fx * self.BLOCK_SIZE + 1, fy * self.BLOCK_SIZE + 1)

    def exit(self):
        if self.timer:
            self.timer.delete()
            self.timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None
