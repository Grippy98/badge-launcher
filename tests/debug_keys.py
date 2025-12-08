import ustruct, uselect, os, time

def monitor():
    f = None
    try:
        f = open("/dev/input/event0", "rb")
        poll = uselect.poll()
        poll.register(f, uselect.POLLIN)
        print("Monitoring /dev/input/event0 for 10 seconds...")
        
        start = time.time()
        while time.time() - start < 10:
            res = poll.poll(500)
            if res:
                data = f.read(24)
                if len(data) == 24:
                    sec, usec, type, code, value = ustruct.unpack('llHHi', data)
                    if type == 1: # EV_KEY
                        print(f"Key Event: code={code}, value={value}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if f: f.close()

if __name__ == "__main__":
    monitor()
