# ============================================================
# SATURDAY HOME BOT - PRODUCTION HARDWARE DRIVERS
# ============================================================
#
# Hardware:
#   M5Stack Core2
#   M5GO Bottom2
#   DCMotor M021
#
# Motor mapping:
#   CH1 = Rear Left
#   CH2 = Rear Right
#   CH3 = Front Left
#   CH4 = Front Right
#
# Bottom2:
#   RGB SK6812 x10 -> GPIO25
#   Mic LMD4737     -> DATA GPIO34 / CLK GPIO0
#   IMU MPU6886     -> I2C GPIO21 / GPIO22
#
# Ultrasonic:
#   Port A -> GPIO32 / GPIO33
#   Address -> 0x57
#
# IR:
#   Analog GPIO36
#   Digital GPIO26
#
# IMPORTANT ARCHITECTURE:
#
#   drivers.py owns ALL physical hardware access.
#
#   runtime.py       -> orchestration / arbitration
#   autonomy.py      -> movement decisions
#   localization.py  -> spatial awareness
#   communication.py -> MQTT / remote commands
#
#   Only this module communicates directly with hardware.
# ============================================================

import time

try:
    import gc
except Exception:
    gc = None

try:
    import M5
except Exception:
    M5 = None

try:
    from machine import Pin, I2C
except Exception:
    Pin = None
    I2C = None

import config


# ============================================================
# OPTIONAL MOTOR MODULE
#
# Official UIFlow2 API:
#
#   from module import DCMotorModule
#
#   driver = DCMotorModule()
#   driver.set_motor_speed(channel, speed)
#   driver.get_encoder(channel)
#   driver.clear_encoder(channel)
# ============================================================

try:

    from module import DCMotorModule

    DC_MOTOR_AVAILABLE = True

except Exception as error:

    print(
        "[DRIVERS] DCMotorModule unavailable:",
        repr(error)
    )

    DCMotorModule = None

    DC_MOTOR_AVAILABLE = False


# ============================================================
# TIME HELPERS
# ============================================================

def _ticks_ms():

    try:

        return time.ticks_ms()

    except Exception:

        return int(time.time() * 1000)


def _ticks_diff(now, old):

    try:

        return time.ticks_diff(
            now,
            old
        )

    except Exception:

        return now - old


def _sleep_ms(value):

    try:

        time.sleep_ms(
            int(value)
        )

    except Exception:

        time.sleep(
            value / 1000.0
        )


def _sleep_us(value):

    try:

        time.sleep_us(
            int(value)
        )

    except Exception:

        time.sleep(
            value / 1000000.0
        )


# ============================================================
# CONFIG HELPER
# ============================================================

def _cfg(name, default=None):

    try:

        return getattr(
            config,
            name,
            default
        )

    except Exception:

        return default


# ============================================================
# I2C FACTORIES
# ============================================================

def create_port_a_i2c():

    if I2C is None or Pin is None:

        print(
            "[I2C] machine.I2C unavailable"
        )

        return None

    try:

        return I2C(

            1,

            sda=Pin(
                _cfg(
                    "PORT_A_SDA",
                    32
                )
            ),

            scl=Pin(
                _cfg(
                    "PORT_A_SCL",
                    33
                )
            ),

            freq=_cfg(
                "PORT_A_I2C_FREQ",
                100000
            )
        )

    except Exception as error:

        print(
            "[I2C] Port A init error:",
            repr(error)
        )

        return None


def create_internal_i2c():

    if I2C is None or Pin is None:

        print(
            "[I2C] machine.I2C unavailable"
        )

        return None

    try:

        return I2C(

            0,

            sda=Pin(
                _cfg(
                    "INTERNAL_I2C_SDA",
                    21
                )
            ),

            scl=Pin(
                _cfg(
                    "INTERNAL_I2C_SCL",
                    22
                )
            ),

            freq=_cfg(
                "INTERNAL_I2C_FREQ",
                100000
            )
        )

    except Exception as error:

        print(
            "[I2C] Internal init error:",
            repr(error)
        )

        return None


# ============================================================
# MOTOR CONTROLLER
#
# M5Stack DCMotor Module M021
#
# Official UIFlow2 API:
#
#   driver = DCMotorModule()
#
#   driver.set_motor_speed(channel, speed)
#   driver.get_encoder(channel)
#   driver.clear_encoder(channel)
#
# Speed:
#
#   -255 -> reverse
#      0 -> stop
#   +255 -> forward
#
# SATURDAY internal normalized API:
#
#   -1.0 -> reverse max
#    0.0 -> stop
#   +1.0 -> forward max
#
# Physical Mapping:
#
#   CH1 -> Rear Left
#   CH2 -> Rear Right
#   CH3 -> Front Left
#   CH4 -> Front Right
# ============================================================

