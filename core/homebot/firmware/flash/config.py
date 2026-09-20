# ============================================================
# SATURDAY HOME BOT
# CENTRAL CONFIGURATION
#
# Platform:
# M5Stack Core2 + M5GO Bottom2
# UIFlow2 MicroPython
# ============================================================

import time


# ============================================================
# TIME HELPERS
# ============================================================

try:

    def now_ms():
        return time.ticks_ms()

    def elapsed_ms(previous):
        return time.ticks_diff(
            time.ticks_ms(),
            previous
        )

except Exception:

    def now_ms():
        return int(time.time() * 1000)

    def elapsed_ms(previous):
        return now_ms() - previous


# ============================================================
# IDENTITY
# ============================================================

DEVICE_ID = "saturday_homebot_01"
DEVICE_NAME = "SATURDAY"

FIRMWARE_VERSION = "3.0.0"
HARDWARE_PLATFORM = "M5STACK_CORE2_M5GO_BOTTOM2"


# ============================================================
# NETWORK
# ============================================================

WIFI_SSID = "G302 2.4G"
WIFI_PASSWORD = "9655683999"

MQTT_USER = ""
MQTT_PASSWORD = ""


try:

    import secrets

    WIFI_SSID = getattr(
        secrets,
        "WIFI_SSID",
        WIFI_SSID
    )

    WIFI_PASSWORD = getattr(
        secrets,
        "WIFI_PASSWORD",
        getattr(
            secrets,
            "WIFI_PASS",
            WIFI_PASSWORD
        )
    )

    MQTT_USER = getattr(
        secrets,
        "MQTT_USER",
        MQTT_USER
    )

    MQTT_PASSWORD = getattr(
        secrets,
        "MQTT_PASSWORD",
        getattr(
            secrets,
            "MQTT_PASS",
            MQTT_PASSWORD
        )
    )

except Exception:

    pass


# ============================================================
# MQTT
# ============================================================

MQTT_PRIMARY = "192.168.1.38"
MQTT_SECONDARY = "192.168.1.38"

MQTT_PORT = 1883
MQTT_KEEPALIVE = 30

MQTT_RECONNECT_MS = 5000
MQTT_POLL_INTERVAL_MS = 30


# ============================================================
# MQTT TOPICS
# ============================================================

MQTT_ROOT = "saturday"

MQTT_TOPIC_COMMAND = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/command"
)

MQTT_TOPIC_TELEMETRY = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/telemetry"
)

MQTT_TOPIC_STATUS = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/status"
)

MQTT_TOPIC_INTENT = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/intent"
)

MQTT_TOPIC_VOICE = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/voice"
)

MQTT_TOPIC_EVENTS = (
    MQTT_ROOT
    + "/"
    + DEVICE_ID
    + "/events"
)


# ============================================================
# CORE2 INTERNAL I2C
#
# GPIO21 SDA
# GPIO22 SCL
#
# Shared:
# - MPU6886
# - Core2 internal peripherals
# - Bottom2 pogo expansion
# ============================================================

INTERNAL_I2C_SDA = 21
INTERNAL_I2C_SCL = 22

INTERNAL_I2C_FREQ = 100000


# ============================================================
# PORT A I2C
#
# GPIO32 SDA
# GPIO33 SCL
#
# Verified:
# Ultrasonic -> 0x57
# ============================================================

PORT_A_SDA = 32
PORT_A_SCL = 33

PORT_A_I2C_FREQ = 100000


# ============================================================
# I2C ADDRESSES
# ============================================================

ULTRASONIC_ADDR = 0x57
MPU6886_ADDR = 0x68


# ============================================================
# M5GO BOTTOM2 RGB BAR
#
# SK6812 x10
# DATA = GPIO25
# ============================================================

BOTTOM2_LED_PIN = 25
BOTTOM2_LED_COUNT = 10

RGB_BRIGHTNESS = 0.20

RGB_UPDATE_INTERVAL_MS = 40


# ============================================================
# M5GO BOTTOM2 MICROPHONE
#
# LMD4737
#
# DATA = GPIO34
# CLK  = GPIO0
# ============================================================

BOTTOM2_MIC_DATA_PIN = 34
BOTTOM2_MIC_CLK_PIN = 0

MIC_SAMPLE_RATE = 8000

MIC_SAMPLE_BITS = 16

MIC_AMBIENT_BYTES = 512

MIC_INTERVAL_MS = 100

MIC_REACTIVE_LEVEL = 15
MIC_LOUD_LEVEL = 35


# ============================================================
# CORE2 AUDIO
# ============================================================

SPEAKER_ENABLED = True

SPEAKER_VOLUME = 70

AUDIO_REACTIVE_ENABLED = True


# ============================================================
# IMU
# ============================================================

IMU_ENABLED = True

IMU_SAMPLE_INTERVAL_MS = 80


# ============================================================
# MOTOR CONFIGURATION
#
# VERIFIED PHYSICAL MAP
#
# FRONT
#
# CH3 = Front Left
# CH4 = Front Right
#
# CH1 = Rear Left
# CH2 = Rear Right
#
# REAR
# ============================================================

