try:
    import machine
    print("machine module exists")
    try:
        p = machine.Pin(29, machine.Pin.OUT)
        print("Pin 29 init success")
    except Exception as e:
        print(f"Pin init failed: {e}")
except ImportError:
    print("machine module missin")