class MotorController:

    REAR_LEFT_CHANNEL = 1
    REAR_RIGHT_CHANNEL = 2
    FRONT_LEFT_CHANNEL = 3
    FRONT_RIGHT_CHANNEL = 4

    MOTOR_1 = 1
    MOTOR_2 = 2
    MOTOR_3 = 3
    MOTOR_4 = 4

    MAX_SPEED = 255


    def __init__(
        self,
        i2c=None,
        safety=None
    ):

        self.i2c = i2c

        self.safety = safety

        self.driver = None

        self.available = False

        self.initialized = False

        self.emergency_stop_active = False

        self.last_command_time = 0

        self.last_command = None

        self.speeds = [

            0.0,
            0.0,
            0.0,
            0.0

        ]

        # ----------------------------------------------------
        # MOTOR POLARITY
        #
        # Allows physical orientation correction without
        # modifying movement mathematics.
        #
        # Example:
        #
        # MOTOR_POLARITY = [1, -1, 1, -1]
        # ----------------------------------------------------

        try:

            polarity = config.MOTOR_POLARITY

            if len(polarity) == 4:

                self.motor_polarity = list(
                    polarity
                )

            else:

                self.motor_polarity = [

                    1,
                    1,
                    1,
                    1

                ]

        except Exception:

            self.motor_polarity = [

                1,
                1,
                1,
                1

            ]


    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    def begin(self):

        print("")
        print(
            "[MOTOR] Initializing M5Stack DCMotor M021..."
        )

        print(
            "[MOTOR] I2C Address: 0x56"
        )

        if not DC_MOTOR_AVAILABLE:

            print(
                "[MOTOR] ERROR: DCMotorModule import unavailable"
            )

            self.available = False

            return False

        try:

            # ------------------------------------------------
            # Official UIFlow2 constructor
            # ------------------------------------------------

            self.driver = DCMotorModule()

            print(
                "[MOTOR] DCMotorModule instance created"
            )

            # ------------------------------------------------
            # IMMEDIATE SAFE STATE
            # ------------------------------------------------

            for channel in range(1, 5):

                try:

                    self.driver.set_motor_speed(
                        channel,
                        0
                    )

                except Exception as error:

                    print(
                        "[MOTOR] Initial stop warning CH{}:".format(
                            channel
                        ),
                        repr(error)
                    )

            # ------------------------------------------------
            # ENCODER RESET
            # ------------------------------------------------

            encoder_ready = 0

            for channel in range(1, 5):

                try:

                    self.driver.clear_encoder(
                        channel
                    )

                    encoder_ready += 1

                except Exception as error:

                    print(
                        "[MOTOR] Encoder clear warning CH{}:".format(
                            channel
                        ),
                        repr(error)
                    )

            self.available = True

            self.initialized = True

            self.last_command_time = (
                _ticks_ms()
            )

            print(
                "[MOTOR] DCMotor M021 READY"
            )

            print(
                "[MOTOR] CH1 -> REAR LEFT"
            )

            print(
                "[MOTOR] CH2 -> REAR RIGHT"
            )

            print(
                "[MOTOR] CH3 -> FRONT LEFT"
            )

            print(
                "[MOTOR] CH4 -> FRONT RIGHT"
            )

            print(
                "[MOTOR] Encoders initialized: {}/4".format(
                    encoder_ready
                )
            )

            return True

        except Exception as error:

            print(
                "[MOTOR] M021 initialization failed:",
                repr(error)
            )

            self.driver = None

            self.available = False

            self.initialized = False

            return False


    # --------------------------------------------------------
    # SAFETY AUTHORIZATION
    # --------------------------------------------------------

    def _motion_allowed(
        self,
        ignore_safety=False
    ):

        if self.emergency_stop_active:

            return False

        if ignore_safety:

            return True

        if self.safety is None:

            return True

        try:

            return bool(
                self.safety.motion_allowed()
            )

        except Exception as error:

            print(
                "[MOTOR] Safety check error:",
                repr(error)
            )

            # Fail safe if explicit safety system fails.

            return False


    # --------------------------------------------------------
    # SPEED NORMALIZATION
    # --------------------------------------------------------

    def _clamp_speed(
        self,
        speed
    ):

        try:

            speed = float(
                speed
            )

        except Exception:

            speed = 0.0

        if speed > 1.0:

            speed = 1.0

        elif speed < -1.0:

            speed = -1.0

        return speed


    def _to_driver_speed(
        self,
        speed
    ):

        speed = self._clamp_speed(
            speed
        )

        return int(
            speed * self.MAX_SPEED
        )


    # --------------------------------------------------------
    # EMERGENCY STOP
    # --------------------------------------------------------

    def emergency_stop(self):

        print(
            "[MOTOR] !!! EMERGENCY STOP !!!"
        )

        self.emergency_stop_active = True

        return self.stop()


    def clear_emergency_stop(self):

        self.emergency_stop_active = False

        print(
            "[MOTOR] Emergency stop cleared"
        )

        return True


    # --------------------------------------------------------
    # RAW MOTOR WRITE
    #
    # Uses official API:
    #
    # set_motor_speed(channel, speed)
    # --------------------------------------------------------

    def _write_channel(
        self,
        channel,
        speed
    ):

        if not self.available:

            return False

        if self.driver is None:

            return False

        if channel < 1 or channel > 4:

            print(
                "[MOTOR] Invalid channel:",
                channel
            )

            return False

        try:

            speed = self._clamp_speed(
                speed
            )

            index = channel - 1

            # Physical motor orientation correction.

            speed *= (
                self.motor_polarity[index]
            )

            driver_speed = (
                self._to_driver_speed(
                    speed
                )
            )

            # Official UIFlow2 M021 API.

            result = (
                self.driver.set_motor_speed(
                    channel,
                    driver_speed
                )
            )

            self.speeds[index] = speed

            self.last_command_time = (
                _ticks_ms()
            )

            # UIFlow often returns None on success.

            if result is None:

                return True

            return bool(
                result
            )

        except Exception as error:

            print(
                "[MOTOR] CH{} write failed:".format(
                    channel
                ),
                repr(error)
            )

            return False


    # --------------------------------------------------------
    # SINGLE MOTOR
    # --------------------------------------------------------

    def set_motor_channel(

        self,

        channel,

        speed,

        ignore_safety=False

    ):

        if not self._motion_allowed(
            ignore_safety
        ):

            self.stop()

            return False

        return self._write_channel(
            channel,
            speed
        )


    def set_motor(
        self,
        channel,
        speed
    ):

        return self.set_motor_channel(
            channel,
            speed
        )


    # --------------------------------------------------------
    # FOUR MOTOR CONTROL
    #
    # Order:
    #
    # rear_left
    # rear_right
    # front_left
    # front_right
    # --------------------------------------------------------

    def set_all_channels(

        self,

        rear_left,
        rear_right,
        front_left,
        front_right,

        ignore_safety=False

    ):

        if not self.available:

            return False

        if not self._motion_allowed(
            ignore_safety
        ):

            print(
                "[MOTOR] Motion command denied"
            )

            self.stop()

            return False

        values = [

            rear_left,
            rear_right,
            front_left,
            front_right

        ]

        success = True

        for channel in range(1, 5):

            result = self._write_channel(

                channel,

                values[channel - 1]

            )

            if not result:

                success = False

        self.last_command = {
            "type": "wheel_command",
            "values": list(values)
        }

        return success


    def set_all(self, *args):

        if len(args) != 4:

            return False

        return self.set_all_channels(

            args[0],
            args[1],
            args[2],
            args[3]

        )


    # --------------------------------------------------------
    # WHEEL API
    #
    # Logical SATURDAY order:
    #
    # FL FR RL RR
    #
    # Physical M021 mapping:
    #
    # CH1 RL
    # CH2 RR
    # CH3 FL
    # CH4 FR
    # --------------------------------------------------------

    def set_wheels(

        self,

        front_left,
        front_right,
        rear_left,
        rear_right,

        cmd_id=None,

        ignore_safety=False

    ):

        self.last_command = {

            "type": "set_wheels",

            "cmd_id": cmd_id,

            "front_left": front_left,

            "front_right": front_right,

            "rear_left": rear_left,

            "rear_right": rear_right

        }

        return self.set_all_channels(

            rear_left,

            rear_right,

            front_left,

            front_right,

            ignore_safety

        )


    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(self):

        if self.driver is None:

            return False

        success = True

        for channel in range(1, 5):

            try:

                result = (
                    self.driver.set_motor_speed(
                        channel,
                        0
                    )
                )

                if result is False:

                    success = False

            except Exception as error:

                print(

                    "[MOTOR] Stop failed CH{}:".format(
                        channel
                    ),

                    repr(error)

                )

                success = False

        self.speeds = [

            0.0,
            0.0,
            0.0,
            0.0

        ]

        self.last_command = {
            "type": "stop"
        }

        return success


    # --------------------------------------------------------
    # BASIC MOVEMENT
    # --------------------------------------------------------

    def forward(

        self,

        speed=0.5,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            speed,
            speed,
            speed,
            speed,

            ignore_safety=force

        )


    def backward(

        self,

        speed=0.5,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            -speed,
            -speed,
            -speed,
            -speed,

            ignore_safety=force

        )


    def rotate_right(

        self,

        speed=0.5,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            speed,
            -speed,
            speed,
            -speed,

            ignore_safety=force

        )


    def rotate_left(

        self,

        speed=0.5,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            -speed,
            speed,
            -speed,
            speed,

            ignore_safety=force

        )


    # --------------------------------------------------------
    # OMNI / MECANUM MOVEMENT
    # --------------------------------------------------------

    def strafe_left(

        self,

        speed=0.4,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            -speed,
            speed,
            speed,
            -speed,

            ignore_safety=force

        )


    def strafe_right(

        self,

        speed=0.4,

        force=False

    ):

        speed = abs(
            self._clamp_speed(
                speed
            )
        )

        return self.set_all_channels(

            speed,
            -speed,
            -speed,
            speed,

            ignore_safety=force

        )


    # --------------------------------------------------------
    # OMNI DRIVE API
    #
    # vx    = lateral
    # vy    = forward/backward
    # omega = rotation
    #
    # Input:
    #
    # -1.0 -> +1.0
    #
    # This performs wheel mixing rather than priority-based
    # movement, allowing combined translation + rotation.
    # --------------------------------------------------------

    def drive(

        self,

        vx=0.0,

        vy=0.0,

        omega=0.0,

        cmd_id=None,

        force=False

    ):

        vx = self._clamp_speed(
            vx
        )

        vy = self._clamp_speed(
            vy
        )

        omega = self._clamp_speed(
            omega
        )

        # ----------------------------------------------------
        # OMNI / MECANUM MIXING
        #
        # Logical wheel order:
        #
        # FL = vy + vx + omega
        # FR = vy - vx - omega
        # RL = vy - vx + omega
        # RR = vy + vx - omega
        # ----------------------------------------------------

        front_left = (
            vy + vx + omega
        )

        front_right = (
            vy - vx - omega
        )

        rear_left = (
            vy - vx + omega
        )

        rear_right = (
            vy + vx - omega
        )

        # Normalize if any wheel exceeds limits.

        maximum = max(

            abs(front_left),

            abs(front_right),

            abs(rear_left),

            abs(rear_right),

            1.0

        )

        front_left /= maximum
        front_right /= maximum
        rear_left /= maximum
        rear_right /= maximum

        # Dead zone.

        if (

            abs(front_left) < 0.01
            and abs(front_right) < 0.01
            and abs(rear_left) < 0.01
            and abs(rear_right) < 0.01

        ):

            return self.stop()

        return self.set_wheels(

            front_left,

            front_right,

            rear_left,

            rear_right,

            cmd_id=cmd_id,

            ignore_safety=force

        )


    # --------------------------------------------------------
    # ENCODERS
    #
    # Official API:
    #
    # get_encoder(channel)
    # clear_encoder(channel)
    # --------------------------------------------------------

    def get_encoder(

        self,

        motor_id

    ):

        if not self.available:

            return None

        if self.driver is None:

            return None

        if motor_id < 1 or motor_id > 4:

            return None

        try:

            return self.driver.get_encoder(
                motor_id
            )

        except Exception as error:

            print(

                "[MOTOR] Encoder read failed CH{}:".format(
                    motor_id
                ),

                repr(error)

            )

            return None


    def clear_encoder(

        self,

        motor_id

    ):

        if not self.available:

            return False

        if self.driver is None:

            return False

        if motor_id < 1 or motor_id > 4:

            return False

        try:

            result = (
                self.driver.clear_encoder(
                    motor_id
                )
            )

            if result is None:

                return True

            return bool(
                result
            )

        except Exception as error:

            print(

                "[MOTOR] Encoder clear failed CH{}:".format(
                    motor_id
                ),

                repr(error)

            )

            return False


    def get_all_encoders(self):

        return {

            "CH1_REAR_LEFT":
                self.get_encoder(1),

            "CH2_REAR_RIGHT":
                self.get_encoder(2),

            "CH3_FRONT_LEFT":
                self.get_encoder(3),

            "CH4_FRONT_RIGHT":
                self.get_encoder(4)

        }


    def clear_all_encoders(self):

        success = True

        for motor_id in range(1, 5):

            if not self.clear_encoder(
                motor_id
            ):

                success = False

        return success


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def status(self):

        return {

            "available":
                self.available,

            "initialized":
                self.initialized,

            "driver":
                "DCMotorModule M021",

            "emergency_stop":
                self.emergency_stop_active,

            "mapping": {

                "CH1":
                    "REAR_LEFT",

                "CH2":
                    "REAR_RIGHT",

                "CH3":
                    "FRONT_LEFT",

                "CH4":
                    "FRONT_RIGHT"

            },

            "speeds":
                list(
                    self.speeds
                ),

            "encoders":
                self.get_all_encoders(),

            "last_command":
                self.last_command

        }


