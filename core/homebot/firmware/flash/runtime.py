"""
============================================================
SATURDAY RUNTIME
Central Nervous System & Motor Arbitration
============================================================

Responsibilities:

- Central subsystem scheduler
- Localization update scheduling
- Autonomy update scheduling
- Communication polling
- Expression updates
- Motor command arbitration
- Emergency stop handling
- Runtime health monitoring
- Garbage collection scheduling
- Safe startup/shutdown

ARCHITECTURE:

    COMMUNICATION ──┐
                    │
    AUTONOMY ───────┤
                    ▼
              ┌─────────────┐
              │   RUNTIME   │
              │  ARBITER    │
              └──────┬──────┘
                     │
                     ▼
                  DRIVERS
                     │
                     ▼
                   MOTORS

IMPORTANT:

No subsystem except Runtime should directly execute
movement commands.

Autonomy proposes movement.

Communication may request movement.

Runtime validates and arbitrates.

Drivers execute.

Designed for:

M5Stack Core2
MicroPython
UIFlow2

============================================================
"""

import time
import gc


# ============================================================
# RUNTIME STATES
# ============================================================

STATE_STOPPED = "stopped"
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_ERROR = "error"
STATE_SHUTTING_DOWN = "shutting_down"


# ============================================================
# MOVEMENT PRIORITIES
# ============================================================

PRIORITY_IDLE = 0
PRIORITY_AUTONOMY = 10
PRIORITY_REMOTE = 50
PRIORITY_SAFETY = 100


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_LOOP_DELAY_MS = 20

DEFAULT_LOCALIZATION_INTERVAL_MS = 50

DEFAULT_AUTONOMY_INTERVAL_MS = 50

DEFAULT_COMMUNICATION_INTERVAL_MS = 50

DEFAULT_EXPRESSION_INTERVAL_MS = 100

DEFAULT_GC_INTERVAL_MS = 30000

DEFAULT_STATUS_INTERVAL_MS = 5000

DEFAULT_MOTOR_TIMEOUT_MS = 500

DEFAULT_MAX_SPEED = 100


