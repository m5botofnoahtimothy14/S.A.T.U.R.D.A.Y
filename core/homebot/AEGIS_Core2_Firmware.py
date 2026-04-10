                                                     
WIFI_SSID = "Timojoe"
WIFI_PASSWORD = "kebajtimo"

SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 1000      

MQTT_BROKER_PRIMARY = "192.168.0.1"
MQTT_PORT_PRIMARY = 1883
MQTT_BROKER_SECONDARY = "192.168.0.180"
MQTT_PORT_SECONDARY = 1883
MQTT_ENABLED = True                               

MQTT_USE_PRIMARY = True                      

M_FL = 26
M_FR = 25
M_BL = 32
M_BR = 33

ULTRASONIC_TRIG = 23
ULTRASONIC_ECHO = 22
VIBRATION_PIN = 34

SENSOR_INTERVAL = 2
MOTOR_TIMEOUT = 10
ANOMALY_THRESHOLD = 0.75
OBSTACLE_THRESHOLD = 30

SPEAKER_VOLUME = 80
MIC_GAIN = 3
TTS_THRESHOLD = 0.3                                     

EYE_COLOR = 0x00FF7F                
MOUTH_COLOR = 0x00FF7F
BG_COLOR = 0x1A1A2E             
EXPRESSIVE_MODE = True

class DLCore:
    def __init__(self):
        self.model_loaded = False
        self.learning_buffer = []
        self.max_buffer = 50
        self.anomaly_score = 0.0
        self.confidence = 0.0
        self.capabilities = {
            "obstacle_avoidance": True,
            "gesture_recognition": True,
            "anomaly_detection": True,
            "voice_command": True,
            "autonomous_nav": True,
            "speech_synthesis": True,
            "speech_recognition": True,
            "emotion_detection": True
        }
        
    def predict(self, sensor_data):
        features = self._extract_features(sensor_data)
        distance = sensor_data.get("distance", 100)
        vibration = sensor_data.get("vibration", 0)
        
        if distance < OBSTACLE_THRESHOLD:
            self.anomaly_score = 0.9
            self.confidence = 0.95
            return {"action": "avoid", "direction": "back", "confidence": self.confidence, "emotion": "surprised"}
        
        if vibration > 2000:
            self.anomaly_score = 0.8
            self.confidence = 0.88
            return {"action": "alert", "type": "anomaly", "confidence": self.confidence, "emotion": "alert"}
        
        self.anomaly_score = max(0.0, self.anomaly_score - 0.05)
        self.confidence = 0.7 + (self.anomaly_score * 0.3)
        return {"action": "normal", "confidence": self.confidence, "emotion": "happy"}
    
    def _extract_features(self, data):
        return [
            data.get("distance", 0) / 400.0,
            data.get("vibration", 0) / 4095.0,
            data.get("rssi", -100) / -30.0
        ]
    
    def learn(self, sensor_data, action_taken):
        self.learning_buffer.append({
            "sensors": sensor_data,
            "action": action_taken
        })
        if len(self.learning_buffer) > self.max_buffer:
            self.learning_buffer.pop(0)
    
    def get_status(self):
        return {
            "model_loaded": self.model_loaded,
            "anomaly_score": self.anomaly_score,
            "confidence": self.confidence,
            "buffer_size": len(self.learning_buffer),
            "capabilities": self.capabilities
        }