# Legacy compatibility alias

FourEncoderMotorV11 = MotorController


# ============================================================
# ULTRASONIC SENSOR
# ============================================================

class UltrasonicSensor:

    ADDRESS = 0x57

    COMMAND = 0x01


    def __init__(
        self,
        i2c=None
    ):

        self.i2c = i2c

        self.available = False

        self.distance_cm = None

        self.last_valid_time = 0

        self.readings = []

        self.max_history = 5

        self.success_count = 0

        self.error_count = 0


    def begin(self):

        print(
            "[ULTRASONIC] Initializing Port A..."
        )

        try:

            if self.i2c is None:

                self.i2c = (
                    create_port_a_i2c()
                )

            if self.i2c is None:

                return False

            devices = self.i2c.scan()

            print(

                "[ULTRASONIC] Scan:",

                [
                    hex(x)
                    for x in devices
                ]

            )

            if self.ADDRESS not in devices:

                print(
                    "[ULTRASONIC] Sensor not detected"
                )

                return False

            self.available = True

            print(
                "[ULTRASONIC] READY"
            )

            return True

        except Exception as error:

            print(

                "[ULTRASONIC] Begin error:",

                repr(error)

            )

            return False


    def _read_raw(self):

        self.i2c.writeto(

            self.ADDRESS,

            bytes([
                self.COMMAND
            ])

        )

        _sleep_ms(80)

        data = self.i2c.readfrom(

            self.ADDRESS,

            3

        )

        if data is None:

            return None

        if len(data) != 3:

            return None

        return (

            (data[0] << 16)

            |

            (data[1] << 8)

            |

            data[2]

        )


    def _filtered_distance(self):

        if not self.readings:

            return self.distance_cm

        values = list(
            self.readings
        )

        values.sort()

        length = len(values)

        middle = length // 2

        if length % 2:

            return values[middle]

        return (

            values[middle - 1]

            +

            values[middle]

        ) / 2


    def read(self):

        if not self.available:

            return None

        for attempt in range(3):

            try:

                raw = self._read_raw()

                if raw is None:

                    continue

                distance = raw / 1000.0

                if distance < 2.0:

                    continue

                if distance > 450.0:

                    continue

                self.distance_cm = distance

                self.last_valid_time = (
                    _ticks_ms()
                )

                self.success_count += 1

                self.readings.append(
                    distance
                )

                if len(
                    self.readings
                ) > self.max_history:

                    self.readings.pop(0)

                return (
                    self._filtered_distance()
                )

            except Exception:

                self.error_count += 1

        if self.last_valid_time:

            age = _ticks_diff(

                _ticks_ms(),

                self.last_valid_time

            )

            if age < 2000:

                return (
                    self._filtered_distance()
                )

        return None


    def read_cm(self):

        return self.read()


    def is_obstacle(
        self,
        threshold_cm=30
    ):

        distance = self.read()

        if distance is None:

            return False

        return (
            distance <= threshold_cm
        )


    def status(self):

        return {

            "available":
                self.available,

            "distance_cm":
                self.distance_cm,

            "success_count":
                self.success_count,

            "error_count":
                self.error_count

        }


