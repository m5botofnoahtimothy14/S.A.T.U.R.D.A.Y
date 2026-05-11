import serial
import time
import sys

print('Uploading firmware to M5Stack...')
ser = serial.Serial('COM4', 115200, timeout=3)
time.sleep(2)

ser.write(b'\x03')
time.sleep(0.5)
ser.write(b'\x04')
time.sleep(2)

if ser.in_waiting:
    ser.read(ser.in_waiting)

with open('homebot/M5STACK_SATURDAY/main.py', 'r') as f:
    lines = f.readlines()

print(f'Lines: {len(lines)}')

ser.write(b'import os\r\n')
time.sleep(0.3)
ser.write(b'try: os.remove("main.py")\r\n')
time.sleep(0.2)
ser.write(b'except: pass\r\n')
time.sleep(0.2)

ser.write(b'f=open("main.py","w")\r\n')
time.sleep(0.5)

errors = 0
for i, line in enumerate(lines):
    line = line.rstrip()
    
    escaped = line.replace('\\', '\\\\').replace('"', '\\"')
    
    cmd = f'f.write("{escaped}\\n")'
    ser.write((cmd + '\r\n').encode())
    time.sleep(0.03)
    
    if i % 50 == 0:
        print(f'{i}/{len(lines)}')
    
    if ser.in_waiting:
        resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        if 'Error' in resp or 'Traceback' in resp:
            errors += 1
            if errors < 5:
                print(f'Error at {i}: {resp[:80]}')

ser.write(b'f.close()\r\n')
time.sleep(0.5)

ser.write(b'import os\r\n')
time.sleep(0.3)
ser.write(b's=os.stat("main.py")\r\n')
time.sleep(0.3)
ser.write(b'print("SIZE:",s[6])\r\n')
time.sleep(1)

if ser.in_waiting:
    resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print('File size:', resp.strip())

ser.write(b'\x04\r\n')
time.sleep(2)

ser.close()
print('Upload complete!')
