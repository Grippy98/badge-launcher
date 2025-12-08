import lvgl as lv
try:
    o = lv.obj()
    print(dir(o))
except Exception as e:
    print(e)
