import os
import struct
import select
import sys

def scan_input():
    devices = []
    # Open all event devices
    try:
        entries = os.listdir("/dev/input")
        for entry in entries:
            if entry.startswith("event"):
                path = "/dev/input/" + entry
                try:
                    f = open(path, "rb")
                    devices.append((f, path))
                    print(f"Opened {path}")
                except:
                    pass
    except Exception as e:
        print(f"Error scanning: {e}")
        return

    if not devices:
        print("No input devices found.")
        return

    print("Press any key on the badge/keyboard...")
    
    poll = select.poll()
    for f, path in devices:
        poll.register(f, select.POLLIN)

    while True:
        try:
            events = poll.poll(1000)
            for fd, event in events:
                if event & select.POLLIN:
                    # Lookup device
                    dev = None
                    try:
                        dev = next((d for d in devices if d[0].fileno() == fd))
                    except StopIteration:
                        pass
                    
                    if dev:
                        dev_f, dev_path = dev
                        data = dev_f.read(24)
                        if data:
                            print(f"Read {len(data)} bytes from {dev_path}: {data}")
                            if len(data) == 24:
                                u = struct.unpack('llHHi', data)
                                print(f"  -> Type: {u[2]}, Code: {u[3]}, Value: {u[4]}")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    scan_input()
