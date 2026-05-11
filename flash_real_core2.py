#!/usr/bin/env python3
import subprocess
import time
import os
import sys
def check_esptool():
    try:
        result = subprocess.run(['python', '-m', 'esptool', '--help'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ esptool found (python -m esptool)")
            return True
    except:
        pass
    try:
        result = subprocess.run(['esptool.py', '--help'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ esptool.py found")
            return True
    except:
        pass
    print("❌ esptool not found")
    print("Install with: pip install esptool")
    return False
def detect_com4():
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        com4_found = any(port.device == 'COM4' for port in ports)
        if com4_found:
            print("✅ COM4 detected")
            return True
        else:
            print("❌ COM4 not found. Available ports:")
            for port in ports:
                print(f"   {port.device} - {port.description}")
            return False
    except ImportError:
        print("❌ pyserial not installed")
        return False
def prepare_firmware():
    firmware_path = os.path.join(os.path.dirname(__file__), 'homebot', 'SATURDAY_Core2_Firmware.py')
    if not os.path.exists(firmware_path):
        print(f"❌ Firmware file not found: {firmware_path}")
        return None
    with open(firmware_path, 'r') as f:
        firmware_code = f.read()
    flash_file = os.path.join(os.path.dirname(__file__), 'homebot_flash.py')
    with open(flash_file, 'w') as f:
        f.write(firmware_code)
    print(f"✅ Firmware prepared: {flash_file}")
    return flash_file
def flash_core2():
    print("🔥 ACTUAL FLASH - HomeBot Core2 Firmware")
    print("=" * 50)
    if not check_esptool():
        return False
    if not detect_com4():
        print("Please connect M5Stack Core2 to COM4")
        return False
    firmware_file = prepare_firmware()
    if not firmware_file:
        return False
    print("\n⚠️  IMPORTANT: Put M5Stack Core2 in BOOT mode")
    print("1. Hold BOOT button")
    print("2. Press RESET button") 
    print("3. Release both buttons")
    print("4. Core2 is now in flash mode")
    input("\nPress Enter when Core2 is in BOOT mode...")
    try:
        print("🔥 Flashing firmware to COM4...")
        print("🧹 Erasing flash...")
        erase_cmd = [
            'python', '-m', 'esptool', 
            '--port', 'COM4',
            '--baud', '115200',
            'erase-flash'
        ]
        subprocess.run(erase_cmd, check=True)
        print("📝 Writing firmware...")
        flash_cmd = [
            'python', '-m', 'esptool',
            '--port', 'COM4', 
            '--baud', '115200',
            'write_flash',
            '--flash_mode', 'dio',
            '--flash_freq', '40m',
            '--flash_size', '16MB',
            '0x1000', firmware_file
        ]
        subprocess.run(flash_cmd, check=True)
        print("✅ Flash successful!")
        print("🔄 Resetting Core2...")
        reset_cmd = [
            'python', '-m', 'esptool',
            '--port', 'COM4',
            'run'
        ]
        subprocess.run(reset_cmd, check=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Flash failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
def verify_flash():
    print("\n🔍 Verifying flash...")
    try:
        import serial
        ser = serial.Serial('COM4', 115200, timeout=5)
        time.sleep(2)                 
        ser.write(b"STP\n")
        time.sleep(1)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode()
            print(f"✅ Core2 response: {response}")
            ser.close()
            return True
        else:
            print("⚠️  No response from Core2")
            ser.close()
            return False
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False
def main():
    print("🚀 ACTUAL HomeBot Core2 Flash Utility")
    print("This will REALLY flash firmware to M5Stack Core2")
    if flash_core2():
        print("\n✅ Flash completed!")
        time.sleep(3)                           
        if verify_flash():
            print("🎉 HomeBot Core2 is LIVE and ready!")
            print("\n📡 Test commands:")
            print("   STP - Stop motors")
            print("   FWD - Move forward") 
            print("   LFT - Turn left")
            print("   RGT - Turn right")
        else:
            print("⚠️  Flash succeeded but verification failed")
    else:
        print("❌ Flash failed!")
if __name__ == "__main__":
    main()