# ============================================================
# IR SENSOR
# ============================================================

class IRSensor:


    def __init__(self):

        self.digital_pin = None

        self.analog_pin = None

        self.available = False

        self.detected = False

        self.last_analog = 0

        self.last_digital = None


    def begin(self):

        try:

            if Pin is None:

                return False

            digital_pin = _cfg(

                "IR_DIGITAL_PIN",

                _cfg(
                    "IR_PIN",
                    26
                )

            )

            analog_pin = _cfg(

                "IR_ANALOG_PIN",

                36

            )

            try:

                self.digital_pin = Pin(

                    digital_pin,

                    Pin.IN

                )

            except Exception:

                self.digital_pin = None

            try:

                self.analog_pin = Pin(

                    analog_pin,

                    Pin.IN

                )

            except Exception:

                self.analog_pin = None

            self.available = (

                self.digital_pin is not None

                or

                self.analog_pin is not None

            )

            print(

                "[IR] Digital:",

                digital_pin,

                "Analog:",

                analog_pin

            )

            return self.available

        except Exception as error:

            print(

                "[IR] Begin error:",

                repr(error)

            )

            return False


    def read_digital(self):

        if self.digital_pin is None:

            return None

        try:

            raw = self.digital_pin.value()

            self.last_digital = raw

            active_low = _cfg(
                "IR_ACTIVE_LOW",
                True
            )

            if active_low:

                self.detected = (
                    raw == 0
                )

            else:

                self.detected = (
                    raw == 1
                )

            return self.detected

        except Exception:

            return False


    def read_analog(self):

        if self.analog_pin is None:

            return None

        try:

            if hasattr(
                self.analog_pin,
                "read"
            ):

                self.last_analog = (
                    self.analog_pin.read()
                )

            elif hasattr(

                self.analog_pin,

                "value"

            ):

                self.last_analog = (
                    self.analog_pin.value()
                )

            return self.last_analog

        except Exception:

            return None


    def read(self):

        return self.read_digital()


    def status(self):

        return {

            "available":
                self.available,

            "detected":
                self.detected,

            "analog":
                self.last_analog,

            "digital":
                self.last_digital

        }


