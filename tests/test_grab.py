import ffi
import uctypes

# Load libc
libc = ffi.open("libc.so.6")

# int ioctl(int fd, unsigned long request, ...);
ioctl = libc.func("i", "ioctl", "iiL")

# EVIOCGRAB for 64-bit Linux (aarch64) seems to be:
# _IOW('E', 0x90, int)
# 'E' is 0x45
# Size of int is 4
# _IOC_WRITE is 1
# _IOC_READ is 2
# _IOC_NONE is 0
# _IOC(dir, type, nr, size)
# dir=1 (write), type=0x45, nr=0x90, size=4
# (1 << 30) | (0x45 << 8) | 0x90 | (4 << 16) ??
#
# Actually, let's verify checking a simpler way or brute force.
# Or better, just try the common value 0x40044590 (32-bit/generic)
# On 64-bit, usually the request size matches data type size? 
# Wait, grab takes separate 'int' argument (1 or 0), it doesn't write to a pointer.
# So access is _IOW.

# Common Values:
# 0x40044590 (EVIOCGRAB)

def try_grab(dev_path):
    print(f"Opening {dev_path}")
    f = open(dev_path, "rb")
    fd = f.fileno()
    
    EVIOCGRAB = 0x40044590
    
    print(f"Attempting grab on fd {fd} with code {EVIOCGRAB:x}")
    try:
        res = ioctl(fd, EVIOCGRAB, 1) # 1 to grab
        print(f"Grab result: {res}")
    except Exception as e:
        print(f"Grab failed: {e}")
    
    f.close()

try:
    try_grab("/dev/input/event1") # Try one device
except Exception as e:
    print(f"Global Error: {e}")
