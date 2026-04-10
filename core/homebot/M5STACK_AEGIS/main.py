                                             
import machine
import time
import network
import math

try:
    import M5
    from M5 import Lcd as lcd
    HAS_M5STACK = True
except:
    try:
        from m5stack import *
        from m5stack_ui import *
        import axp
        HAS_M5STACK = True
    except:
        HAS_M5STACK = False

try:
    from umqtt.simple import MQTTClient
    HAS_MQTT = True
except:
    HAS_MQTT = False

WIFI_SSID = "Timojoe"
WIFI_PASSWORD = "kebajtimo"
AEGIS_MQTT_SERVER = "192.168.0.180"
AEGIS_MQTT_PORT = 1884

BG = 0x000000
AEGIS_BLUE = 0x00AAFF
AEGIS_GREEN = 0x00FF88
AEGIS_ORANGE = 0xFF8800
AEGIS_RED = 0xFF4444
WHITE = 0xFFFFFF
CYAN = 0x00FFFF

MA_PWM, MA_IN1, MA_IN2 = 32, 33, 25
MB_PWM, MB_IN1, MB_IN2 = 26, 27, 14

pwm_a = pwm_b = None
connected_wifi = connected_mqtt = False
direction = "STOP"
mqtt_client = None
wlan = None
anim_frame = 0

def init_display():
    if not HAS_M5STACK: return
    try:
        try:
            M5.begin()
            lcd.setRotation(1)
            lcd.setBrightness(80)
        except: pass
        
        lcd.clear(BG)
        lcd.rect(0, 0, 320, 30, AEGIS_BLUE, BG)
        lcd.setFont(lcd.FONT_DejaVu24)
        lcd.setColor(WHITE)
        lcd.textCenter(160, 5, "AEGIS HOMEBOT")
        lcd.rect(0, 215, 320, 25, AEGIS_BLUE, BG)
        lcd.setFont(lcd.FONT_DejaVu12)
        lcd.setColor(WHITE)
        lcd.textCenter(160, 220, "v4.0 | INITIALIZING...")
    except Exception as e:
        print("Display error:", e)

def update_display(wifi_ok, mqtt_ok, ip=""):
    if not HAS_M5STACK: return
    try:
        lcd.rect(10, 40, 90, 25, AEGIS_GREEN if wifi_ok else AEGIS_RED, BG)
        lcd.setFont(lcd.FONT_DejaVu16)
        lcd.setColor(BG)
        lcd.text(15, 45, "WiFi:" + ("ON" if wifi_ok else "OFF"))
        
        lcd.rect(110, 40, 90, 25, AEGIS_GREEN if mqtt_ok else AEGIS_ORANGE, BG)
        lcd.setColor(BG)
        lcd.text(115, 45, "MQTT:" + ("ON" if mqtt_ok else "OFF"))
        
        lcd.rect(210, 40, 100, 25, BG, BG)
        lcd.setColor(WHITE)
        lcd.setFont(lcd.FONT_DejaVu12)
        if ip: lcd.text(215, 45, ip[:12])
    except: pass

def draw_eye(frame, direction_cmd):
    if not HAS_M5STACK: return
    try:
        x, y, r = 160, 100, 50
        pulse = abs(math.sin(frame * 0.1)) * 5
        
        lcd.circle(x, y, r + 10, BG)
        lcd.circle(x, y, r + 3 + int(pulse), AEGIS_BLUE)
        lcd.circle(x, y, r, AEGIS_BLUE)
        lcd.circle(x, y, r - 10, 0x001133)
        
        if direction_cmd == "FWD": px, py = x, y - 15
        elif direction_cmd == "REV": px, py = x, y + 15
        elif direction_cmd == "LEFT": px, py = x - 15, y
        elif direction_cmd == "RIGHT": px, py = x + 15, y
        elif direction_cmd in ["RTL", "ROTATE_L"]: px, py = x - 20, y
        elif direction_cmd in ["RTR", "ROTATE_R"]: px, py = x + 20, y
        else:
            blink = abs(math.sin(frame * 0.05))
            if blink > 0.95:
                lcd.line(x - 20, y, x + 20, y, AEGIS_BLUE)
                return
            px, py = x, y
        
        lcd.circle(px, py, 15, AEGIS_BLUE)
        lcd.circle(px, py, 8, 0x000011)
        lcd.circle(px - 4, py - 4, 4, WHITE)
        
        if direction_cmd not in ["STOP"]:
            if direction_cmd == "FWD":
                lcd.line(x, y - 80, x - 15, y - 60, AEGIS_GREEN)
                lcd.line(x, y - 80, x + 15, y - 60, AEGIS_GREEN)
            elif direction_cmd == "REV":
                lcd.line(x, y + 80, x - 15, y + 60, AEGIS_RED)
                lcd.line(x, y + 80, x + 15, y + 60, AEGIS_RED)
    except: pass