# ============================================================
# RAW SK6812 DRIVER
#
# Bottom2
#
# GPIO25
# 10 LEDs
# ============================================================

class Bottom2RGB:

    T0H = 1
    T0L = 1

    T1H = 1
    T1L = 1


    def __init__(self):

        self.pin_number = _cfg(

            "BOTTOM2_LED_PIN",

            25

        )

        self.count = _cfg(

            "BOTTOM2_LED_COUNT",

            10

        )

        self.pin = None

        self.available = False

        self.backend = "raw_gpio"

        self.brightness = _cfg(

            "BOTTOM2_LED_BRIGHTNESS",

            255

        )

        self.pixels = []

        for _ in range(
            self.count
        ):

            self.pixels.append(
                (0, 0, 0)
            )


    def begin(self):

        try:

            if Pin is None:

                return False

            self.pin = Pin(

                self.pin_number,

                Pin.OUT

            )

            self.pin.value(0)

            self.available = True

            self.clear()

            print(
                "[RGB] SK6812 RAW READY"
            )

            print(

                "[RGB] GPIO:",

                self.pin_number,

                "Count:",

                self.count

            )

            return True

        except Exception as error:

            print(

                "[RGB] Init error:",

                repr(error)

            )

            self.available = False

            return False


    def _send_byte(
        self,
        value
    ):

        mask = 0x80

        while mask:

            if value & mask:

                self.pin.value(1)

                _sleep_us(1)

                self.pin.value(0)

                _sleep_us(1)

            else:

                self.pin.value(1)

                _sleep_us(1)

                self.pin.value(0)

                _sleep_us(1)

            mask >>= 1


    def _scale(
        self,
        value
    ):

        return int(

            max(

                0,

                min(
                    255,
                    value
                )

            )

            *

            self.brightness

            /

            255

        )


    def show(self):

        if not self.available:

            return False

        try:

            # SK6812 GRB ordering.

            for red, green, blue in self.pixels:

                green = self._scale(
                    green
                )

                red = self._scale(
                    red
                )

                blue = self._scale(
                    blue
                )

                self._send_byte(
                    green
                )

                self._send_byte(
                    red
                )

                self._send_byte(
                    blue
                )

            self.pin.value(0)

            _sleep_us(100)

            return True

        except Exception as error:

            print(

                "[RGB] Show error:",

                repr(error)

            )

            return False


    def set_pixel(

        self,

        index,

        red,

        green,

        blue,

        show=False

    ):

        if index < 0:

            return False

        if index >= self.count:

            return False

        red = max(
            0,
            min(
                255,
                int(red)
            )
        )

        green = max(
            0,
            min(
                255,
                int(green)
            )
        )

        blue = max(
            0,
            min(
                255,
                int(blue)
            )
        )

        self.pixels[index] = (

            red,

            green,

            blue

        )

        if show:

            return self.show()

        return True


    def fill(

        self,

        red,

        green,

        blue,

        show=True

    ):

        for index in range(
            self.count
        ):

            self.pixels[index] = (

                int(red),

                int(green),

                int(blue)

            )

        if show:

            return self.show()

        return True


    def clear(self):

        return self.fill(

            0,

            0,

            0,

            True

        )


    def set_brightness(
        self,
        value
    ):

        self.brightness = max(

            0,

            min(

                255,

                int(value)

            )

        )

        return self.show()


    def status(self):

        return {

            "available":
                self.available,

            "backend":
                self.backend,

            "pin":
                self.pin_number,

            "count":
                self.count,

            "brightness":
                self.brightness

        }