class Runtime:
    """
    SATURDAY Central Runtime.

    Runtime owns the execution loop.

    Every subsystem receives time through Runtime.

    Runtime is also responsible for motor arbitration.
    """

    def __init__(
        self,
        config=None,
        drivers=None,
        autonomy=None,
        communication=None,
        expression=None,
        localization=None
    ):

        print("[RUNTIME] Initializing central nervous system...")

        # ----------------------------------------------------
        # DEPENDENCIES
        # ----------------------------------------------------

        self.config = config

        self.drivers = drivers

        self.autonomy = autonomy

        self.communication = communication

        self.expression = expression

        self.localization = localization

        # ----------------------------------------------------
        # CONFIGURATION
        # ----------------------------------------------------

        self.loop_delay_ms = self._get_config(
            "runtime_loop_delay",
            DEFAULT_LOOP_DELAY_MS
        )

        self.localization_interval_ms = self._get_config(
            "localization_interval",
            DEFAULT_LOCALIZATION_INTERVAL_MS
        )

        self.autonomy_interval_ms = self._get_config(
            "autonomy_interval",
            DEFAULT_AUTONOMY_INTERVAL_MS
        )

        self.communication_interval_ms = self._get_config(
            "communication_interval",
            DEFAULT_COMMUNICATION_INTERVAL_MS
        )

        self.expression_interval_ms = self._get_config(
            "expression_interval",
            DEFAULT_EXPRESSION_INTERVAL_MS
        )

        self.gc_interval_ms = self._get_config(
            "gc_interval",
            DEFAULT_GC_INTERVAL_MS
        )

        self.status_interval_ms = self._get_config(
            "status_interval",
            DEFAULT_STATUS_INTERVAL_MS
        )

        self.motor_timeout_ms = self._get_config(
            "motor_timeout",
            DEFAULT_MOTOR_TIMEOUT_MS
        )

        self.max_speed = self._get_config(
            "max_speed",
            DEFAULT_MAX_SPEED
        )

        # ----------------------------------------------------
        # RUNTIME STATE
        # ----------------------------------------------------

        self.state = STATE_STOPPED

        self.running = False

        self.paused = False

        self.emergency_stop = False

        # ----------------------------------------------------
        # TIMERS
        # ----------------------------------------------------

        now = time.ticks_ms()

        self.last_loop = now

        self.last_localization_update = now

        self.last_autonomy_update = now

        self.last_communication_update = now

        self.last_expression_update = now

        self.last_gc = now

        self.last_status = now

        # ----------------------------------------------------
        # MOTOR ARBITRATION
        # ----------------------------------------------------

        self.motor_command = self._idle_command()

        self.last_motor_command = now

        self.command_source = "idle"

        self.command_priority = PRIORITY_IDLE

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        self.loop_count = 0

        self.error_count = 0

        self.start_time = 0

        self.last_error = None

        print("[RUNTIME] Dependencies:")

        print(
            "[RUNTIME] Drivers:",
            "ONLINE"
            if self.drivers
            else "OFFLINE"
        )

        print(
            "[RUNTIME] Localization:",
            "ONLINE"
            if self.localization
            else "OFFLINE"
        )

        print(
            "[RUNTIME] Autonomy:",
            "ONLINE"
            if self.autonomy
            else "OFFLINE"
        )

        print(
            "[RUNTIME] Communication:",
            "ONLINE"
            if self.communication
            else "OFFLINE"
        )

        print(
            "[RUNTIME] Expression:",
            "ONLINE"
            if self.expression
            else "OFFLINE"
        )

        print("[RUNTIME] Central nervous system ready")

    # ========================================================
    # CONFIG ACCESS
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
    # IDLE COMMAND
    # ========================================================

    def _idle_command(self):

        return {

            "forward": 0,

            "lateral": 0,

            "rotation": 0,

            "speed": 0,

            "timestamp": time.ticks_ms(),

            "source": "idle",

            "priority": PRIORITY_IDLE

        }

    # ========================================================
    # NORMALIZE MOTOR COMMAND
    # ========================================================

    def _normalize_command(
        self,
        command,
        source="unknown",
        priority=PRIORITY_IDLE
    ):

        if not isinstance(
            command,
            dict
        ):

            return None

        try:

            forward = float(
                command.get(
                    "forward",
                    0
                )
            )

            lateral = float(
                command.get(
                    "lateral",
                    0
                )
            )

            rotation = float(
                command.get(
                    "rotation",
                    0
                )
            )

            speed = float(
                command.get(
                    "speed",
                    self.max_speed
                )
            )

            # Clamp directional values.

            forward = max(
                -100,
                min(
                    100,
                    forward
                )
            )

            lateral = max(
                -100,
                min(
                    100,
                    lateral
                )
            )

            rotation = max(
                -100,
                min(
                    100,
                    rotation
                )
            )

            speed = max(
                0,
                min(
                    self.max_speed,
                    speed
                )
            )

            return {

                "forward": forward,

                "lateral": lateral,

                "rotation": rotation,

                "speed": speed,

                "timestamp": time.ticks_ms(),

                "source": source,

                "priority": priority

            }

        except Exception:

            return None

    # ========================================================
    # SUBMIT MOTOR COMMAND
    # ========================================================

    def submit_motor_command(
        self,
        command,
        source="unknown",
        priority=PRIORITY_AUTONOMY
    ):
        """
        Submit a proposed movement command.

        Runtime decides whether the command replaces the
        currently active command.
        """

        if self.emergency_stop:

            return False

        normalized = self._normalize_command(

            command,

            source,

            priority

        )

        if normalized is None:

            return False

        # ----------------------------------------------------
        # PRIORITY ARBITRATION
        # ----------------------------------------------------

        if priority < self.command_priority:

            return False

        self.motor_command = normalized

        self.command_source = source

        self.command_priority = priority

        self.last_motor_command = time.ticks_ms()

        return True

    # ========================================================
    # CLEAR MOTOR COMMAND
    # ========================================================

    def clear_motor_command(self):

        self.motor_command = self._idle_command()

        self.command_source = "idle"

        self.command_priority = PRIORITY_IDLE

    # ========================================================
    # MOTOR COMMAND TIMEOUT
    # ========================================================

    def _check_motor_timeout(self):

        if self.command_priority <= PRIORITY_IDLE:

            return

        now = time.ticks_ms()

        elapsed = time.ticks_diff(

            now,

            self.last_motor_command

        )

        if elapsed >= self.motor_timeout_ms:

            self.clear_motor_command()

    # ========================================================
    # DRIVER MOVEMENT EXECUTION
    # ========================================================

    def _execute_motor_command(
        self,
        command
    ):
        """
        Translate runtime command into the driver's public API.

        Supported driver APIs:

        drivers.move(...)
        drivers.drive(...)
        drivers.set_motion(...)
        drivers.stop()
        """

        if not self.drivers:

            return False

        if self.emergency_stop:

            return self._execute_stop()

        try:

            forward = command.get(
                "forward",
                0
            )

            lateral = command.get(
                "lateral",
                0
            )

            rotation = command.get(
                "rotation",
                0
            )

            speed = command.get(
                "speed",
                0
            )

            # ------------------------------------------------
            # IDLE
            # ------------------------------------------------

            if (

                forward == 0

                and

                lateral == 0

                and

                rotation == 0

            ):

                return self._execute_stop()

            # ------------------------------------------------
            # MOVE API
            # ------------------------------------------------

            mover = getattr(

                self.drivers,

                "move",

                None

            )

            if callable(mover):

                try:

                    mover(

                        forward=forward,

                        lateral=lateral,

                        rotation=rotation,

                        speed=speed

                    )

                    return True

                except TypeError:

                    try:

                        mover(

                            forward,

                            lateral,

                            rotation,

                            speed

                        )

                        return True

                    except Exception:

                        pass

            # ------------------------------------------------
            # DRIVE API
            # ------------------------------------------------

            driver = getattr(

                self.drivers,

                "drive",

                None

            )

            if callable(driver):

                try:

                    driver(

                        forward,

                        lateral,

                        rotation,

                        speed

                    )

                    return True

                except Exception:

                    pass

            # ------------------------------------------------
            # SET MOTION API
            # ------------------------------------------------

            setter = getattr(

                self.drivers,

                "set_motion",

                None

            )

            if callable(setter):

                try:

                    setter(command)

                    return True

                except Exception:

                    pass

        except Exception as e:

            self._record_error(

                "motor_execution",

                e

            )

        return False

    # ========================================================
    # STOP EXECUTION
    # ========================================================

    def _execute_stop(self):

        if not self.drivers:

            return False

        try:

            stopper = getattr(

                self.drivers,

                "stop",

                None

            )

            if callable(stopper):

                stopper()

                return True

        except Exception as e:

            self._record_error(

                "motor_stop",

                e

            )

        return False

    # ========================================================
    # EMERGENCY STOP
    # ========================================================

    def emergency_halt(
        self,
        reason="manual"
    ):

        print(
            "[RUNTIME] EMERGENCY STOP:",
            reason
        )

        self.emergency_stop = True

        self.clear_motor_command()

        self._execute_stop()

        # Inform autonomy.

        if self.autonomy:

            try:

                stopper = getattr(

                    self.autonomy,

                    "stop",

                    None

                )

                if callable(stopper):

                    stopper()

            except Exception:

                pass

        return True

    # ========================================================
    # RELEASE EMERGENCY STOP
    # ========================================================

    def release_emergency_stop(self):

        self.emergency_stop = False

        print(
            "[RUNTIME] Emergency stop released"
        )

        return True

    # ========================================================
    # UPDATE LOCALIZATION
    # ========================================================

    def _update_localization(self):

        if not self.localization:

            return

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_localization_update

        ) < self.localization_interval_ms:

            return

        self.last_localization_update = now

        try:

            updater = getattr(

                self.localization,

                "update",

                None

            )

            if callable(updater):

                updater()

        except Exception as e:

            self._record_error(

                "localization",

                e

            )

    # ========================================================
    # UPDATE AUTONOMY
    # ========================================================

    def _update_autonomy(self):

        if not self.autonomy:

            return

        if self.emergency_stop:

            return

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_autonomy_update

        ) < self.autonomy_interval_ms:

            return

        self.last_autonomy_update = now

        try:

            updater = getattr(

                self.autonomy,

                "update",

                None

            )

            if not callable(updater):

                return

            result = updater()

            # ----------------------------------------------
            # Autonomy may return a motor command.
            # ----------------------------------------------

            if isinstance(
                result,
                dict
            ):

                if (

                    "forward" in result

                    or

                    "lateral" in result

                    or

                    "rotation" in result

                ):

                    self.submit_motor_command(

                        result,

                        source="autonomy",

                        priority=PRIORITY_AUTONOMY

                    )

        except Exception as e:

            self._record_error(

                "autonomy",

                e

            )

    # ========================================================
    # UPDATE COMMUNICATION
    # ========================================================

    def _update_communication(self):

        if not self.communication:

            return

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_communication_update

        ) < self.communication_interval_ms:

            return

        self.last_communication_update = now

        try:

            updater = getattr(

                self.communication,

                "update",

                None

            )

            if callable(updater):

                result = updater()

                self._handle_communication_result(
                    result
                )

        except Exception as e:

            self._record_error(

                "communication",

                e

            )

    # ========================================================
    # HANDLE COMMUNICATION COMMAND
    # ========================================================

    def _handle_communication_result(
        self,
        result
    ):

        if not isinstance(
            result,
            dict
        ):

            return

        # ----------------------------------------------------
        # EMERGENCY STOP
        # ----------------------------------------------------

        if result.get(
            "emergency_stop",
            False
        ):

            self.emergency_halt(
                "remote_command"
            )

            return

        # ----------------------------------------------------
        # RELEASE STOP
        # ----------------------------------------------------

        if result.get(
            "release_stop",
            False
        ):

            self.release_emergency_stop()

            return

        # ----------------------------------------------------
        # REMOTE MOVEMENT
        # ----------------------------------------------------

        command = result.get(
            "motor_command"
        )

        if isinstance(
            command,
            dict
        ):

            self.submit_motor_command(

                command,

                source="communication",

                priority=PRIORITY_REMOTE

            )

    # ========================================================
    # UPDATE EXPRESSION
    # ========================================================

    def _update_expression(self):

        if not self.expression:

            return

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_expression_update

        ) < self.expression_interval_ms:

            return

        self.last_expression_update = now

        try:

            updater = getattr(

                self.expression,

                "update",

                None

            )

            if callable(updater):

                updater()

        except Exception as e:

            self._record_error(

                "expression",

                e

            )

    # ========================================================
    # EXECUTE MOVEMENT
    # ========================================================

    def _update_motors(self):

        self._check_motor_timeout()

        command = self.motor_command

        self._execute_motor_command(
            command
        )

        # ----------------------------------------------------
        # Reset priority after execution.
        #
        # New autonomy commands can replace previous ones.
        # ----------------------------------------------------

        if not self.emergency_stop:

            self.command_priority = (
                PRIORITY_IDLE
            )

    # ========================================================
    # GARBAGE COLLECTION
    # ========================================================

    def _update_memory(self):

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_gc

        ) < self.gc_interval_ms:

            return

        self.last_gc = now

        try:

            gc.collect()

        except Exception:

            pass

    # ========================================================
    # STATUS LOGGING
    # ========================================================

    def _update_status(self):

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_status

        ) < self.status_interval_ms:

            return

        self.last_status = now

        try:

            print(

                "[RUNTIME] loops:",

                self.loop_count,

                "| mem:",

                gc.mem_free(),

                "| state:",

                self.state

            )

        except Exception:

            pass

    # ========================================================
    # ERROR RECORDING
    # ========================================================

    def _record_error(
        self,
        subsystem,
        error
    ):

        self.error_count += 1

        self.last_error = {

            "subsystem": subsystem,

            "error": str(error),

            "timestamp": time.ticks_ms()

        }

        print(

            "[RUNTIME] ERROR:",

            subsystem,

            error

        )

    # ========================================================
    # SINGLE RUNTIME TICK
    # ========================================================

    def tick(self):
        """
        Execute one SATURDAY nervous-system cycle.
        """

        if not self.running:

            return False

        if self.paused:

            self._update_communication()

            self._update_expression()

            self._update_memory()

            return True

        # ----------------------------------------------------
        # SPATIAL AWARENESS
        # ----------------------------------------------------

        self._update_localization()

        # ----------------------------------------------------
        # COMMUNICATION
        # ----------------------------------------------------

        self._update_communication()

        # ----------------------------------------------------
        # AUTONOMY
        # ----------------------------------------------------

        self._update_autonomy()

        # ----------------------------------------------------
        # EXPRESSION
        # ----------------------------------------------------

        self._update_expression()

        # ----------------------------------------------------
        # MOTOR ARBITRATION + EXECUTION
        # ----------------------------------------------------

        self._update_motors()

        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        self._update_memory()

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self._update_status()

        self.loop_count += 1

        return True

    # ========================================================
    # RUN LOOP
    # ========================================================

    def run(self):

        if self.running:

            return

        print("[RUNTIME] Starting SATURDAY event loop...")

        self.running = True

        self.paused = False

        self.state = STATE_RUNNING

        self.start_time = time.ticks_ms()

        try:

            while self.running:

                loop_start = time.ticks_ms()

                self.tick()

                elapsed = time.ticks_diff(

                    time.ticks_ms(),

                    loop_start

                )

                remaining = (

                    self.loop_delay_ms

                    - elapsed

                )

                if remaining > 0:

                    time.sleep_ms(
                        remaining
                    )

        except KeyboardInterrupt:

            print(
                "[RUNTIME] Keyboard interrupt"
            )

        except Exception as e:

            self.state = STATE_ERROR

            self._record_error(
                "runtime_loop",
                e
            )

            raise

        finally:

            self.stop()

    # ========================================================
    # PAUSE
    # ========================================================

    def pause(self):

        if not self.running:

            return False

        self.paused = True

        self.state = STATE_PAUSED

        self.clear_motor_command()

        self._execute_stop()

        print(
            "[RUNTIME] Runtime paused"
        )

        return True

    # ========================================================
    # RESUME
    # ========================================================

    def resume(self):

        if not self.running:

            return False

        self.paused = False

        self.state = STATE_RUNNING

        print(
            "[RUNTIME] Runtime resumed"
        )

        return True

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        if self.state == STATE_STOPPED:

            return

        print(
            "[RUNTIME] Stopping SATURDAY runtime..."
        )

        self.state = STATE_SHUTTING_DOWN

        self.running = False

        self.paused = False

        self.clear_motor_command()

        self._execute_stop()

        # ----------------------------------------------------
        # STOP AUTONOMY
        # ----------------------------------------------------

        if self.autonomy:

            try:

                stopper = getattr(

                    self.autonomy,

                    "stop",

                    None

                )

                if callable(stopper):

                    stopper()

            except Exception:

                pass

        # ----------------------------------------------------
        # STOP COMMUNICATION
        # ----------------------------------------------------

        if self.communication:

            try:

                stopper = getattr(

                    self.communication,

                    "stop",

                    None

                )

                if callable(stopper):

                    stopper()

            except Exception:

                pass

        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------

        self.cleanup()

        self.state = STATE_STOPPED

        print(
            "[RUNTIME] SATURDAY runtime stopped"
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        uptime = 0

        if self.start_time:

            uptime = time.ticks_diff(

                time.ticks_ms(),

                self.start_time

            )

        return {

            "state": self.state,

            "running": self.running,

            "paused": self.paused,

            "emergency_stop": self.emergency_stop,

            "loop_count": self.loop_count,

            "uptime_ms": uptime,

            "errors": self.error_count,

            "last_error": self.last_error,

            "memory_free": gc.mem_free(),

            "motor": {

                "command": dict(
                    self.motor_command
                ),

                "source":
                    self.command_source,

                "priority":
                    self.command_priority

            },

            "subsystems": {

                "drivers":
                    self.drivers is not None,

                "localization":
                    self.localization is not None,

                "autonomy":
                    self.autonomy is not None,

                "communication":
                    self.communication is not None,

                "expression":
                    self.expression is not None

            }

        }

    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup(self):

        modules = [

            self.localization,

            self.autonomy,

            self.communication,

            self.expression,

            self.drivers

        ]

        for module in modules:

            if not module:

                continue

            try:

                cleaner = getattr(

                    module,

                    "cleanup",

                    None

                )

                if callable(cleaner):

                    cleaner()

            except Exception:

                pass

        try:

            gc.collect()

        except Exception:

            pass


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

SaturdayRuntime = Runtime

SATURDAYRuntime = Runtime