class SerialComm:
    def __init__(self):
        self.uart = None
        self.connected = False
        
    def init(self):
        
        try:
            from machine import UART
                                                           
            self.uart = UART(2, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
            self.connected = True
            print("[SERIAL] COM4 ready")
        except Exception as e:
            print("[SERIAL] Init error:", e)
            self.connected = False
    
    def send(self, data):
        
        if self.connected and self.uart:
            try:
                if isinstance(data, str):
                    data = data.encode()
                self.uart.write(data)
                return True
            except Exception as e:
                print("[SERIAL] Send error:", e)
        return False
    
    def receive(self):
        
        if self.connected and self.uart:
            try:
                if self.uart.any():
                    data = self.uart.read()
                    return data.decode() if data else None
            except Exception as e:
                print("[SERIAL] Receive error:", e)
        return None
    
    def process_commands(self):
        
        cmd = self.receive()
        if cmd:
            cmd = cmd.strip()
            print("[SERIAL] Received:", cmd)
            
            if cmd == "FWD":
                motors.omni(0, 50, 0)
            elif cmd == "REV":
                motors.omni(0, -50, 0)
            elif cmd == "LFT":
                motors.omni(-50, 0, 0)
            elif cmd == "RGT":
                motors.omni(50, 0, 0)
            elif cmd == "RTL":
                motors.omni(0, 0, -50)
            elif cmd == "RTR":
                motors.omni(0, 0, 50)
            elif cmd == "STP":
                motors.stop()
            elif cmd.startswith("NAV"):
                               
                try:
                    coords = cmd[3:].split(',')
                    x, y = int(coords[0]), int(coords[1])
                    navigator.autonomous_navigate((x, y))
                except:
                    pass
            
            return cmd
        return None

class Motors:
    def __init__(self):
        from machine import Pin
        self.pins = {
            "FL": Pin(M_FL, Pin.OUT),
            "FR": Pin(M_FR, Pin.OUT),
            "BL": Pin(M_BL, Pin.OUT),
            "BR": Pin(M_BR, Pin.OUT)
        }
        self.speeds = {"FL": 0, "FR": 0, "BL": 0, "BR": 0}
        for p in self.pins.values():
            p.value(0)
        print("[MOTORS] Ready")
    
    def set(self, name, speed):
        if name in self.pins:
            self.pins[name].value(1 if speed != 0 else 0)
            self.speeds[name] = speed
    
    def set_all(self, data):
        for k, v in data.items():
            self.set(k, v)
    
    def stop(self):
        for k in self.pins:
            self.set(k, 0)
    
    def omni(self, x, y, rot):
        fl = y + x + rot
        fr = y - x - rot
        bl = y - x + rot
        br = y + x - rot
        m = max(abs(fl), abs(fr), abs(bl), abs(br), 1)
        self.set_all({
            "FL": int(fl/m*100),
            "FR": int(fr/m*100),
            "BL": int(bl/m*100),
            "BR": int(br/m*100)
        })

class Sensors:
    def __init__(self):
        from machine import Pin, ADC
        self.trig = Pin(ULTRASONIC_TRIG, Pin.OUT)
        self.echo = Pin(ULTRASONIC_ECHO, Pin.IN)
        self.vib = ADC(Pin(VIBRATION_PIN))
        print("[SENSORS] Ready")
    
    def ultrasonic(self):
        import time
        self.trig.value(0)
        time.sleep_us(2)
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)
        
        t_start = time.ticks_us()
        while self.echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), t_start) > 25000:
                return 0
        t_end = t_start
        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), t_start) > 25000:
                return 0
            t_end = time.ticks_us()
        
        d = time.ticks_diff(t_end, t_start) * 0.0343 / 2
        return round(d, 2)
    
    def vibration(self):
        try:
            return self.vib.read()
        except:
            return 0
    
    def wifi_rssi(self, wlan):
        try:
            if wlan and wlan.isconnected():
                return wlan.status('rssi')
        except:
            pass
        return 0
    
    def read_all(self):
        d = self.ultrasonic()
        v = self.vibration()
        r = self.wifi_rssi(None)
        return {"distance": d, "vibration": v, "rssi": r}

class SpeechEngine:
    def __init__(self):
        self.speaking = False
        self.listening = False
        self.last_speech_time = 0
        self.volume_level = 0
        self.tts_queue = []
        print("[SPEECH] Engine Ready")
    
    def speak(self, text):
        
        if not text:
            return
            
        self.speaking = True
        print("[TTS]", text)
        
        try:
            import M5
            from M5 import Speaker
            Speaker.setVolume(SPEAKER_VOLUME)
            
            for i, char in enumerate(text):
                if char in 'aeiou':
                    freq = 800 + (i * 50)
                    Speaker.tone(freq, 50)
        
        except Exception as e:
            print("[SPEECH ERROR]", e)
        
        self.speaking = False
        self.last_speech_time = time.time()
    
    def listen_start(self):
        
        self.listening = True
        print("[STT] Listening...")
    
    def listen_stop(self):
        
        self.listening = False
        print("[STT] Stopped")
    
    def get_audio_level(self):
        
        try:
            import M5
            from M5 import Mic
            level = Mic.getVolume()
            self.volume_level = level
            return level
        except:
            return 0
    
    def is_speech_detected(self):
        
        level = self.get_audio_level()
        return level > (TTS_THRESHOLD * 100)

