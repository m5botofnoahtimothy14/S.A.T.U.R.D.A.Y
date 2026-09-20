# ============================================================
# SATURDAY HOME BOT - UTILITY FUNCTIONS
# Firmware V3
#
# Pure utility layer.
# No hardware access.
# No MQTT.
# No display access.
# ============================================================

import time
import math


# ============================================================
# TIME
# ============================================================

def ticks_ms():
    """Return current monotonic time in milliseconds."""
    return time.ticks_ms()


def ticks_diff(new, old):
    """Safe MicroPython tick difference."""
    return time.ticks_diff(new, old)


def elapsed_ms(start_ms):
    """Milliseconds elapsed since start_ms."""
    return time.ticks_diff(time.ticks_ms(), start_ms)


def interval_elapsed(last_ms, interval_ms):
    """Return True when an interval has elapsed."""
    return time.ticks_diff(time.ticks_ms(), last_ms) >= interval_ms


# ============================================================
# BASIC MATH
# ============================================================

def clamp(value, minimum, maximum):
    """Clamp value between minimum and maximum."""
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def lerp(start, end, amount):
    """
    Linear interpolation.

    amount:
        0.0 -> start
        1.0 -> end
    """
    return start + (end - start) * amount


def smooth_step(start, end, amount):
    """Smooth interpolation using smoothstep."""
    amount = clamp(amount, 0.0, 1.0)
    amount = amount * amount * (3.0 - 2.0 * amount)
    return lerp(start, end, amount)


def map_range(value, in_min, in_max, out_min, out_max):
    """Map a value from one range into another."""
    if in_max == in_min:
        return out_min

    ratio = (value - in_min) / (in_max - in_min)

    return out_min + ratio * (out_max - out_min)


def deadband(value, threshold):
    """Return zero when value is inside threshold."""
    if abs(value) < threshold:
        return 0
    return value


# ============================================================
# ANGLES
# ============================================================

def normalize_angle(angle):
    """
    Normalize degrees to -180 .. +180.
    """
    while angle > 180:
        angle -= 360

    while angle <= -180:
        angle += 360

    return angle


def normalize_angle_360(angle):
    """
    Normalize degrees to 0 .. 360.
    """
    angle = angle % 360

    if angle < 0:
        angle += 360

    return angle


def angle_difference(target, current):
    """
    Smallest angular difference.

    Positive = clockwise/right
    Negative = counter-clockwise/left
    """
    return normalize_angle(target - current)


def degrees_to_radians(angle):
    return angle * math.pi / 180.0


def radians_to_degrees(angle):
    return angle * 180.0 / math.pi


# ============================================================
# DISTANCE / POSITION
# ============================================================

def distance_2d(x1, y1, x2, y2):
    """Euclidean distance between two 2D points."""
    dx = x2 - x1
    dy = y2 - y1

    return math.sqrt(dx * dx + dy * dy)


def heading_to_point(x1, y1, x2, y2):
    """
    Calculate heading in degrees from point A to point B.
    """
    dx = x2 - x1
    dy = y2 - y1

    return normalize_angle_360(
        radians_to_degrees(math.atan2(dy, dx))
    )


def project_position(x, y, heading_deg, distance):
    """
    Move a point forward by distance using heading.

    Returns:
        (new_x, new_y)
    """
    heading = degrees_to_radians(heading_deg)

    new_x = x + math.cos(heading) * distance
    new_y = y + math.sin(heading) * distance

    return new_x, new_y


# ============================================================
# SMOOTHING
# ============================================================

class MovingAverage:
    """
    Lightweight moving average filter.

    Designed for:
        ultrasonic readings
        microphone levels
        IMU smoothing
        sensor noise reduction
    """

    def __init__(self, size=5):
        self.size = max(1, int(size))
        self.values = []
        self.total = 0.0

    def add(self, value):
        value = float(value)

        self.values.append(value)
        self.total += value

        if len(self.values) > self.size:
            removed = self.values.pop(0)
            self.total -= removed

        return self.value()

    def value(self):
        if not self.values:
            return 0.0

        return self.total / len(self.values)

    def reset(self):
        self.values = []
        self.total = 0.0

    def count(self):
        return len(self.values)


class ExponentialFilter:
    """
    Exponential smoothing filter.

    alpha:
        closer to 1 = faster response
        closer to 0 = smoother response
    """

    def __init__(self, alpha=0.25):
        self.alpha = clamp(alpha, 0.0, 1.0)
        self.initialized = False
        self.current = 0.0

    def update(self, value):
        value = float(value)

        if not self.initialized:
            self.current = value
            self.initialized = True
        else:
            self.current = (
                self.alpha * value +
                (1.0 - self.alpha) * self.current
            )

        return self.current

    def value(self):
        return self.current

    def reset(self):
        self.initialized = False
        self.current = 0.0


# ============================================================
# RATE LIMITING
# ============================================================