def show_direction(direction_cmd):
    if not HAS_M5STACK: return
    try:
        lcd.rect(10, 155, 140, 30, BG, BG)
        lcd.setFont(lcd.FONT_DejaVu16)
        if direction_cmd == "STOP": lcd.setColor(AEGIS_RED)
        elif direction_cmd in ["RTL", "RTR"]: lcd.setColor(AEGIS_ORANGE)
        else: lcd.setColor(AEGIS_GREEN)
        lcd.text(15, 160, "DIR: " + direction_cmd)
    except: pass

def show_battery():
    if not HAS_M5STACK: return
    try:
        lcd.rect(160, 155, 150, 30, BG, BG)
        lcd.setFont(lcd.FONT_DejaVu16)
        lcd.setColor(WHITE)
        lcd.text(165, 160, "BAT:")
        try:
            vbat = axp.getBatVoltage()
            bat_pct = int((vbat - 3.0) / 1.2 * 100)
            bat_pct = max(0, min(100, bat_pct))
            color = AEGIS_GREEN if bat_pct > 50 else AEGIS_ORANGE if bat_pct > 20 else AEGIS_RED
            lcd.setColor(color)
            lcd.text(220, 160, str(bat_pct) + "%")
        except:
            lcd.text(220, 160, "---%")
    except: pass

def show_loading():
    if not HAS_M5STACK: return
    try:
        lcd.setFont(lcd.FONT_DejaVu24)
        lcd.setColor(AEGIS_BLUE)
        lcd.textCenter(160, 100, "LOADING...")
        for i in range(3):
            lcd.circle(130 + i * 25, 130, 5, AEGIS_BLUE)
            time.sleep_ms(200)
    except: pass

def init_motors():
    global pwm_a, pwm_b
    machine.Pin(MA_IN1, machine.Pin.OUT)
    machine.Pin(MA_IN2, machine.Pin.OUT)
    machine.Pin(MB_IN1, machine.Pin.OUT)
    machine.Pin(MB_IN2, machine.Pin.OUT)
    pwm_a = machine.PWM(machine.Pin(MA_PWM), freq=1000)
    pwm_b = machine.PWM(machine.Pin(MB_PWM), freq=1000)
    stop_all()
    print("MOTORS OK")

def stop_all():
    global pwm_a, pwm_b, direction
    if pwm_a: pwm_a.duty(0)
    if pwm_b: pwm_b.duty(0)
    machine.Pin(MA_IN1).value(0)
    machine.Pin(MA_IN2).value(0)
    machine.Pin(MB_IN1).value(0)
    machine.Pin(MB_IN2).value(0)
    direction = "STOP"

def move(cmd, speed=800):
    global pwm_a, pwm_b, direction
    if not pwm_a: return
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    if cmd == "FWD":
        machine.Pin(MA_IN1).value(1); machine.Pin(MA_IN2).value(0)
        machine.Pin(MB_IN1).value(1); machine.Pin(MB_IN2).value(0)
        direction = "FWD"
    elif cmd == "REV":
        machine.Pin(MA_IN1).value(0); machine.Pin(MA_IN2).value(1)
        machine.Pin(MB_IN1).value(0); machine.Pin(MB_IN2).value(1)
        direction = "REV"
    elif cmd == "LFT":
        machine.Pin(MA_IN1).value(0); machine.Pin(MA_IN2).value(1)
        machine.Pin(MB_IN1).value(1); machine.Pin(MB_IN2).value(0)
        direction = "LEFT"
    elif cmd == "RGT":
        machine.Pin(MA_IN1).value(1); machine.Pin(MA_IN2).value(0)
        machine.Pin(MB_IN1).value(0); machine.Pin(MB_IN2).value(1)
        direction = "RIGHT"
    elif cmd == "RTL":
        machine.Pin(MA_IN1).value(0); machine.Pin(MA_IN2).value(1)
        machine.Pin(MB_IN1).value(1); machine.Pin(MB_IN2).value(0)
        direction = "RTL"
    elif cmd == "RTR":
        machine.Pin(MA_IN1).value(1); machine.Pin(MA_IN2).value(0)
        machine.Pin(MB_IN1).value(0); machine.Pin(MB_IN2).value(1)
        direction = "RTR"