class ReactiveFace:
    def __init__(self):
        self.emotion = "happy"
        self.blink_timer = 0
        self.blink_state = False
        self.eye_open = 1.0
        self.mouth_open = 0.0
        self.talk_frame = 0
        self.music_beat = 0
        self.eye_x = 0
        self.eye_y = 0
        self.wobble = 0
        self.initialized = False
        self.colors = {
            "happy": 0x00FF7F,
            "sad": 0x4169E1,
            "surprised": 0xFFD700,
            "alert": 0xFF4444,
            "sleepy": 0x9966CC,
            "excited": 0xFF69B4,
            "thinking": 0x00CED1,
            "listening": 0x00BFFF,
            "speaking": 0xFFA500
        }
        self.bg_color = 0x1A1A2E
        self.face_brightness = 1.0
        self.face_loaded = False
        self.init_display()
        print("[FACE] Reactive Face Ready")
    
    def init_display(self):
        
        self.lcd = None
        try:
            import M5
            M5.begin()
                                           
            try:
                from M5 import M5Lcd
                self.lcd = M5Lcd
                print("[FACE] Using M5Lcd")
            except:
                try:
                    from M5 import Lcd
                    self.lcd = Lcd
                    print("[FACE] Using Lcd")
                except:
                    try:
                        self.lcd = M5
                        print("[FACE] Using M5")
                    except:
                        print("[FACE] No display found")
                        return
            
            try:
                self.lcd.setRotation(1)             
                self.lcd.setBrightness(80)
                print("[FACE] Display configured")
            except:
                pass
            
            self.initialized = True
            print("[FACE] Display ready")
                              
            self.draw_face()
        except Exception as e:
            print("[FACE] Init error:", str(e))
            self.initialized = False
    
    def set_emotion(self, emotion):
        self.emotion = emotion
    
    def update(self, speaking=False, music_level=0, sensor_data=None):
                    
        self.blink_timer += 1
        if self.blink_timer > 120:
            self.blink_state = not self.blink_state
            self.blink_timer = 0
            self.eye_open = 0.15 if self.blink_state else 1.0
        
        if speaking:
            self.talk_frame += 1
            self.mouth_open = 0.5 + (self.talk_frame % 3) * 0.15
        else:
            self.mouth_open = max(0, self.mouth_open - 0.15)
        
        if music_level > 20:
            self.music_beat = music_level / 100.0
            self.wobble = self.music_beat * 8
        else:
            self.wobble *= 0.85
        
        if sensor_data:
            dist = sensor_data.get("distance", 100)
            vib = sensor_data.get("vibration", 0)
            if dist < 30:
                self.eye_y = -3
            elif dist < 50:
                self.eye_y = -1
            else:
                self.eye_y = 0
            
            if vib > 1500:
                self.emotion = "alert"
    
    def draw_face(self):
        
        if not self.initialized:
            return
            
        try:
            import M5
            Lcd = self.lcd
            
            cleared = False
            for clear_method in [lambda: Lcd.clear(0x000000), 
                              lambda: Lcd.fillScreen(0x000000),
                              lambda: Lcd.fill(0x000000)]:
                try:
                    clear_method()
                    cleared = True
                    break
                except:
                    continue
            
            if not cleared:
                print("[FACE] Could not clear screen")
                return
            
            color = self.colors.get(self.emotion, 0x00FF7F)
            eye_size = int(25 * self.eye_open)
            wobble = int(self.wobble)
            
            def draw_circle(x, y, radius, color):
                for method in [lambda: Lcd.drawCircle(x, y, radius, color),
                             lambda: Lcd.fillCircle(x, y, radius, color)]:
                    try:
                        method()
                        break
                    except:
                        continue
            
            def fill_circle(x, y, radius, color):
                for method in [lambda: Lcd.fillCircle(x, y, radius, color),
                             lambda: Lcd.drawCircle(x, y, radius, color)]:            
                    try:
                        method()
                        break
                    except:
                        continue
            
            def draw_line(x1, y1, x2, y2, color):
                try:
                    Lcd.drawLine(x1, y1, x2, y2, color)
                except:
                    pass
            
            draw_circle(90 - wobble, 100, eye_size + 8, 0xFFFFFF)
            draw_circle(90 - wobble, 100, eye_size, color)
            fill_circle(90 - wobble, 100, 6, 0x000000)
            
            draw_circle(190 + wobble, 100, eye_size + 8, 0xFFFFFF)
            draw_circle(190 + wobble, 100, eye_size, color)
            fill_circle(190 + wobble, 100, 6, 0x000000)
            
            brow_y = 70
            if self.emotion == "surprised":
                brow_y = 60
            elif self.emotion == "sad":
                brow_y = 80
            draw_line(60, brow_y, 120, brow_y - 5, color)
            draw_line(160, brow_y - 5, 220, brow_y, color)
            
            self.draw_mouth(color)
            
            if self.emotion in ["happy", "excited", "speaking"]:
                fill_circle(50, 140, 12, 0xFFB6C1)
                fill_circle(230, 140, 12, 0xFFB6C1)
            
        except Exception as e:
            print("[FACE DRAW ERROR]", str(e))
    
    def draw_mouth(self, color):
        
        if not self.initialized:
            return
        try:
            Lcd = self.lcd
            mouth_x = 140
            mouth_y = 155
            
            if self.emotion == "happy":
                for i in range(7):
                    Lcd.fillCircle(mouth_x - 21 + i*7, mouth_y - 3, 8, color)
            elif self.emotion == "surprised":
                Lcd.fillCircle(mouth_x, mouth_y, int(10 + self.mouth_open * 8), color)
            elif self.emotion == "sad":
                for i in range(7):
                    Lcd.fillCircle(mouth_x - 21 + i*7, mouth_y + 8, 8, color)
            elif self.emotion == "speaking" or self.mouth_open > 0.3:
                Lcd.fillCircle(mouth_x, mouth_y, int(12 + self.mouth_open * 8), 0xFFFFFF)
                Lcd.fillCircle(mouth_x, mouth_y, int(8 + self.mouth_open * 5), color)
            elif self.emotion == "thinking":
                Lcd.fillCircle(mouth_x, mouth_y + 5, 6, color)
            else:
                Lcd.drawLine(mouth_x - 20, mouth_y, mouth_x + 20, mouth_y, color)
        except Exception as e:
            print("[MOUTH ERROR]", str(e))
    
    def draw_status_indicators(self):
        
        try:
            from M5 import Lcd
            
            if self.emotion == "listening" or self.emotion == "thinking":
                Lcd.fillCircle(295, 35, 5, 0xFF0000)
                Lcd.drawCircle(295, 48, 5, 0xFF0000)
            
            if self.emotion == "speaking":
                Lcd.fillCircle(15, 35, 5, 0x00FF00)
                Lcd.drawCircle(22, 35, 8, 0x00FF00)
                Lcd.drawCircle(26, 35, 12, 0x00FF00)
        
        except:
            pass
    
    def draw(self):
        
        self.draw_face()

