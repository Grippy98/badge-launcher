import struct
import time

def stop():
    try:
        # Try both 16 and 24 byte formats
        for fmt in ['llHHi', 'qqHHi']:
            try:
                with open('/dev/input/event6', 'wb') as f:
                    # Type=0x12 (EV_SND), Code=0x02 (SND_TONE), Value=0
                    data = struct.pack(fmt, 0, 0, 0x12, 0x02, 0)
                    f.write(data)
                    f.flush()
                print(f"Sent stop with format {fmt}")
            except Exception as e:
                print(f"Failed {fmt}: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    stop()
