import struct
import time
import os

EV_SYN = 0x00
EV_SND = 0x12
SND_TONE = 0x02

class SoundDriver:
    def __init__(self):
        import config
        self.enabled = config.sound_enabled
        self.fd = None
        self.dev_path = "/dev/input/event6"
        self.init_device()
        
    def init_device(self):
        try:
            # Open for writing in binary mode
            if self.fd: self.fd.close()
            self.fd = open(self.dev_path, "wb")
        except Exception as e:
            print(f"Sound init failed: {e}")
            self.fd = None
            
    def beep(self, duration_ms=20, freq=1000):
        if not self.enabled or not self.fd: return
        
        try:
            # Start Tone
            self.send_event(EV_SND, SND_TONE, freq)
            self.send_event(EV_SYN, 0, 0)
            
            time.sleep_ms(duration_ms)
        finally:
            self.stop_tone()
            
    def start_tone(self, freq):
        if not self.enabled or not self.fd: return
        self.send_event(EV_SND, SND_TONE, freq)
        self.send_event(EV_SYN, 0, 0)
        
    def stop_tone(self):
        if not self.fd: return
        try:
            self.send_event(EV_SND, SND_TONE, 0)
            self.send_event(EV_SYN, 0, 0)
        except: pass
            
    def send_event(self, type, code, value):
        if not self.fd: return
        # Format for 64-bit aarch64 (24 bytes)
        try:
            data = struct.pack('llHHi', 0, 0, type, code, value)
            self.fd.write(data)
            # Avoid flush() if it causes EINVAL, kernel should handle the write
        except Exception as e:
            # print(f"Send event error: {e}")
            raise e

driver = None

def init():
    global driver
    if not driver:
        driver = SoundDriver()
    return driver

def beep(duration_ms=20, freq=1000):
    if driver:
        driver.beep(duration_ms, freq)

def start_tone(freq):
    if driver:
        driver.start_tone(freq)

def stop_tone():
    if driver:
        driver.stop_tone()

