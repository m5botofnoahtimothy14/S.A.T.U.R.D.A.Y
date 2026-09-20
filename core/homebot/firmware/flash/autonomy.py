"""
============================================================
SATURDAY AUTONOMY
Navigation, Return-Home & Behaviour Controller
============================================================

Responsibilities:
- Autonomous behaviour state machine
- Return-to-home navigation
- Coordinate navigation
- Heading correction
- Obstacle avoidance
- Dock approach behaviour
- Localization-aware navigation
- Safe navigation degradation

IMPORTANT:

Autonomy DOES NOT directly control motors.

It only produces movement intents:

{
    "action": "forward",
    "speed": 40
}

Runtime remains the single motor execution authority.

============================================================
"""

import time
import math
import gc


# ============================================================
# AUTONOMY STATES
# ============================================================

STATE_IDLE = "idle"
STATE_EXPLORE = "explore"
STATE_NAVIGATE = "navigate"
STATE_RETURN_HOME = "return_home"
STATE_DOCK_APPROACH = "dock_approach"
STATE_DOCKED = "docked"
STATE_AVOIDING = "avoiding"
STATE_PAUSED = "paused"
STATE_ERROR = "error"


# ============================================================
# NAVIGATION SETTINGS
# ============================================================

DEFAULT_SPEED = 40
SLOW_SPEED = 25
ROTATE_SPEED = 30
DOCK_SPEED = 20

HEADING_TOLERANCE = 12.0
POSITION_TOLERANCE = 0.35
HOME_APPROACH_RADIUS = 1.5
DOCKING_RADIUS = 0.45

OBSTACLE_DISTANCE_CM = 20
CRITICAL_OBSTACLE_DISTANCE_CM = 12

MIN_LOCALIZATION_CONFIDENCE = 0.25
GOOD_LOCALIZATION_CONFIDENCE = 0.45

AVOIDANCE_DURATION_MS = 900
ROTATION_TIMEOUT_MS = 3000
NAVIGATION_TIMEOUT_MS = 120000