REAR_LEFT_CHANNEL = 1
REAR_RIGHT_CHANNEL = 2

FRONT_LEFT_CHANNEL = 3
FRONT_RIGHT_CHANNEL = 4


# Physical calibration already verified.
MOTOR_POLARITY = (
    1,
    1,
    1,
    1
)

MAX_MOTOR_SPEED = 0.70

MAX_AUTONOMY_SPEED = 0.28

MOTOR_COMMAND_TIMEOUT_MS = 1500


# ============================================================
# ULTRASONIC
# ============================================================

ULTRASONIC_ENABLED = True

ULTRASONIC_INTERVAL_MS = 150

ULTRASONIC_MIN_CM = 2.0
ULTRASONIC_MAX_CM = 450.0

ULTRASONIC_STOP_CM = 25.0
ULTRASONIC_CAUTION_CM = 55.0


# ============================================================
# IR REFLECTIVE SENSOR
#
# Bottom2 Port B
#
# Analog = GPIO36
# Digital = GPIO26
# ============================================================

IR_ANALOG_PIN = 36
IR_DIGITAL_PIN = 26

IR_ACTIVE_LOW = True

IR_INTERVAL_MS = 80


# ============================================================
# SAFETY
# ============================================================

OBSTACLE_STOP_CM = 25
OBSTACLE_CAUTION_CM = 55

DEADMAN_MS = 1200

REMOTE_PRIORITY_MS = 1800

EMERGENCY_STOP_ENABLED = True


# ============================================================
# AUTONOMY
# ============================================================

AUTONOMY_ENABLED = True

AUTONOMY_INTERVAL_MS = 80

AUTONOMY_IDLE_INTERVAL_MS = 3000

FOLLOW_ENABLED = True

FOLLOW_SPEED = 0.20

FOLLOW_TURN_SPEED = 0.18

FOLLOW_DISTANCE_CM = 80

FOLLOW_DISTANCE_TOLERANCE_CM = 20


# ============================================================
# MULTI-BRAIN ARBITRATION
#
# Priority:
#
# 100 = Emergency safety
# 90  = Collision / boundary safety
# 80  = Docking
# 70  = Master SATURDAY brain
# 60  = Interactive behaviour
# 50  = Local autonomy
# 10  = Idle
# ============================================================

PRIORITY_EMERGENCY = 100
PRIORITY_SAFETY = 90
PRIORITY_DOCKING = 80
PRIORITY_MASTER = 70
PRIORITY_INTERACTION = 60
PRIORITY_AUTONOMY = 50
PRIORITY_IDLE = 10

INTENT_TIMEOUT_MS = 1500


# ============================================================
# POWER MANAGEMENT
# ============================================================

POWER_MONITOR_ENABLED = True

POWER_INTERVAL_MS = 5000

LOW_BATTERY_PERCENT = 25
CRITICAL_BATTERY_PERCENT = 12

AUTO_DOCK_ENABLED = True

DOCK_SEARCH_TIMEOUT_MS = 120000

DOCK_APPROACH_SPEED = 0.15


# ============================================================
# DOCK MEMORY
#
# First stable startup position becomes origin.
# Later this becomes the remembered dock reference.
#
# This is intentionally logical state for now.
# True coordinate navigation requires odometry/localization.
# ============================================================

DOCK_MEMORY_ENABLED = True

DOCK_SAVE_INTERVAL_MS = 30000

DOCK_ORIGIN_X = 0.0
DOCK_ORIGIN_Y = 0.0
DOCK_ORIGIN_HEADING = 0.0


# ============================================================
# FACE / DISPLAY
# ============================================================

DISPLAY_ENABLED = True

FACE_INTERVAL_MS = 40

FACE_BLINK_MIN_MS = 2500
FACE_BLINK_MAX_MS = 6000

FACE_ANIMATION_SPEED = 1.0

FACE_SMOOTHING = 0.18


# ============================================================
# DISPLAY COLORS
#
# RGB565
# ============================================================

COLOR_BG = 0x10131C

COLOR_WHITE = 0xFFFF
COLOR_BLACK = 0x0000

COLOR_EYE = 0xA7E7FF
COLOR_EYE_HIGHLIGHT = 0xFFFFFF

COLOR_ALERT = 0xF800

COLOR_HAPPY = 0x07E0

COLOR_IDLE = 0x001F

COLOR_ACCENT = 0xC618


# ============================================================
# RUNTIME
# ============================================================

SENSOR_INTERVAL_MS = 80

FACE_UPDATE_INTERVAL_MS = 40

RUNTIME_IDLE_SLEEP_MS = 10

TELEMETRY_INTERVAL_MS = 2500


# ============================================================
# DEBUG
# ============================================================

DEBUG = True

DEBUG_HARDWARE = True
DEBUG_MQTT = False
DEBUG_AUTONOMY = True
DEBUG_AUDIO = False
DEBUG_POWER = True