# ============================================================
# MICROPHONE
# ============================================================

class MicrophoneSensor:


    def __init__(self):

        self.available = False

        self.backend = None

        self.data_pin = _cfg(

            "BOTTOM2_MIC_DATA_PIN",

            34

        )

        self.clock_pin = _cfg(

            "BOTTOM2_MIC_CLK_PIN",

            0

        )

        self.level = 0


    def begin(self):

        if M5 is not None:

            try:

                if hasattr(
                    M5,
                    "Mic"
                ):

                    self.backend = "M5.Mic"

                    self.available = True

                    print(

                        "[MIC] Backend:",

                        self.backend

                    )

                    return True

            except Exception:

                pass

        return False


    def read_level(self):

        # Preserved placeholder hardware abstraction.
        # Actual microphone sampling can be expanded later.

        self.level = 0

        return self.level


    def is_sound_active(
        self,
        threshold=15
    ):

        return (

            self.read_level()

            >=

            threshold

        )


    def status(self):

        return {

            "available":
                self.available,

            "backend":
                self.backend,

            "level":
                self.level

        }


# ============================================================
# MPU6886 IMU
# ============================================================

class IMUSensor:

    ADDRESS = 0x68

    ACCEL_XOUT_H = 0x3B

    PWR_MGMT_1 = 0x6B


    def __init__(self):

        self.i2c = None

        self.available = False

        self.acceleration = (

            0.0,

            0.0,

            0.0

        )


    def begin(self):

        try:

            self.i2c = (
                create_internal_i2c()
            )

            if self.i2c is None:

                return False

            devices = self.i2c.scan()

            if self.ADDRESS not in devices:

                print(
                    "[IMU] MPU6886 not detected"
                )

                return False

            try:

                self.i2c.writeto_mem(

                    self.ADDRESS,

                    self.PWR_MGMT_1,

                    bytes([0])

                )

            except Exception:

                pass

            self.available = True

            print(
                "[IMU] MPU6886 READY"
            )

            return True

        except Exception as error:

            print(

                "[IMU] Begin error:",

                repr(error)

            )

            return False


    def _signed16(
        self,
        high,
        low
    ):

        value = (
            high << 8
        ) | low

        if value & 0x8000:

            value -= 65536

        return value


    def read_acceleration(self):

        if not self.available:

            return self.acceleration

        try:

            data = self.i2c.readfrom_mem(

                self.ADDRESS,

                self.ACCEL_XOUT_H,

                6

            )

            x = self._signed16(

                data[0],

                data[1]

            )

            y = self._signed16(

                data[2],

                data[3]

            )

            z = self._signed16(

                data[4],

                data[5]

            )

            self.acceleration = (

                x / 16384.0,

                y / 16384.0,

                z / 16384.0

            )

        except Exception:

            pass

        return self.acceleration


    def read(self):

        return self.read_acceleration()


    def status(self):

        return {

            "available":
                self.available,

            "acceleration":
                self.acceleration

        }