class Navigator:
    def __init__(self, motors, sensors, dl_core):
        self.motors = motors
        self.sensors = sensors
        self.dl = dl_core
        self.position = [0, 0]
        self.grid = []
        self.target = None
        self.autonomous = False
    
    def scan_environment(self):
        readings = []
        import time
        for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
            d = self.sensors.ultrasonic()
            readings.append({"angle": angle, "distance": d})
            time.sleep_ms(100)
        return readings
    
    def autonomous_navigate(self, target_pos):
        self.target = target_pos
        self.autonomous = True
        print("[NAV] Autonomous to", target_pos)
    
    def step(self):
        import time
        sensor_data = self.sensors.read_all()
        prediction = self.dl.predict(sensor_data)
        
        action = prediction.get("action", "normal")
        
        if action == "avoid":
            self.motors.stop()
            time.sleep_ms(200)
            self.motors.set_all({"FL": -50, "FR": 50, "BL": -50, "BR": 50})
        elif action == "alert":
            print("[NAV] Anomaly detected!")
        
        self.dl.learn(sensor_data, action)
        return prediction

class MQTTManager:
    def __init__(self):
        self.client = None
        self.connected = False
        self.using_primary = MQTT_USE_PRIMARY
        self.reconnect_timer = 0
        self.last_heartbeat = 0
    
    def get_broker_info(self):
        if self.using_primary:
            return MQTT_BROKER_PRIMARY, MQTT_PORT_PRIMARY
        return MQTT_BROKER_SECONDARY, MQTT_PORT_SECONDARY
    
    def switch_broker(self):
        
        self.using_primary = not self.using_primary
        broker, port = self.get_broker_info()
        print("[MQTT] Switching to:", broker, port)
        return broker, port
    
    def connect(self):
        import time
        broker, port = self.get_broker_info()
        
        print("[MQTT] Connecting to", broker, port, "...")
        
        try:
            from umqtt.robust import MQTTClient
        except:
            from umqtt.simple import MQTTClient
        
        client_id = "AEGIS-Core2-{}".format(int(time.time()))
        
        try:
            self.client = MQTTClient(client_id, broker, port=port, keepalive=30)
            self.client.connect()
            self.connected = True
            print("[MQTT] Connected to", broker)
            return True
        except Exception as e:
            print("[MQTT] Failed:", str(e)[:50])
        
        print("[MQTT] Trying alternate...")
        broker2, port2 = self.switch_broker()
        
        try:
            self.client = MQTTClient(client_id, broker2, port=port2, keepalive=30)
            self.client.connect()
            self.connected = True
            print("[MQTT] Connected to alternate:", broker2)
            return True
        except Exception as e:
            print("[MQTT] Alt failed:", str(e)[:50])
        
        print("[MQTT] All brokers failed - continuing without MQTT")
        self.connected = False
        return False
    
    def publish(self, topic, msg):
        if self.connected and self.client:
            try:
                self.client.publish(topic, msg)
            except Exception as e:
                print("[MQTT] Pub error:", e)
                self.connected = False
    
    def subscribe(self, topic):
        if self.connected and self.client:
            try:
                self.client.subscribe(topic)
            except Exception as e:
                print("[MQTT] Sub error:", e)
    
    def check_msg(self):
        if self.connected and self.client:
            try:
                self.client.check_msg()
                self.last_heartbeat = time.time()
            except Exception as e:
                print("[MQTT] Msg check error:", e)
                self.connected = False
    
    def is_alive(self):
        
        if not self.connected:
            return False
        
        if time.time() - self.last_heartbeat > 60:
            print("[MQTT] Heartbeat timeout")
            self.connected = False
            return False
        
        return True

