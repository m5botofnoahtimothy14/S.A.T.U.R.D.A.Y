#!/usr/bin/env python3

import serial
import time
import sys

def send_command(ser, cmd, wait=1):
    ser.write((cmd + '\r\n').encode())
    ser.flush()
    time.sleep(wait)
    if ser.in_waiting:
        return ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    return ""

def upload_file(ser, filename, content):
    
    print(f"Uploading {filename}...")
    
    ser.reset_input_buffer()
    
    lines = content.split('\n')
    
    cmd = f'f = open("{filename}", "w")'
    print(send_command(ser, cmd, 0.5))
    
    for line in lines:
                       
        escaped = line.replace('\\', '\\\\').replace('"', '\\"')
        cmd = f'f.write("{escaped}\\n")'
        send_command(ser, cmd, 0.2)
    
    cmd = 'f.close()'
    print(send_command(ser, cmd, 0.5))
    
    print(f"{filename} uploaded!")

def main():
    port = 'COM4'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    filename = 'homebot/firmware/m5stack/main.py'
    if len(sys.argv) > 2:
        filename = sys.argv[2]
    
    print(f"Connecting to M5Stack on {port}...")
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)
        
        if ser.in_waiting:
            boot = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            print("Boot:", boot[:100])
        
        print("\nSoft resetting...")
        ser.write(b'\x04')          
        time.sleep(1)
        
        if ser.in_waiting:
            print("REPL ready:", ser.read(ser.in_waiting).decode('utf-8', errors='ignore')[:100])
        
        print("\nTesting connection...")
        response = send_command(ser, 'print("OK")', 1)
        if 'OK' in response:
            print("Connection successful!")
        else:
            print("Response:", response)
        
        with open(filename, 'r') as f:
            content = f.read()
        
        print(f"\nFile size: {len(content)} bytes")
        
        upload_file(ser, 'main.py', content)
        
        print("\nVerifying upload...")
        send_command(ser, 'import os', 0.5)
        response = send_command(ser, 'os.listdir()', 1)
        print("Files:", response)
        
        print("\nRebooting...")
        ser.write(b'\x04')          
        time.sleep(2)
        
        ser.close()
        print("\nUpload complete!")
        print("M5Stack will run main.py on boot.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
