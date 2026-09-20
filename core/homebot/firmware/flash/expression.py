"""
============================================================
SATURDAY EMBODIMENT ENGINE v2
Core2 Display + M5GO Bottom2 RGB
============================================================

Hardware:
- M5Stack Core2
- 320x240 Display
- M5GO Bottom2
- 10x SK6812 RGB LEDs
- GPIO25

Design:
- Smooth interpolated eyes
- Natural blinking
- Idle breathing
- Gentle gaze movement
- Cute responsive expressions
- Non-blocking animation loop
- Raw SK6812 driver
- Full dual-side RGB control

IMPORTANT:
update() must be called continuously by Runtime.
No blocking loops.
No sleep() inside animation logic.
============================================================
"""

import time
import math

try:
    import M5
    from M5 import *
    M5_AVAILABLE = True
except Exception as e:
    print("[EXPRESSION] M5 import error:", e)
    M5_AVAILABLE = False

try:
    from machine import Pin, bitstream
    RGB_AVAILABLE = True
except Exception as e:
    print("[EXPRESSION] RGB machine driver unavailable:", e)
    RGB_AVAILABLE = False


# ============================================================
# HELPERS
# ============================================================

def clamp(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def lerp(current, target, amount):
    return current + ((target - current) * amount)


# ============================================================
# RAW SK6812 DRIVER
# ============================================================

class RGBController:
    """
    Direct GPIO25 SK6812 driver.

    M5GO Bottom2:
    GPIO25 -> 10 chained SK6812 LEDs
    """

    LED_PIN = 25
    LED_COUNT = 10

    # WS2812 / SK6812 compatible timing
    TIMING = (400, 850, 800, 450)

    def __init__(self):

        self.available = False
        self.pin = None

        self.pixels = [
            (0, 0, 0)
            for _ in range(self.LED_COUNT)
        ]

        self.brightness = 0.65

        try:

            if RGB_AVAILABLE:

                self.pin = Pin(
                    self.LED_PIN,
                    Pin.OUT
                )

                self.available = True

                print(
                    "[RGB] Raw SK6812 driver ready"
                )

                print(
                    "[RGB] GPIO:",
                    self.LED_PIN
                )

                print(
                    "[RGB] LEDs:",
                    self.LED_COUNT
                )

        except Exception as e:

            print(
                "[RGB] Initialization error:",
                e
            )

    # --------------------------------------------------------

    def set_brightness(self, brightness):

        self.brightness = clamp(
            brightness,
            0.0,
            1.0
        )

    # --------------------------------------------------------

    def set_pixel(self, index, r, g, b):

        if index < 0:
            return

        if index >= self.LED_COUNT:
            return

        self.pixels[index] = (

            int(clamp(r, 0, 255)),

            int(clamp(g, 0, 255)),

            int(clamp(b, 0, 255))

        )

    # --------------------------------------------------------

    def fill(self, r, g, b):

        color = (

            int(clamp(r, 0, 255)),

            int(clamp(g, 0, 255)),

            int(clamp(b, 0, 255))

        )

        for i in range(self.LED_COUNT):

            self.pixels[i] = color

    # --------------------------------------------------------

    def clear(self):

        self.fill(0, 0, 0)

    # --------------------------------------------------------

    def show(self):

        if not self.available:
            return

        try:

            data = bytearray()

            for r, g, b in self.pixels:

                r = int(r * self.brightness)
                g = int(g * self.brightness)
                b = int(b * self.brightness)

                # SK6812 GRB byte order
                data.append(g)
                data.append(r)
                data.append(b)

            bitstream(

                self.pin,

                0,

                self.TIMING,

                data

            )

        except Exception as e:

            print(
                "[RGB] Show error:",
                e
            )

    # --------------------------------------------------------

    def left_bar(self, r, g, b):

        for i in range(5):

            self.set_pixel(
                i,
                r,
                g,
                b
            )

    # --------------------------------------------------------

    def right_bar(self, r, g, b):

        for i in range(5, 10):

            self.set_pixel(
                i,
                r,
                g,
                b
            )


# ============================================================
# FACE ENGINE
# ============================================================

class FaceEngine:

    SCREEN_WIDTH = 320
    SCREEN_HEIGHT = 240

    BACKGROUND = 0x0000

    # Eye color
    EYE_COLOR = 0xAFFF

    def __init__(self):

        self.display = None
        self.available = False

        # ------------------------------------------------
        # CURRENT EYE GEOMETRY
        # ------------------------------------------------

        self.left_x = 92
        self.left_y = 115

        self.right_x = 228
        self.right_y = 115

        self.left_w = 72
        self.left_h = 88

        self.right_w = 72
        self.right_h = 88

        # ------------------------------------------------
        # TARGET GEOMETRY
        # ------------------------------------------------

        self.target_left_x = self.left_x
        self.target_left_y = self.left_y

        self.target_right_x = self.right_x
        self.target_right_y = self.right_y

        self.target_left_w = self.left_w
        self.target_left_h = self.left_h

        self.target_right_w = self.right_w
        self.target_right_h = self.right_h

        # ------------------------------------------------
        # BLINK
        # ------------------------------------------------

        self.eye_open = 1.0
        self.target_eye_open = 1.0

        self.blinking = False

        self.last_blink = time.ticks_ms()

        self.next_blink = 2800

        # ------------------------------------------------
        # GAZE
        # ------------------------------------------------

        self.gaze_x = 0
        self.gaze_y = 0

        self.target_gaze_x = 0
        self.target_gaze_y = 0

        self.last_gaze_change = time.ticks_ms()

        # ------------------------------------------------
        # IDLE BREATHING
        # ------------------------------------------------

        self.phase = 0.0

        # ------------------------------------------------
        # FRAME CONTROL
        # ------------------------------------------------

        self.last_frame = 0
        self.frame_interval = 33

        # ------------------------------------------------

        self._initialize()

    # ====================================================

    def _initialize(self):

        if not M5_AVAILABLE:
            return

        try:

            M5.begin()

            self.display = M5.Display

            self.display.setBrightness(255)

            self.display.fillScreen(
                self.BACKGROUND
            )

            self.available = True

            print(
                "[FACE] Core2 display ready"
            )

        except Exception as e:

            print(
                "[FACE] Display init error:",
                e
            )

    # ====================================================
    # DISPLAY HELPERS
    # ====================================================

    def _fill_round_eye(
        self,
        x,
        y,
        width,
        height,
        color
    ):

        if not self.display:
            return

        try:

            x = int(x - width / 2)
            y = int(y - height / 2)

            radius = int(
                min(width, height) / 2
            )

            self.display.fillRoundRect(

                x,
                y,

                int(width),
                int(height),

                radius,

                color

            )

        except Exception:

            # Fallback if round rect behaves differently
            try:

                self.display.fillEllipse(

                    int(x),
                    int(y),

                    int(width / 2),
                    int(height / 2),

                    color

                )

            except Exception:
                pass

    # ====================================================
    # BLINK SYSTEM
    # ====================================================

    def _update_blink(self, now):

        elapsed = time.ticks_diff(
            now,
            self.last_blink
        )

        if not self.blinking:

            if elapsed >= self.next_blink:

                self.blinking = True

                self.target_eye_open = 0.08

        else:

            if self.eye_open <= 0.15:

                self.target_eye_open = 1.0

            elif self.eye_open >= 0.92:

                self.blinking = False

                self.last_blink = now

                # Natural variation
                self.next_blink = (
                    2200 +
                    int(
                        (math.sin(
                            self.phase * 0.37
                        ) + 1)
                        * 1000
                    )
                )

    # ====================================================
    # IDLE GAZE
    # ====================================================

    def _update_gaze(self, now):

        elapsed = time.ticks_diff(
            now,
            self.last_gaze_change
        )

        if elapsed > 2200:

            self.last_gaze_change = now

            wave_a = math.sin(
                self.phase * 0.73
            )

            wave_b = math.cos(
                self.phase * 0.47
            )

            self.target_gaze_x = (
                wave_a * 5
            )

            self.target_gaze_y = (
                wave_b * 3
            )

        self.gaze_x = lerp(
            self.gaze_x,
            self.target_gaze_x,
            0.025
        )

        self.gaze_y = lerp(
            self.gaze_y,
            self.target_gaze_y,
            0.025
        )

    # ====================================================
    # ANIMATION INTERPOLATION
    # ====================================================

    def _interpolate(self):

        speed = 0.14

        self.left_x = lerp(
            self.left_x,
            self.target_left_x,
            speed
        )

        self.left_y = lerp(
            self.left_y,
            self.target_left_y,
            speed
        )

        self.right_x = lerp(
            self.right_x,
            self.target_right_x,
            speed
        )

        self.right_y = lerp(
            self.right_y,
            self.target_right_y,
            speed
        )

        self.left_w = lerp(
            self.left_w,
            self.target_left_w,
            speed
        )

        self.left_h = lerp(
            self.left_h,
            self.target_left_h,
            speed
        )

        self.right_w = lerp(
            self.right_w,
            self.target_right_w,
            speed
        )

        self.right_h = lerp(
            self.right_h,
            self.target_right_h,
            speed
        )

        self.eye_open = lerp(
            self.eye_open,
            self.target_eye_open,
            0.32
        )

    # ====================================================
    # DRAW
    # ====================================================

    def render(self):

        if not self.available:
            return

        try:

            # Clear frame
            self.display.fillScreen(
                self.BACKGROUND
            )

            # ------------------------------------------------
            # BREATHING
            # ------------------------------------------------

            breath = math.sin(
                self.phase
            )

            breathing_offset = (
                breath * 2
            )

            # ------------------------------------------------
            # EYE OPENING
            # ------------------------------------------------

            opening = clamp(
                self.eye_open,
                0.05,
                1.0
            )

            left_h = (
                self.left_h *
                opening
            )

            right_h = (
                self.right_h *
                opening
            )

            # ------------------------------------------------
            # DRAW LEFT EYE
            # ------------------------------------------------

            self._fill_round_eye(

                self.left_x +
                self.gaze_x,

                self.left_y +
                self.gaze_y +
                breathing_offset,

                self.left_w,

                left_h,

                self.EYE_COLOR

            )

            # ------------------------------------------------
            # DRAW RIGHT EYE
            # ------------------------------------------------

            self._fill_round_eye(

                self.right_x +
                self.gaze_x,

                self.right_y +
                self.gaze_y +
                breathing_offset,

                self.right_w,

                right_h,

                self.EYE_COLOR

            )

        except Exception as e:

            print(
                "[FACE] Render error:",
                e
            )

    # ====================================================
    # STATE PRESETS
    # ====================================================

    def set_expression(self, state):

        # Reset eye openness

        self.target_eye_open = 1.0

        # ------------------------------------------------
        # IDLE
        # ------------------------------------------------

        if state == "idle":

            self.target_left_x = 92
            self.target_left_y = 115

            self.target_right_x = 228
            self.target_right_y = 115

            self.target_left_w = 72
            self.target_left_h = 88

            self.target_right_w = 72
            self.target_right_h = 88

        # ------------------------------------------------
        # HAPPY
        # ------------------------------------------------

        elif state == "happy":

            self.target_left_x = 92
            self.target_left_y = 112

            self.target_right_x = 228
            self.target_right_y = 112

            self.target_left_w = 76
            self.target_left_h = 70

            self.target_right_w = 76
            self.target_right_h = 70

        # ------------------------------------------------
        # LISTENING
        # ------------------------------------------------

        elif state == "listening":

            self.target_left_x = 92
            self.target_left_y = 112

            self.target_right_x = 228
            self.target_right_y = 112

            self.target_left_w = 80
            self.target_left_h = 98

            self.target_right_w = 80
            self.target_right_h = 98

        # ------------------------------------------------
        # THINKING
        # ------------------------------------------------

        elif state == "thinking":

            self.target_left_x = 88
            self.target_left_y = 110

            self.target_right_x = 224
            self.target_right_y = 105

            self.target_left_w = 66
            self.target_left_h = 72

            self.target_right_w = 62
            self.target_right_h = 82

        # ------------------------------------------------
        # CURIOUS
        # ------------------------------------------------

        elif state == "curious":

            self.target_left_x = 92
            self.target_left_y = 108

            self.target_right_x = 228
            self.target_right_y = 118

            self.target_left_w = 70
            self.target_left_h = 92

            self.target_right_w = 78
            self.target_right_h = 70

        # ------------------------------------------------
        # SPEAKING
        # ------------------------------------------------

        elif state == "speaking":

            pulse = (
                math.sin(
                    self.phase * 3
                ) * 5
            )

            self.target_left_w = (
                76 + pulse
            )

            self.target_right_w = (
                76 + pulse
            )

            self.target_left_h = 82
            self.target_right_h = 82

        # ------------------------------------------------
        # ALERT
        # ------------------------------------------------

        elif state == "alert":

            self.target_left_w = 82
            self.target_left_h = 58

            self.target_right_w = 82
            self.target_right_h = 58

        # ------------------------------------------------
        # SLEEPING
        # ------------------------------------------------

        elif state == "sleeping":

            self.target_left_w = 72
            self.target_left_h = 10

            self.target_right_w = 72
            self.target_right_h = 10

        # ------------------------------------------------
        # EXCITED
        # ------------------------------------------------

        elif state == "excited":

            self.target_left_w = 88
            self.target_left_h = 105

            self.target_right_w = 88
            self.target_right_h = 105

        else:

            # Unknown -> idle

            self.set_expression(
                "idle"
            )

    # ====================================================
    # UPDATE
    # ====================================================

    def update(self, now):

        if not self.available:
            return

        elapsed = time.ticks_diff(
            now,
            self.last_frame
        )

        if elapsed < self.frame_interval:
            return

        self.last_frame = now

        # Advance animation phase
        self.phase += 0.055

        # Natural systems
        self._update_blink(now)

        self._update_gaze(now)

        # Smooth transitions
        self._interpolate()

        # Render frame
        self.render()


# ============================================================
# SATURDAY EXPRESSION ENGINE
# ============================================================

class ExpressionEngine:

    def __init__(self, config=None):

        print(
            "[EXPRESSION] Initializing embodiment engine..."
        )

        self.config = config

        # ------------------------------------------------
        # STATE
        # ------------------------------------------------

        self.state = "idle"

        self.previous_state = None

        self.state_changed = (
            time.ticks_ms()
        )

        # ------------------------------------------------
        # ENGINES
        # ------------------------------------------------

        self.face = FaceEngine()

        self.rgb = RGBController()

        # ------------------------------------------------
        # RGB ANIMATION
        # ------------------------------------------------

        self.rgb_phase = 0.0

        self.last_rgb_frame = 0

        self.rgb_frame_interval = 45

        # ------------------------------------------------

        print(
            "[EXPRESSION] Embodiment engine ready"
        )

    # ====================================================
    # STATE
    # ====================================================

    def set_state(self, state):

        if state == self.state:
            return

        old_state = self.state

        self.previous_state = old_state

        self.state = state

        self.state_changed = (
            time.ticks_ms()
        )

        print(
            "[EXPRESSION] State:",
            old_state,
            "->",
            state
        )

        self.face.set_expression(
            state
        )

    # Compatibility aliases

    def set_expression(self, state):
        self.set_state(state)

    def express(self, state):
        self.set_state(state)

    # ====================================================
    # RGB RENDERING
    # ====================================================

    def _update_rgb(self, now):

        if not self.rgb.available:
            return

        elapsed = time.ticks_diff(
            now,
            self.last_rgb_frame
        )

        if elapsed < self.rgb_frame_interval:
            return

        self.last_rgb_frame = now

        self.rgb_phase += 0.12

        phase = self.rgb_phase

        # ------------------------------------------------
        # IDLE
        # Soft cyan breathing
        # ------------------------------------------------

        if self.state == "idle":

            level = int(
                25 +
                (
                    (math.sin(phase) + 1)
                    * 20
                )
            )

            self.rgb.fill(
                0,
                level,
                int(level * 1.8)
            )

        # ------------------------------------------------
        # HAPPY
        # Green / warm cyan
        # ------------------------------------------------

        elif self.state == "happy":

            pulse = int(
                80 +
                (
                    (math.sin(phase * 1.5) + 1)
                    * 50
                )
            )

            self.rgb.fill(
                int(pulse * 0.2),
                pulse,
                int(pulse * 0.7)
            )

        # ------------------------------------------------
        # LISTENING
        # Blue pulse
        # ------------------------------------------------

        elif self.state == "listening":

            pulse = int(
                60 +
                (
                    (math.sin(phase * 2) + 1)
                    * 70
                )
            )

            self.rgb.fill(
                0,
                int(pulse * 0.45),
                pulse
            )

        # ------------------------------------------------
        # THINKING
        # Purple traveling energy
        # ------------------------------------------------

        elif self.state == "thinking":

            self.rgb.clear()

            position = int(
                (phase * 2) %
                self.rgb.LED_COUNT
            )

            for offset in range(3):

                index = (
                    position + offset
                ) % self.rgb.LED_COUNT

                intensity = (
                    220 -
                    offset * 60
                )

                self.rgb.set_pixel(

                    index,

                    intensity,

                    0,

                    255

                )

        # ------------------------------------------------
        # CURIOUS
        # Cyan / purple split
        # ------------------------------------------------

        elif self.state == "curious":

            pulse = int(
                80 +
                math.sin(phase * 1.7)
                * 40
            )

            self.rgb.left_bar(
                0,
                pulse,
                255
            )

            self.rgb.right_bar(
                pulse,
                0,
                255
            )

        # ------------------------------------------------
        # SPEAKING
        # Alternating symmetrical pulse
        # ------------------------------------------------

        elif self.state == "speaking":

            wave = (
                math.sin(
                    phase * 3
                ) + 1
            ) / 2

            for i in range(5):

                intensity = int(
                    70 +
                    wave *
                    (
                        140 -
                        i * 15
                    )
                )

                self.rgb.set_pixel(
                    i,
                    0,
                    intensity,
                    255
                )

                self.rgb.set_pixel(
                    9 - i,
                    0,
                    intensity,
                    255
                )

        # ------------------------------------------------
        # ALERT
        # Amber
        # ------------------------------------------------

        elif self.state == "alert":

            pulse = int(
                120 +
                (
                    math.sin(phase * 3)
                    + 1
                ) * 60
            )

            self.rgb.fill(
                pulse,
                int(pulse * 0.45),
                0
            )

        # ------------------------------------------------
        # EXCITED
        # Bright cyan
        # ------------------------------------------------

        elif self.state == "excited":

            pulse = int(
                140 +
                (
                    math.sin(phase * 4)
                    + 1
                ) * 50
            )

            self.rgb.fill(
                0,
                pulse,
                255
            )

        # ------------------------------------------------
        # SLEEPING
        # Dim blue
        # ------------------------------------------------

        elif self.state == "sleeping":

            level = int(
                8 +
                (
                    math.sin(phase * 0.4)
                    + 1
                ) * 8
            )

            self.rgb.fill(
                0,
                0,
                level * 3
            )

        # ------------------------------------------------
        # ERROR
        # Red pulse
        # ------------------------------------------------

        elif self.state == "error":

            pulse = int(
                80 +
                (
                    math.sin(phase * 5)
                    + 1
                ) * 80
            )

            self.rgb.fill(
                pulse,
                0,
                0
            )

        # ------------------------------------------------
        # DEFAULT
        # ------------------------------------------------

        else:

            self.rgb.fill(
                0,
                40,
                80
            )

        self.rgb.show()

    # ====================================================
    # WAKE
    # ====================================================

    def wake(self):

        print(
            "[EXPRESSION] SATURDAY awake"
        )

        self.set_state(
            "happy"
        )

        # Initial RGB energy
        if self.rgb.available:

            self.rgb.clear()

            self.rgb.show()

    # ====================================================
    # SLEEP
    # ====================================================

    def sleep(self):

        self.set_state(
            "sleeping"
        )

    # ====================================================
    # UPDATE
    # ====================================================

    def update(self):

        now = time.ticks_ms()

        # Face engine
        self.face.update(now)

        # RGB engine
        self._update_rgb(now)

    # ====================================================
    # STATUS
    # ====================================================

    def status(self):

        return {

            "state":
                self.state,

            "display":
                self.face.available,

            "rgb":
                self.rgb.available,

            "rgb_led_count":
                self.rgb.LED_COUNT

        }


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

Expression = ExpressionEngine
ExpressionManager = ExpressionEngine
EmbodimentEngine = ExpressionEngine