class Autonomy:
    """
    SATURDAY Autonomous Behaviour Controller.

    This module decides WHERE SATURDAY should go.

    Runtime decides whether movement is physically allowed.
    """

    def __init__(
        self,
        localization=None,
        config=None
    ):

        print("[AUTONOMY] Initializing autonomous brain...")

        self.localization = localization
        self.config = config

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.state = STATE_IDLE

        self.previous_state = STATE_IDLE

        self.enabled = True

        self.paused = False

        # ----------------------------------------------------
        # NAVIGATION TARGET
        # ----------------------------------------------------

        self.target = None

        self.target_name = None

        self.navigation_started = 0

        # ----------------------------------------------------
        # RETURN HOME
        # ----------------------------------------------------

        self.returning_home = False

        self.home_target = None

        # ----------------------------------------------------
        # AVOIDANCE
        # ----------------------------------------------------

        self.avoiding_obstacle = False

        self.avoidance_started = 0

        self.avoidance_direction = None

        # ----------------------------------------------------
        # MOTION MEMORY
        # ----------------------------------------------------

        self.last_action = "stop"

        self.last_speed = 0

        self.last_command_time = 0

        # ----------------------------------------------------
        # SENSOR CACHE
        # ----------------------------------------------------

        self.sensors = {}

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.stats = {

            "updates": 0,

            "navigation_requests": 0,

            "return_home_requests": 0,

            "obstacles_avoided": 0,

            "successful_arrivals": 0,

            "localization_failures": 0

        }

        print("[AUTONOMY] Autonomous brain ready")

    # ========================================================
    # CONFIG
    # ========================================================

    def _get_config(
        self,
        key,
        default
    ):

        if self.config is None:
            return default

        try:

            if isinstance(
                self.config,
                dict
            ):

                return self.config.get(
                    key,
                    default
                )

            return getattr(
                self.config,
                key,
                default
            )

        except Exception:

            return default

    # ========================================================
    # STATE MANAGEMENT
    # ========================================================

    def set_state(
        self,
        state
    ):

        if state == self.state:
            return

        self.previous_state = self.state

        self.state = state

        print(
            "[AUTONOMY] State:",
            self.previous_state,
            "->",
            state
        )

    # ========================================================
    # ENABLE / DISABLE
    # ========================================================

    def enable(self):

        self.enabled = True

        self.paused = False

        print("[AUTONOMY] Enabled")

        return True

    def disable(self):

        self.enabled = False

        self.paused = True

        self.set_state(
            STATE_PAUSED
        )

        return True

    def pause(self):

        self.paused = True

        self.set_state(
            STATE_PAUSED
        )

        return True

    def resume(self):

        self.paused = False

        self.enabled = True

        self.set_state(
            STATE_IDLE
        )

        return True

    # ========================================================
    # COMMAND RESULT
    # ========================================================

    def _command(
        self,
        action,
        speed=DEFAULT_SPEED
    ):

        self.last_action = action

        self.last_speed = speed

        self.last_command_time = (
            time.ticks_ms()
        )

        return {

            "action": action,

            "speed": speed

        }

    # ========================================================
    # STOP COMMAND
    # ========================================================

    def _stop(self):

        return self._command(
            "stop",
            0
        )

    # ========================================================
    # LOCALIZATION ACCESS
    # ========================================================

    def _get_position(self):

        if not self.localization:
            return None

        try:

            getter = getattr(
                self.localization,
                "get_position",
                None
            )

            if callable(getter):

                return getter()

        except Exception:

            pass

        return None

    # ========================================================
    # LOCALIZATION HEALTH
    # ========================================================

    def _localization_confidence(self):

        position = self._get_position()

        if not position:
            return 0.0

        try:

            return float(
                position.get(
                    "confidence",
                    0.0
                )
            )

        except Exception:

            return 0.0

    # ========================================================
    # NAVIGATION TARGET
    # ========================================================

    def navigate_to(
        self,
        target,
        name="target"
    ):

        if not isinstance(
            target,
            dict
        ):

            return False

        try:

            x = float(
                target.get(
                    "x"
                )
            )

            y = float(
                target.get(
                    "y"
                )
            )

        except Exception:

            return False

        self.target = {

            "x": x,

            "y": y,

            "heading": float(
                target.get(
                    "heading",
                    0.0
                )
            )

        }

        self.target_name = name

        self.navigation_started = (
            time.ticks_ms()
        )

        self.stats[
            "navigation_requests"
        ] += 1

        self.set_state(
            STATE_NAVIGATE
        )

        print(
            "[AUTONOMY] Navigating to:",
            name,
            self.target
        )

        return True

    # ========================================================
    # RETURN HOME
    # ========================================================

    def return_home(
        self,
        home_position=None
    ):

        if home_position is None:

            if not self.localization:

                print(
                    "[AUTONOMY] No localization system"
                )

                return False

            try:

                home_position = (
                    self.localization.get_home()
                )

            except Exception:

                home_position = None

        if not isinstance(
            home_position,
            dict
        ):

            print(
                "[AUTONOMY] Home position unavailable"
            )

            return False

        self.home_target = dict(
            home_position
        )

        self.target = {

            "x": float(
                home_position.get(
                    "x",
                    0.0
                )
            ),

            "y": float(
                home_position.get(
                    "y",
                    0.0
                )
            ),

            "heading": float(
                home_position.get(
                    "heading",
                    0.0
                )
            )

        }

        self.target_name = "home"

        self.returning_home = True

        self.navigation_started = (
            time.ticks_ms()
        )

        self.stats[
            "return_home_requests"
        ] += 1

        self.set_state(
            STATE_RETURN_HOME
        )

        print(
            "[AUTONOMY] Return-home initiated"
        )

        return True

    # ========================================================
    # CANCEL NAVIGATION
    # ========================================================

    def cancel_navigation(self):

        self.target = None

        self.target_name = None

        self.returning_home = False

        self.home_target = None

        self.set_state(
            STATE_IDLE
        )

        return self._stop()

    # ========================================================
    # DISTANCE TO TARGET
    # ========================================================

    def _distance_to_target(self):

        if not self.localization:
            return None

        if not self.target:
            return None

        try:

            distance = getattr(
                self.localization,
                "distance_to",
                None
            )

            if callable(distance):

                return distance(
                    self.target
                )

        except Exception:

            pass

        return None

    # ========================================================
    # HEADING ERROR
    # ========================================================

    def _heading_error_to_target(self):

        if not self.localization:
            return None

        if not self.target:
            return None

        try:

            getter = getattr(
                self.localization,
                "heading_error_to",
                None
            )

            if callable(getter):

                return getter(
                    self.target
                )

        except Exception:

            pass

        return None

    # ========================================================
    # OBSTACLE DETECTION
    # ========================================================

    def _obstacle_distance(self):

        try:

            distance = self.sensors.get(
                "distance"
            )

            if distance is None:
                return None

            return float(
                distance
            )

        except Exception:

            return None

    def _obstacle_detected(self):

        distance = self._obstacle_distance()

        if distance is None:
            return False

        if distance <= 0:
            return False

        return (
            distance
            < OBSTACLE_DISTANCE_CM
        )

    def _critical_obstacle(self):

        distance = self._obstacle_distance()

        if distance is None:
            return False

        if distance <= 0:
            return False

        return (
            distance
            < CRITICAL_OBSTACLE_DISTANCE_CM
        )

    # ========================================================
    # OBSTACLE AVOIDANCE
    # ========================================================

    def _start_avoidance(self):

        self.avoiding_obstacle = True

        self.avoidance_started = (
            time.ticks_ms()
        )

        self.stats[
            "obstacles_avoided"
        ] += 1

        if self.last_action in [

            "strafe_left",
            "rotate_left"

        ]:

            self.avoidance_direction = (
                "strafe_right"
            )

        else:

            self.avoidance_direction = (
                "strafe_left"
            )

        self.set_state(
            STATE_AVOIDING
        )

        print(
            "[AUTONOMY] Avoiding obstacle"
        )

    def _update_avoidance(self):

        now = time.ticks_ms()

        elapsed = time.ticks_diff(

            now,

            self.avoidance_started

        )

        if elapsed < AVOIDANCE_DURATION_MS:

            return self._command(

                self.avoidance_direction,

                SLOW_SPEED

            )

        self.avoiding_obstacle = False

        if self.returning_home:

            self.set_state(
                STATE_RETURN_HOME
            )

        elif self.target:

            self.set_state(
                STATE_NAVIGATE
            )

        else:

            self.set_state(
                STATE_IDLE
            )

        return self._stop()

    # ========================================================
    # HEADING CORRECTION
    # ========================================================

    def _correct_heading(
        self,
        error
    ):

        if error is None:

            return self._stop()

        if abs(error) <= HEADING_TOLERANCE:

            return None

        if error > 0:

            return self._command(

                "rotate_right",

                ROTATE_SPEED

            )

        return self._command(

            "rotate_left",

            ROTATE_SPEED

        )

    # ========================================================
    # NAVIGATE TO TARGET
    # ========================================================

    def _navigate_target(self):

        if not self.target:

            self.set_state(
                STATE_IDLE
            )

            return self._stop()

        # ----------------------------------------------------
        # NAVIGATION TIMEOUT
        # ----------------------------------------------------

        now = time.ticks_ms()

        elapsed = time.ticks_diff(

            now,

            self.navigation_started

        )

        if elapsed > NAVIGATION_TIMEOUT_MS:

            print(
                "[AUTONOMY] Navigation timeout"
            )

            self.set_state(
                STATE_ERROR
            )

            return self._stop()

        # ----------------------------------------------------
        # LOCALIZATION HEALTH
        # ----------------------------------------------------

        confidence = (
            self._localization_confidence()
        )

        if confidence < MIN_LOCALIZATION_CONFIDENCE:

            self.stats[
                "localization_failures"
            ] += 1

            print(
                "[AUTONOMY] Localization confidence low:",
                confidence
            )

            return self._stop()

        # ----------------------------------------------------
        # OBSTACLE
        # ----------------------------------------------------

        if self._obstacle_detected():

            self._start_avoidance()

            return self._update_avoidance()

        # ----------------------------------------------------
        # DISTANCE
        # ----------------------------------------------------

        distance = (
            self._distance_to_target()
        )

        if distance is None:

            return self._stop()

        # ----------------------------------------------------
        # ARRIVED
        # ----------------------------------------------------

        if distance <= POSITION_TOLERANCE:

            print(
                "[AUTONOMY] Arrived at:",
                self.target_name
            )

            self.stats[
                "successful_arrivals"
            ] += 1

            if self.returning_home:

                self.set_state(
                    STATE_DOCK_APPROACH
                )

                return self._stop()

            self.target = None

            self.target_name = None

            self.set_state(
                STATE_IDLE
            )

            return self._stop()

        # ----------------------------------------------------
        # HEADING CORRECTION
        # ----------------------------------------------------

        heading_error = (
            self._heading_error_to_target()
        )

        correction = self._correct_heading(

            heading_error

        )

        if correction:

            return correction

        # ----------------------------------------------------
        # SPEED CONTROL
        # ----------------------------------------------------

        speed = DEFAULT_SPEED

        if distance < HOME_APPROACH_RADIUS:

            speed = SLOW_SPEED

        return self._command(

            "forward",

            speed

        )

    # ========================================================
    # RETURN HOME NAVIGATION
    # ========================================================

    def _update_return_home(self):

        if not self.localization:

            self.set_state(
                STATE_ERROR
            )

            return self._stop()

        # ----------------------------------------------------
        # CHECK FOR HOME ENVIRONMENT
        # ----------------------------------------------------

        try:

            home_confidence = (
                self.localization.home_confidence()
            )

        except Exception:

            home_confidence = 0.0

        # BLE / WiFi confirmation means SATURDAY
        # is likely physically near the dock.

        if home_confidence >= 0.8:

            self.set_state(
                STATE_DOCK_APPROACH
            )

            return self._stop()

        # Continue coordinate navigation.

        return self._navigate_target()

    # ========================================================
    # DOCK APPROACH
    # ========================================================

    def _update_dock_approach(self):

        if not self.localization:

            self.set_state(
                STATE_ERROR
            )

            return self._stop()

        # ----------------------------------------------------
        # DISTANCE TO HOME
        # ----------------------------------------------------

        distance = None

        try:

            distance = (
                self.localization.distance_to_home()
            )

        except Exception:

            pass

        # ----------------------------------------------------
        # BLE HOME CONFIRMATION
        # ----------------------------------------------------

        ble_detected = False

        try:

            ble_detected = (
                self.localization.ble_home_detected()
            )

        except Exception:

            pass

        # ----------------------------------------------------
        # DOCKED
        # ----------------------------------------------------

        if (

            distance is not None

            and

            distance <= DOCKING_RADIUS

        ):

            self.returning_home = False

            self.target = None

            self.target_name = None

            self.set_state(
                STATE_DOCKED
            )

            print(
                "[AUTONOMY] Home reached"
            )

            return self._stop()

        # ----------------------------------------------------
        # BLE CONFIRMED DOCK ZONE
        # ----------------------------------------------------

        if ble_detected:

            if self._critical_obstacle():

                self.returning_home = False

                self.target = None

                self.set_state(
                    STATE_DOCKED
                )

                print(
                    "[AUTONOMY] Dock proximity confirmed"
                )

                return self._stop()

        # ----------------------------------------------------
        # CONTINUE CAREFUL NAVIGATION
        # ----------------------------------------------------

        if self._obstacle_detected():

            if self._critical_obstacle():

                return self._stop()

            self._start_avoidance()

            return self._update_avoidance()

        heading_error = (
            self._heading_error_to_target()
        )

        correction = self._correct_heading(

            heading_error

        )

        if correction:

            return correction

        return self._command(

            "forward",

            DOCK_SPEED

        )

    # ========================================================
    # EXPLORE
    # ========================================================

    def explore(self):

        self.returning_home = False

        self.target = None

        self.target_name = None

        self.set_state(
            STATE_EXPLORE
        )

        return True

    def _update_explore(self):

        if self._obstacle_detected():

            self._start_avoidance()

            return self._update_avoidance()

        return self._command(

            "forward",

            SLOW_SPEED

        )

    # ========================================================
    # MAIN UPDATE
    # ========================================================

    def update(
        self,
        sensors=None
    ):
        """
        Main non-blocking autonomy update.

        Runtime calls this continuously.

        Returns:

        {
            "action": "...",
            "speed": ...
        }

        Runtime remains responsible for arbitration
        and actual motor execution.
        """

        self.stats[
            "updates"
        ] += 1

        if isinstance(
            sensors,
            dict
        ):

            self.sensors = sensors

        # ----------------------------------------------------
        # DISABLED
        # ----------------------------------------------------

        if not self.enabled:

            return self._stop()

        if self.paused:

            return self._stop()

        # ----------------------------------------------------
        # GLOBAL CRITICAL OBSTACLE
        # ----------------------------------------------------

        if (

            self.state
            not in [

                STATE_IDLE,

                STATE_DOCKED,

                STATE_PAUSED

            ]

            and

            self._critical_obstacle()

        ):

            self._start_avoidance()

        # ----------------------------------------------------
        # STATE MACHINE
        # ----------------------------------------------------

        if self.state == STATE_IDLE:

            return self._stop()

        if self.state == STATE_PAUSED:

            return self._stop()

        if self.state == STATE_ERROR:

            return self._stop()

        if self.state == STATE_DOCKED:

            return self._stop()

        if self.state == STATE_AVOIDING:

            return self._update_avoidance()

        if self.state == STATE_NAVIGATE:

            return self._navigate_target()

        if self.state == STATE_RETURN_HOME:

            return self._update_return_home()

        if self.state == STATE_DOCK_APPROACH:

            return self._update_dock_approach()

        if self.state == STATE_EXPLORE:

            return self._update_explore()

        return self._stop()

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        position = self._get_position()

        distance = None

        heading_error = None

        if self.target:

            distance = (
                self._distance_to_target()
            )

            heading_error = (
                self._heading_error_to_target()
            )

        return {

            "state":
                self.state,

            "previous_state":
                self.previous_state,

            "enabled":
                self.enabled,

            "paused":
                self.paused,

            "returning_home":
                self.returning_home,

            "target":
                self.target,

            "target_name":
                self.target_name,

            "position":
                position,

            "distance_to_target":
                distance,

            "heading_error":
                heading_error,

            "last_action":
                self.last_action,

            "last_speed":
                self.last_speed,

            "avoiding_obstacle":
                self.avoiding_obstacle,

            "localization_confidence":
                self._localization_confidence(),

            "stats":
                self.stats

        }

    # ========================================================
    # MEMORY MAINTENANCE
    # ========================================================

    def cleanup(self):

        try:

            gc.collect()

        except Exception:

            pass


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

AutonomyController = Autonomy

SaturdayAutonomy = Autonomy

SATURDAYAutonomy = Autonomy