import time
import os

path_base = "/sys/bus/iio/devices/iio:device2/"
channels = ["in_voltage0_raw", "in_voltage1_raw", "in_voltage2_raw", "in_voltage3_raw"]

print("Time,CH0,CH1,CH2,CH3")
start = time.time()

for i in range(20): # 10 seconds (0.5s interval)
    row = [f"{time.time()-start:.1f}"]
    for ch in channels:
        try:
            with open(path_base + ch, "r") as f:
                row.append(f.read().strip())
        except:
             row.append("0")
    print(",".join(row))
    time.sleep(0.5)
