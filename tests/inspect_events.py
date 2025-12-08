import sys
import os

dev = "/dev/input/event0"
print(f"Reading from {dev}. Press a key...")

with open(dev, "rb") as f:
    while True:
        data = f.read(24) # Expect 24 bytes
        if not data: break
        
        # Print hex bytes
        hex_data = " ".join([f"{b:02x}" for b in data])
        print(f"Event ({len(data)} bytes): {hex_data}")
        
        # Stop after a few
        break
