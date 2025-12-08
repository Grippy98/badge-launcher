import sys
sys.path.append('drivers')
sys.path.append('lib')
import sound
import time

print("Testing Sound...")
try:
    drv = sound.init()
    print("Driver Init")
    
    for i in range(3):
        print(f"Beep {i}")
        drv.beep(50) # 50ms beep
        time.sleep(0.5)
        
    print("Done")
except Exception as e:
    import sys
    sys.print_exception(e)
