import struct
for fmt in ['llHHi', 'qqHHi', 'LLHHi', 'i i H H i', 'q q H H i']:
    try:
        data = struct.pack(fmt, 0, 0, 0, 0, 0)
        print(f"{fmt} size: {len(data)}")
    except:
        print(f"{fmt} not supported")
