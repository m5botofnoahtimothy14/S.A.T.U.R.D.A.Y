# Manual Flash Instructions for HomeBot Core2

Since automatic flashing failed, here's the manual method:

## 🔥 Manual Flash Steps

### 1. Put M5Stack Core2 in BOOT Mode
- Hold BOOT button (side button)
- Press RESET button (top button)
- Release both buttons
- Core2 is now in flash mode

### 2. Open Command Prompt/Terminal
```bash
# Navigate to SATURDAY directory
cd d:\SATURDAY

# Check COM4 connection
python -m esptool --port COM4 chip_id
```

### 3. Erase Flash
```bash
python -m esptool --port COM4 erase-flash
```

### 4. Flash Firmware
```bash
python -m esptool --port COM4 --baud 115200 write_flash --flash_mode dio --flash_freq 40m --flash_size 16MB 0x1000 homebot\homebot_flash.py
```

### 5. Reset Device
```bash
python -m esptool --port COM4 run
```

## 🔧 Troubleshooting

### If COM4 not found:
```bash
# List all COM ports
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

### If connection fails:
- Check USB cable (use data cable, not charge-only)
- Try different USB port
- Reinstall M5Stack drivers
- Make sure Core2 is in BOOT mode

### Alternative: Use UiFlow2 Web IDE
1. Go to https://flow.m5stack.com
2. Connect to M5Stack Core2
3. Copy the firmware code from `homebot\SATURDAY_Core2_Firmware.py`
4. Paste into UiFlow2 IDE
5. Click "Download" or "Run"

## ✅ Verification

After flashing, test with:
```bash
# Test serial communication
python -c "
import serial, time
ser = serial.Serial('COM4', 115200, timeout=2)
ser.write(b'STP\n')
time.sleep(1)
if ser.in_waiting:
    print('Core2 response:', ser.read(ser.in_waiting).decode())
ser.close()
"
```

## 🎯 Expected Results

After successful flash:
- Core2 screen shows reactive face
- COM4 responds to commands (STP, FWD, LFT, RGT, etc.)
- MQTT connection attempts
- Ready for SATURDAY integration