# ============================================================
# POWER MANAGER
# ============================================================

class PowerManager:


    def __init__(self):

        self.available = False

        self.battery_percent = None

        self.charging = None


    def begin(self):

        if M5 is None:

            return False

        try:

            if hasattr(
                M5,
                "Power"
            ):

                self.available = True

                print(
                    "[POWER] M5 Power API available"
                )

                return True

        except Exception:

            pass

        return False


    def update(self):

        if not self.available:

            return {

                "battery_percent":
                    self.battery_percent,

                "charging":
                    self.charging

            }

        try:

            power = M5.Power

            for method in (

                "getBatteryLevel",

                "getBatteryPercentage",

                "getBatteryPercent"

            ):

                if hasattr(
                    power,
                    method
                ):

                    self.battery_percent = int(

                        getattr(
                            power,
                            method
                        )()

                    )

                    break

        except Exception:

            pass

        return {

            "battery_percent":
                self.battery_percent,

            "charging":
                self.charging

        }


    def is_low(self):

        if self.battery_percent is None:

            return False

        return (

            self.battery_percent

            <=

            _cfg(

                "LOW_BATTERY_PERCENT",

                25

            )

        )


    def is_critical(self):

        if self.battery_percent is None:

            return False

        return (

            self.battery_percent

            <=

            _cfg(

                "CRITICAL_BATTERY_PERCENT",

                12

            )

        )


    def status(self):

        return self.update()


# ============================================================
# HARDWARE MANAGER
#
# Central physical hardware abstraction for SATURDAY.
#
# This class is injected into:
#
# Runtime
# Localization
# Autonomy
# Communication
#
# Hardware remains owned HERE.
# ============================================================

