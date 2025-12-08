import os
print("Testing os.system...")
try:
    ret = os.system("ip -4 addr > ip_out.txt")
    print(f"Ret: {ret}")
    with open("ip_out.txt", "r") as f:
        print(f.read())
except Exception as e:
    print(f"Error: {e}")
