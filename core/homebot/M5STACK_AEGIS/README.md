# AEGIS HomeBot - M5Stack CORE2
## Complete Firmware v3.0

### Features
- **WiFi Connection** - Connects to your network
- **MQTT** - Communicates with AEGIS server
- **Display UI** - Shows status, IP, battery, direction
- **AEGIS Eye Animation** - Animated eye that looks in movement direction
- **Motor Control** - FWD, REV, LFT, RGT, RTL, RTR, STP
- **Serial Commands** - Control via UART
- **Auto-Reconnect** - Reconnects if connection lost

### Installation

#### 1. Install MicroPython on M5Stack CORE2
Using M5Burner:
- Open M5Burner app
- Go to "MicroPython" category
- Download "M5Core2" MicroPython firmware
- Select COM port and burn

#### 2. Configure WiFi
Edit `main.py` and set your WiFi credentials:
```python
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
```

#### 3. Set AEGIS Server IP
```python
AEGIS_MQTT_SERVER = "192.168.0.100"  # Your AEGIS PC IP
```

#### 4. Upload main.py to M5Stack
Using M5Burner:
- Click "Custom" tab
- Select main.py
- Upload

Or using Thonny:
- Connect M5Stack
- Open main.py in Thonny
- Save to M5Stack as main.py

### Display Features
```
+--------------------------------+
|     AEGIS HOMEBOT              |  <- Title
|                                |
|   WiFi: OK    MQTT: OK         |  <- Status
|                                |
|        ( AEGIS EYE )           |  <- Animated eye
|           O  O                  |     Looks in direction
|                                |
|   DIRECTION: FWD               |  <- Current move
|   BATTERY: 85%                 |
|   IP: 192.168.1.100           |
+--------------------------------+
```

### Serial Commands (115200 baud)
| Command | Description |
|---------|-------------|
| FWD | Move forward |
| REV | Move backward |
| LFT | Strafe left |
| RGT | Strafe right |
| RTL | Rotate left |
| RTR | Rotate right |
| STP | Stop |
| PING | Check connection |
| STATUS | Show all status |
| WIFI | Show IP address |

### MQTT Topics
- Subscribe: `aegis/homebot/cmd` - Receive commands from AEGIS
- Publish: `aegis/homebot/status` - Send status to AEGIS

### Example Commands
```
FWD     -> Move forward
REV     -> Move backward
RTL     -> Rotate counter-clockwise
STP     -> Stop motors
PING    -> Response: PONG
```

### Wiring (Motor Driver)
```
M5Stack CORE2 -> Motor Driver
GPIO32 -> Motor A PWM
GPIO33 -> Motor A IN1
GPIO25 -> Motor A IN2
GPIO26 -> Motor B PWM
GPIO27 -> Motor B IN1
GPIO14 -> Motor B IN2
GND    -> GND
```

### Troubleshooting
1. No display? - Make sure M5Stack LCD firmware is installed
2. Motors not working? - Check motor driver connections
3. WiFi not connecting? - Verify SSID and password
4. MQTT not connecting? - Check AEGIS MQTT server IP

### AEGIS Integration
When connected to AEGIS, you can say:
- "HomeBot move forward"
- "HomeBot turn left"
- "HomeBot stop"
AEGIS will send the command via MQTT to the HomeBot!
