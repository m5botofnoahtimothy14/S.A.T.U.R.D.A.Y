"""
AEGIS Core2 safe-mode firmware.

Purpose:
- Recover from crash loops.
- Confirm Core2 display + serial + basic hardware init are working.
"""

import time

try:
    import M5
    from M5 import Lcd

    M5.begin()
    Lcd.setRotation(1)
    Lcd.setBrightness(80)
    Lcd.fillScreen(0x000000)
    Lcd.fillCircle(90, 100, 20, 0x00FF7F)
    Lcd.fillCircle(190, 100, 20, 0x00FF7F)
    Lcd.drawLine(120, 160, 160, 160, 0x00FF7F)
    print("[FACE] SAFE face rendered")
except Exception as e:
    print("[FACE] init error:", e)

uart = None

try:
    from machine import ADC, Pin, UART

    motors = {
        "FL": Pin(26, Pin.OUT),
        "FR": Pin(25, Pin.OUT),
        "BL": Pin(32, Pin.OUT),
        "BR": Pin(33, Pin.OUT),
    }
    for p in motors.values():
        p.value(0)

    trig = Pin(23, Pin.OUT)
    echo = Pin(22, Pin.IN)
    vib = ADC(Pin(34))

    uart = UART(2, 115200, timeout=1000)
    print("[HW] motors/sensors/uart initialized")
except Exception as e:
    print("[HW] init error:", e)

print("AEGIS HomeBot SAFE mode ready")

while True:
    try:
        if uart and uart.any():
            raw = uart.read()
            cmd = raw.decode().strip() if raw else ""
            if cmd:
                print("[SERIAL]", cmd)
                if cmd == "PING":
                    uart.write(b"PONG\n")
                elif cmd == "STP":
                    for p in motors.values():
                        p.value(0)
                    uart.write(b"OK\n")
                else:
                    uart.write(b"ACK\n")
        time.sleep_ms(50)
    except Exception as e:
        print("[LOOP] error:", e)
        time.sleep(1)
