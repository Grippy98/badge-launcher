import struct
import sys
import os

dev_path = "/dev/input/event0"

try:
    f = open(dev_path, "rb")
    print(f"Listening on {dev_path}... Press keys (Ctrl+C to exit)")
    
    while True:
        data = f.read(24)
        if not data or len(data) < 24:
            continue
            
        sec, usec, type, code, value = struct.unpack('llHHi', data)
        
        if type == 1 and value == 1: # Key Press
            print(f"Key Pressed: Code={code}")

except Exception as e:
    print(f"Error: {e}")