def run():
    import network
    import time
    import json
    import random
    
    print("="*50)
    print("AEGIS HomeBot Core2 v3.0 - Full AI Edition")
    print("Multi-MQTT | Speech | Reactive Face")
    print("="*50)
    
    try:
        import M5
        M5.begin()
        print("[M5] Core2 Ready")
    except Exception as e:
        print("[M5] Init error:", e)
    
    dl_core = DLCore()
    print("[DL] Neural Core Initialized")
    
    motors = Motors()
    sensors = Sensors()
    navigator = Navigator(motors, sensors, dl_core)
    speech = SpeechEngine()
    face = ReactiveFace()
    serial_comm = SerialComm()
    
    serial_comm.init()
    
    face.set_emotion("happy")
    face.draw()
    
    mqtt_connected = False
    mqtt_mgr = MQTTManager()
    if MQTT_ENABLED:
        mqtt_connected = False
        for attempt in range(3):
            if mqtt_mgr.connect():
                mqtt_connected = True
                break
            time.sleep(2)
    else:
        print("[MQTT] Disabled - skipping")
    
    print("[WIFI] Connecting...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    for _ in range(30):
        if wlan.isconnected():
            print("[WIFI] OK:", wlan.ifconfig()[0])
            break
        time.sleep(1)
    else:
        print("[WIFI] Failed!")
    
    wifi_ok = wlan.isconnected()
    
    mqtt_connected = False
    if MQTT_ENABLED:
        for attempt in range(3):
            if mqtt_mgr.connect():
                mqtt_connected = True
                break
            time.sleep(2)
    
    def sub(topic, msg):
        print("[MSG]", topic, "<-", msg)
        
        try:
            t = topic.decode() if isinstance(topic, bytes) else topic
            m = msg.decode() if isinstance(msg, bytes) else msg
            
            if t == "homebot/motor/FL":
                motors.set("FL", int(m))
            elif t == "homebot/motor/FR":
                motors.set("FR", int(m))
            elif t == "homebot/motor/BL":
                motors.set("BL", int(m))
            elif t == "homebot/motor/BR":
                motors.set("BR", int(m))
            elif t == "homebot/motors/all":
                motors.set_all(json.loads(m))
            elif t == "homebot/motors/omni":
                d = json.loads(m)
                motors.omni(d.get("x",0), d.get("y",0), d.get("rotation",0))
            elif t == "homebot/motors/stop":
                motors.stop()
            
            elif t == "homebot/sensors/read":
                data = sensors.read_all()
                if mqtt_mgr:
                    mqtt_mgr.publish("homebot/sensors/data", json.dumps(data))
            
            elif t == "homebot/dl/status":
                status = dl_core.get_status()
                if mqtt_mgr:
                    mqtt_mgr.publish("homebot/dl/status", json.dumps(status))
            
            elif t == "homebot/nav/autonomous":
                target = json.loads(m)
                navigator.autonomous_navigate((target.get("x",0), target.get("y",0)))
            elif t == "homebot/nav/scan":
                scan = navigator.scan_environment()
                if mqtt_mgr:
                    mqtt_mgr.publish("homebot/nav/scan", json.dumps(scan))
            
            elif t == "homebot/speech/say":
                                                   
                face.set_emotion("speaking")
                face.update(True, 0, {})
                face.draw()
                speech.speak(m)
                time.sleep(0.5)
                face.set_emotion("happy")
                face.draw()
            
            elif t == "homebot/speech/listen":
                                 
                face.set_emotion("thinking")
                speech.listen_start()
            
            elif t == "homebot/speech/stop":
                speech.listen_stop()
                face.set_emotion("happy")
            
            elif t == "homebot/face/emotion":
                face.set_emotion(m)
            
            elif t == "homebot/audio/beat":
                level = int(m)
                face.update(speech.speaking, level, {})
                face.draw()
            
        except Exception as e:
            print("[ERR]", e)
    
    if mqtt_mgr:
        mqtt_mgr.client.set_callback(sub)
        
        if mqtt_connected:
            try:
                mqtt_mgr.client.connect()
                mqtt_mgr.subscribe(b"homebot/motor/#")
                mqtt_mgr.subscribe(b"homebot/motors/#")
                mqtt_mgr.subscribe(b"homebot/sensors/#")
                mqtt_mgr.subscribe(b"homebot/dl/#")
                mqtt_mgr.subscribe(b"homebot/nav/#")
                mqtt_mgr.subscribe(b"homebot/speech/#")
                mqtt_mgr.subscribe(b"homebot/face/#")
                mqtt_mgr.subscribe(b"homebot/audio/#")
                mqtt_mgr.connected = True
                print("[MQTT] Subscribed to all topics")
            except Exception as e:
                print("[MQTT] Sub error:", e)
        
        if mqtt_connected:
            mqtt_mgr.publish("homebot/status", json.dumps({
                "type": "AEGIS-Core2-v3",
                "wifi": wlan.ifconfig()[0] if wifi_ok else "disconnected",
                "mqtt": mqtt_mgr.get_broker_info()[0],
                "speech": True,
                "face": True
            }))
    
    print("="*50)
    print("AEGIS HomeBot v3.0 Ready!")
    print("Features: Multi-MQTT, Speech, Reactive Face")
    print("="*50)
    
    last_cmd = time.time()
    last_pub = time.time()
    last_nav = time.time()
    last_face = time.time()
    
    while True:
        try:
                                               
            serial_cmd = serial_comm.process_commands()
            if serial_cmd:
                face.set_emotion("thinking")
                face.draw()
                time.sleep(0.5)
                face.set_emotion("happy")
                face.draw()
            
            if mqtt_connected:
                mqtt_mgr.check_msg()
                
                if not mqtt_mgr.is_alive():
                    print("[MQTT] Reconnecting...")
                    for _ in range(3):
                        if mqtt_mgr.connect():
                            mqtt_connected = True
                            break
            
            if time.time() - last_cmd > MOTOR_TIMEOUT:
                if any(motors.speeds.values()):
                    motors.stop()
            
            if time.time() - last_pub > SENSOR_INTERVAL:
                data = sensors.read_all()
                if mqtt_connected:
                    mqtt_mgr.publish("homebot/sensors/data", json.dumps(data))
                last_pub = time.time()
            
            if navigator.autonomous and time.time() - last_nav > 1:
                navigator.step()
                last_nav = time.time()
            
            if time.time() - last_face > 0.1:
                sensor_data = sensors.read_all()
                
                if speech.listening:
                    if speech.is_speech_detected():
                        face.set_emotion("listening")
                        face.update(True, 0, sensor_data)
                    else:
                        face.set_emotion("thinking")
                        face.update(False, 0, sensor_data)
                elif speech.speaking:
                    face.set_emotion("speaking")
                    face.update(True, 0, sensor_data)
                else:
                                           
                    dist = sensor_data.get("distance", 100)
                    vib = sensor_data.get("vibration", 0)
                    if dist < 30:
                        face.set_emotion("surprised")
                    elif vib > 1500:
                        face.set_emotion("alert")
                    elif dl_core.anomaly_score > 0.5:
                        face.set_emotion("alert")
                    else:
                        face.set_emotion("happy")
                    face.update(False, 0, sensor_data)
                
                face.draw()
                
                last_face = time.time()
            
            time.sleep_ms(10)
            
        except Exception as e:
            print("[LOOP]", e)
            time.sleep(1)

if __name__ == "__main__":
    run()