def wifi_connect():
    global connected_wifi, wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    print("WiFi connecting...")
    for i in range(30):
        if wlan.isconnected():
            connected_wifi = True
            print("WiFi OK:", wlan.ifconfig()[0])
            return wlan
        time.sleep(1)
    connected_wifi = False
    return None

def mqtt_callback(topic, msg):
    global connected_mqtt
    try:
        cmd = msg.decode().strip().upper()
        print("MQTT CMD:", cmd)
        if cmd == "FWD": move("FWD")
        elif cmd == "REV": move("REV")
        elif cmd == "LFT": move("LFT")
        elif cmd == "RGT": move("RGT")
        elif cmd == "RTL": move("RTL")
        elif cmd == "RTR": move("RTR")
        elif cmd == "STP": stop_all()
        elif cmd == "PING": mqtt_pub("PONG")
        elif cmd == "STATUS": mqtt_pub("ONLINE|" + direction)
    except Exception as e:
        print("MQTT error:", e)

def mqtt_connect():
    global mqtt_client, connected_mqtt
    if not HAS_MQTT: return False
    try:
        mqtt_client = MQTTClient("AEGIS_HB", AEGIS_MQTT_SERVER, AEGIS_MQTT_PORT)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe("aegis/homebot/cmd")
        connected_mqtt = True
        print("MQTT OK")
        mqtt_pub("ONLINE")
        return True
    except Exception as e:
        print("MQTT error:", e)
        connected_mqtt = False
        return False

def mqtt_pub(msg):
    global mqtt_client, connected_mqtt
    if connected_mqtt and mqtt_client:
        try:
            mqtt_client.publish("aegis/homebot/status", msg)
        except:
            connected_mqtt = False

def main():
    global connected_wifi, connected_mqtt, direction, anim_frame, wlan
    
    print("=" * 40)
    print("AEGIS HOMEBOT v4.0")
    print("=" * 40)
    
    init_motors()
    init_display()
    show_loading()
    
    wlan = wifi_connect()
    if connected_wifi:
        mqtt_connect()
    
    ip = wlan.ifconfig()[0] if wlan and connected_wifi else ""
    update_display(connected_wifi, connected_mqtt, ip)
    
    print("READY")
    
    uart = machine.UART(2, 115200, tx=17, rx=16)
    uart.init(115200)
    buffer = ""
    
    last_update = time.time()
    last_heartbeat = time.time()
    
    while True:
        now = time.time()
        
        if connected_mqtt and mqtt_client:
            try:
                mqtt_client.check_msg()
            except:
                connected_mqtt = False
        
        if now - last_heartbeat > 30:
            if connected_mqtt:
                mqtt_pub("HEARTBEAT|" + direction)
            last_heartbeat = now
        
        if uart.any():
            data = uart.read()
            if data:
                for b in data:
                    if 32 <= b < 127:
                        c = chr(b)
                        if c == '\n' or c == '\r':
                            if buffer.strip():
                                cmd = buffer.strip().upper()
                                if cmd == "FWD": move("FWD")
                                elif cmd == "REV": move("REV")
                                elif cmd == "LFT": move("LFT")
                                elif cmd == "RGT": move("RGT")
                                elif cmd == "RTL": move("RTL")
                                elif cmd == "RTR": move("RTR")
                                elif cmd == "STP": stop_all()
                                elif cmd == "PING": uart.write("PONG\r\n")
                                elif cmd == "STATUS":
                                    s = "WIFI:" + ("OK" if connected_wifi else "OFF")
                                    s += " MQTT:" + ("OK" if connected_mqtt else "OFF")
                                    s += " " + direction
                                    uart.write((s + "\r\n").encode())
                                else:
                                    uart.write(("UNK:" + cmd + "\r\n").encode())
                                buffer = ""
                        else:
                            buffer += c
        
        if now - last_update > 0.1:
            anim_frame += 1
            draw_eye(anim_frame, direction)
            show_direction(direction)
            show_battery()
            last_update = now
        
        if connected_wifi and not connected_mqtt and (now - last_heartbeat) > 10:
            mqtt_connect()
            last_heartbeat = now
        
        time.sleep_ms(10)

if __name__ == "__main__":
    main()