class RateLimiter:
    """
    Limits how frequently something may execute.

    Example:

        if telemetry_limiter.ready():
            publish()
    """

    def __init__(self, interval_ms):
        self.interval_ms = int(interval_ms)
        self.last_time = time.ticks_ms()

    def ready(self):
        now = time.ticks_ms()

        if time.ticks_diff(now, self.last_time) >= self.interval_ms:
            self.last_time = now
            return True

        return False

    def reset(self):
        self.last_time = time.ticks_ms()


class Cooldown:
    """
    Simple cooldown timer.
    """

    def __init__(self, cooldown_ms):
        self.cooldown_ms = int(cooldown_ms)
        self.last_trigger = None

    def ready(self):
        if self.last_trigger is None:
            return True

        return elapsed_ms(self.last_trigger) >= self.cooldown_ms

    def trigger(self):
        self.last_trigger = time.ticks_ms()

    def reset(self):
        self.last_trigger = None


# ============================================================
# VALUE CHANGE DETECTION
# ============================================================

class ChangeDetector:
    """
    Detect significant changes in a numeric value.

    Useful for:
        sensor events
        microphone activity
        battery changes
        IMU motion
    """

    def __init__(self, threshold=1.0):
        self.threshold = float(threshold)
        self.last_value = None

    def update(self, value):
        value = float(value)

        if self.last_value is None:
            self.last_value = value
            return True

        changed = abs(value - self.last_value) >= self.threshold

        if changed:
            self.last_value = value

        return changed

    def value(self):
        return self.last_value

    def reset(self):
        self.last_value = None


# ============================================================
# SAFE INTENT HELPERS
# ============================================================

def create_intent(
    action,
    priority,
    source="unknown",
    timeout_ms=2000,
    data=None
):
    """
    Create a standard SATURDAY decision intent.

    Runtime's Decision Arbiter will compare these.
    """

    now = time.ticks_ms()

    if data is None:
        data = {}

    return {
        "action": action,
        "priority": int(priority),
        "source": source,
        "created_ms": now,
        "timeout_ms": int(timeout_ms),
        "data": data
    }


def intent_expired(intent):
    """
    Check whether an intent is stale.
    """

    if not intent:
        return True

    created = intent.get("created_ms", 0)
    timeout = intent.get("timeout_ms", 0)

    if timeout <= 0:
        return False

    return elapsed_ms(created) >= timeout


def intent_valid(intent):
    """True if intent exists and has not expired."""
    return intent is not None and not intent_expired(intent)


# ============================================================
# SAFE VALUE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_bool(value, default=False):
    """
    Convert common values into boolean safely.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.lower().strip()

        if value in ("true", "1", "yes", "on"):
            return True

        if value in ("false", "0", "no", "off"):
            return False

    if isinstance(value, (int, float)):
        return value != 0

    return default


# ============================================================
# DICTIONARY HELPERS
# ============================================================

def dict_get(data, key, default=None):
    """
    Safe dictionary access.
    """
    try:
        return data.get(key, default)
    except Exception:
        return default


def merge_dict(base, update):
    """
    Lightweight dictionary merge.

    Returns a new dictionary.
    """
    result = {}

    if base:
        for key in base:
            result[key] = base[key]

    if update:
        for key in update:
            result[key] = update[key]

    return result


# ============================================================
# POSE HELPERS
# ============================================================

def create_pose(x=0.0, y=0.0, heading=0.0):
    """
    Standard SATURDAY pose object.
    """
    return {
        "x": float(x),
        "y": float(y),
        "heading": normalize_angle_360(float(heading))
    }


def copy_pose(pose):
    """
    Create safe copy of pose.
    """
    if pose is None:
        return create_pose()

    return create_pose(
        pose.get("x", 0.0),
        pose.get("y", 0.0),
        pose.get("heading", 0.0)
    )


def pose_distance(pose_a, pose_b):
    """
    Distance between two SATURDAY poses.
    """
    if pose_a is None or pose_b is None:
        return 0.0

    return distance_2d(
        pose_a.get("x", 0.0),
        pose_a.get("y", 0.0),
        pose_b.get("x", 0.0),
        pose_b.get("y", 0.0)
    )


# ============================================================
# DEBUG
# ============================================================

def format_pose(pose):
    """
    Human-readable pose.
    """
    if pose is None:
        return "Pose(None)"

    return (
        "Pose(x={:.2f}, y={:.2f}, heading={:.1f})"
    ).format(
        pose.get("x", 0.0),
        pose.get("y", 0.0),
        pose.get("heading", 0.0)
    )


def format_intent(intent):
    """
    Human-readable intent for debugging.
    """
    if intent is None:
        return "Intent(None)"

    return (
        "Intent(action={}, priority={}, source={})"
    ).format(
        intent.get("action", "unknown"),
        intent.get("priority", 0),
        intent.get("source", "unknown")
    )