class HardwareManager:


    def __init__(
        self,
        config=None
    ):

        # Configuration object accepted for SATURDAY dependency
        # injection compatibility.

        self.config = config

        # ----------------------------------------------------
        # HARDWARE SUBSYSTEMS
        # ----------------------------------------------------

        self.motor = MotorController()

        self.ultrasonic = UltrasonicSensor()

        self.ir = IRSensor()

        self.rgb = Bottom2RGB()

        self.microphone = MicrophoneSensor()

        self.imu = IMUSensor()

        self.power = PowerManager()

        # ----------------------------------------------------
        # SYSTEM STATE
        # ----------------------------------------------------

        self.initialized = False

        self.results = {}


    # --------------------------------------------------------
    # INITIALIZE ALL HARDWARE
    # --------------------------------------------------------

    def begin(self):

        print("")
        print(
            "[DRIVERS] ================================="
        )

        print(
            "[DRIVERS] INITIALIZING SATURDAY HARDWARE"
        )

        print(
            "[DRIVERS] ================================="
        )

        results = {}

        # ----------------------------------------------------
        # MOTOR
        # ----------------------------------------------------

        try:

            results["motor"] = (
                self.motor.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] Motor init error:",
                repr(error)
            )

            results["motor"] = False

        # ----------------------------------------------------
        # ULTRASONIC
        # ----------------------------------------------------

        try:

            results["ultrasonic"] = (
                self.ultrasonic.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] Ultrasonic init error:",
                repr(error)
            )

            results["ultrasonic"] = False

        # ----------------------------------------------------
        # IR
        # ----------------------------------------------------

        try:

            results["ir"] = (
                self.ir.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] IR init error:",
                repr(error)
            )

            results["ir"] = False

        # ----------------------------------------------------
        # RGB
        # ----------------------------------------------------

        try:

            results["rgb"] = (
                self.rgb.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] RGB init error:",
                repr(error)
            )

            results["rgb"] = False

        # ----------------------------------------------------
        # MICROPHONE
        # ----------------------------------------------------

        try:

            results["microphone"] = (
                self.microphone.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] Microphone init error:",
                repr(error)
            )

            results["microphone"] = False

        # ----------------------------------------------------
        # IMU
        # ----------------------------------------------------

        try:

            results["imu"] = (
                self.imu.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] IMU init error:",
                repr(error)
            )

            results["imu"] = False

        # ----------------------------------------------------
        # POWER
        # ----------------------------------------------------

        try:

            results["power"] = (
                self.power.begin()
            )

        except Exception as error:

            print(
                "[DRIVERS] Power init error:",
                repr(error)
            )

            results["power"] = False

        self.results = results

        self.initialized = True

        print("")
        print(
            "[DRIVERS] Hardware initialization complete"
        )

        for name in results:

            state = (

                "ONLINE"

                if results[name]

                else

                "OFFLINE"

            )

            print(

                "[DRIVERS] {}: {}".format(

                    name.upper(),

                    state

                )

            )

        print(
            "[DRIVERS] ================================="
        )

        return results


    # --------------------------------------------------------
    # COMPATIBILITY INITIALIZER
    # --------------------------------------------------------

    def initialize(self):

        return self.begin()


    # --------------------------------------------------------
    # SAFE STOP
    # --------------------------------------------------------

    def stop_all(self):

        success = True

        try:

            if not self.motor.stop():

                success = False

        except Exception:

            success = False

        return success


    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    def cleanup(self):

        print(
            "[DRIVERS] Cleaning up hardware..."
        )

        try:

            self.stop_all()

        except Exception:

            pass

        try:

            self.rgb.clear()

        except Exception:

            pass

        if gc is not None:

            try:

                gc.collect()

            except Exception:

                pass

        print(
            "[DRIVERS] Hardware cleanup complete"
        )


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def status(self):

        return {

            "initialized":
                self.initialized,

            "motor":
                self.motor.status(),

            "ultrasonic":
                self.ultrasonic.status(),

            "ir":
                self.ir.status(),

            "rgb":
                self.rgb.status(),

            "microphone":
                self.microphone.status(),

            "imu":
                self.imu.status(),

            "power":
                self.power.status(),

            "initialization_results":
                dict(self.results)

        }


# ============================================================
# SATURDAY ARCHITECTURE COMPATIBILITY
#
# main.py expects:
#
#     Drivers = safe_import("drivers", "Drivers")
#
# This alias MUST exist AFTER HardwareManager.
# ============================================================

Drivers = HardwareManager