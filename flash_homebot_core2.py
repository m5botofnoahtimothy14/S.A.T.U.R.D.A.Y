#!/usr/bin/env python3
import serial
import time
import sys
import os
def flash_core2():
    print("[FLASH] Preparing to flash HomeBot Core2 firmware...")
    print("[FLASH] Make sure M5Stack Core2 is connected to COM4")
    try:
        ser = serial.Serial('COM4', 115200, timeout=2)
        ser.close()
        print("✅ COM4 is available")
    except Exception as e:
        print(f"❌ COM4 not available: {e}")
        print("Please check:")
        print("1. M5Stack Core2 connected to COM4")
        print("2. Drivers installed")
        print("3. No other program using COM4")
        return False
    firmware_path = os.path.join(os.path.dirname(__file__), 'homebot', 'AEGIS_Core2_Firmware.py')
    try:
        with open(firmware_path, 'r') as f:
            firmware_code = f.read()
        print(f"✅ Firmware loaded: {len(firmware_code)} bytes")
    except Exception as e:
        print(f"❌ Failed to load firmware: {e}")
        return False
    print("\n[FLASH] Instructions:")
    print("1. Open UiFlow2 Web IDE (https://flow.m5stack.com)")
    print("2. Connect to your M5Stack Core2")
    print("3. Copy the firmware code below:")
    print("=" * 60)
    print(firmware_code)
    print("=" * 60)
    print("\n[FLASH] After flashing:")
    print("1. Core2 will reboot with HomeBot firmware")
    print("2. Face display will show happy emotion")
    print("3. COM4 serial communication active")
    print("4. MQTT connection will attempt")
    print("5. Ready for AEGIS commands")
    input("\nPress Enter after flashing to test connection...")
    try:
        ser = serial.Serial('COM4', 115200, timeout=5)
        print("✅ Connected to flashed Core2")
        ser.write(b"STP\n")
        time.sleep(1)
        if ser.in_waiting:
            response = ser.read(ser.in_waiting).decode()
            print(f"📡 Core2 response: {response}")
        ser.close()
        print("✅ HomeBot Core2 ready!")
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    return True
if __name__ == "__main__":
    flash_core2()
