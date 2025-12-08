import sys
sys.path.append('drivers')
sys.path.append('lib')
import lvgl as lv
import display
import input
import time

def main():
    lv.init()
    display.init()
    input_drv = input.init()
    
    scr = lv.screen_active()
    scr.set_style_bg_color(lv.color_white(), 0)
    scr.set_style_bg_opa(lv.OPA.COVER, 0)
    
    # Create Group
    g = input_drv.group or lv.group_create()
    g.remove_all_objs()
    g.set_default()
    
    # Create Buttons
    cont = lv.obj(scr)
    cont.set_size(200, 200)
    cont.center()
    cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    
    btns = []
    for i in range(3):
        btn = lv.button(cont)
        btn.set_width(lv.pct(100))
        label = lv.label(btn)
        label.set_text(f"Button {i}")
        g.add_obj(btn)
        
        # Style for focus
        style = lv.style_t()
        style.init()
        style.set_bg_color(lv.palette_main(lv.PALETTE.BLUE))
        btn.add_style(style, lv.STATE.FOCUSED)
        
        btns.append(btn)
        
        # Event
        def cb(e, idx=i):
            code = e.get_code()
            if code == lv.EVENT.KEY:
                k = e.get_key()
                print(f"Btn {idx} Key: {k}")
            elif code == lv.EVENT.CLICKED:
                print(f"Btn {idx} CLICKED")
            elif code == lv.EVENT.FOCUSED:
                print(f"Btn {idx} FOCUSED")
                
        btn.add_event_cb(cb, lv.EVENT.ALL, None)
        
    lv.group_focus_obj(btns[0])
    
    print("Running debug_nav.py. Press Up/Down. Ctrl+C to exit.")
    
    try:
        while True:
            lv.task_handler()
            time.sleep(0.01)
    finally:
        pass

if __name__ == "__main__":
    main()
