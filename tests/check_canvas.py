import lvgl as lv
lv.init()
try:
    c = lv.canvas(lv.obj())
    print("Canvas: OK")
except Exception as e:
    print(f"Canvas: FAIL {e}")
