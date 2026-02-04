"""Sound driver using Linux input events for system beeper.

Provides tone generation through /dev/input/event6 using EV_SND events.
"""

import struct
import time
import os

EV_SYN = 0x00
EV_SND = 0x12
SND_TONE = 0x02

class SoundDriver:
    """Driver for PC speaker-style beeper via Linux input events.

    Sends EV_SND/SND_TONE events to /dev/input/event6 for tone generation.
    """
    def __init__(self):
        """Initialize sound driver and open beeper device."""
        import config
        self.enabled = config.sound_enabled
        self.fd = None
        self.dev_path = "/dev/input/event6"
        self.init_device()

    def init_device(self):
        """Open the beeper device file for writing."""
        try:
            # Open for writing in binary mode
            if self.fd: self.fd.close()
            self.fd = open(self.dev_path, "wb")
        except Exception as e:
            print(f"Sound init failed: {e}")
            self.fd = None

    def beep(self, duration_ms=20, freq=1000):
        """Play a short beep tone.

        Args:
            duration_ms: Tone duration in milliseconds
            freq: Tone frequency in Hz
        """
        if not self.enabled or not self.fd: return
        
        try:
            # Start Tone
            self.send_event(EV_SND, SND_TONE, freq)
            self.send_event(EV_SYN, 0, 0)
            
            time.sleep_ms(duration_ms)
        finally:
            self.stop_tone()

    def start_tone(self, freq):
        """Start a continuous tone.

        Args:
            freq: Tone frequency in Hz
        """
        if not self.enabled or not self.fd: return
        self.send_event(EV_SND, SND_TONE, freq)
        self.send_event(EV_SYN, 0, 0)

    def stop_tone(self):
        """Stop any currently playing tone."""
        if not self.fd: return
        try:
            self.send_event(EV_SND, SND_TONE, 0)
            self.send_event(EV_SYN, 0, 0)
        except: pass

    def send_event(self, type, code, value):
        """Send a Linux input event to the beeper device.

        Args:
            type: Event type (e.g., EV_SND)
            code: Event code (e.g., SND_TONE)
            value: Event value (frequency in Hz, or 0 to stop)
        """
        if not self.fd: return
        # Format for 64-bit aarch64 (24 bytes)
        try:
            data = struct.pack('llHHi', 0, 0, type, code, value)
            self.fd.write(data)
            # Avoid flush() if it causes EINVAL, kernel should handle the write
        except Exception as e:
            raise e

driver = None

def init():
    """Initialize the global sound driver instance.

    Returns:
        SoundDriver instance
    """
    global driver
    if not driver:
        driver = SoundDriver()
    return driver

def beep(duration_ms=20, freq=1000):
    """Play a beep using the global driver.

    Args:
        duration_ms: Tone duration in milliseconds
        freq: Tone frequency in Hz
    """
    if driver:
        driver.beep(duration_ms, freq)

def start_tone(freq):
    """Start a continuous tone using the global driver.

    Args:
        freq: Tone frequency in Hz
    """
    if driver:
        driver.start_tone(freq)

def stop_tone():
    """Stop any currently playing tone using the global driver."""
    if driver:
        driver.stop_tone()
