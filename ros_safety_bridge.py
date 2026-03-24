from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BridgeLimits:
    max_linear_speed: float = 0.8
    max_angular_speed: float = 1.2
    max_torque: float = 60.0
    min_obstacle_distance: float = 0.50
    command_publish_rate_hz: float = 20.0


class ROSSafetyBridge:
    def __init__(self, *, limits: BridgeLimits | None = None, node_name: str = "aegis_safety_bridge") -> None:
        self.limits = limits or BridgeLimits()
        self.node_name = node_name
        self._state_lock = threading.RLock()

        self._initialized = False
        self._mode = "IDLE"
        self._estop_engaged = False
        self._obstacle_distance = 1.5
        self._current_speed = 0.0
        self._current_torque = 0.0
        self._last_sensor_timestamp = time.time()

        self._ros_node = None
        self._ros_executor = None
        self._ros_thread = None
        self._cmd_pub = None
        self._estop_pub = None
        self._mode_pub = None

        self._try_init_ros()

    def _try_init_ros(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import Twist
            from nav_msgs.msg import Odometry
            from rclpy.executors import MultiThreadedExecutor
            from sensor_msgs.msg import JointState, LaserScan
            from std_msgs.msg import Bool, String
        except ImportError as exc:
            print(f"ROS2 not available: {exc}")
            self._initialized = False
            return

        self.rclpy = rclpy
        self.Twist = Twist
        self.Bool = Bool
        self.String = String
        self.Odometry = Odometry
        self.LaserScan = LaserScan
        self.JointState = JointState
        self.MultiThreadedExecutor = MultiThreadedExecutor

        try:
            if not rclpy.ok():
                rclpy.init(args=None)

            self._ros_node = rclpy.create_node(self.node_name)
            self._cmd_pub = self._ros_node.create_publisher(self.Twist, "/cmd_vel", 10)
            self._estop_pub = self._ros_node.create_publisher(self.Bool, "/aegis/estop", 10)
            self._mode_pub = self._ros_node.create_publisher(self.String, "/aegis/mode", 10)

            self._ros_node.create_subscription(self.LaserScan, "/scan", self._on_scan, 10)
            self._ros_node.create_subscription(self.Odometry, "/odom", self._on_odom, 10)
            self._ros_node.create_subscription(self.JointState, "/joint_states", self._on_joint_state, 10)

            self._ros_executor = self.MultiThreadedExecutor()
            self._ros_executor.add_node(self._ros_node)
            self._initialized = True

            self._ros_thread = threading.Thread(target=self._spin_ros, daemon=True)
            self._ros_thread.start()
            print("ROS2 bridge initialized successfully")
        except Exception as exc:
            print(f"ROS2 initialization failed: {exc}")
            self._initialized = False
            self._cleanup_ros()

    def _spin_ros(self) -> None:
        while self._initialized and self._ros_executor is not None:
            try:
                self._ros_executor.spin_once(timeout_sec=0.1)
            except Exception:
                time.sleep(0.1)

    def _on_scan(self, message: Any) -> None:
        valid = [float(value) for value in message.ranges if math.isfinite(value) and value > 0.0]
        if not valid:
            return
        with self._state_lock:
            self._obstacle_distance = min(valid)
            self._last_sensor_timestamp = time.time()

    def _on_odom(self, message: Any) -> None:
        linear = message.twist.twist.linear
        speed = math.sqrt((linear.x * linear.x) + (linear.y * linear.y) + (linear.z * linear.z))
        with self._state_lock:
            self._current_speed = speed
            self._last_sensor_timestamp = time.time()

    def _on_joint_state(self, message: Any) -> None:
        if not message.effort:
            return
        max_effort = max(abs(float(value)) for value in message.effort)
        with self._state_lock:
            self._current_torque = max_effort
            self._last_sensor_timestamp = time.time()

    def _build_twist(self, *, direction: str, speed: float) -> Any:
        twist = self.Twist()
        direction = direction.upper()
        if direction == "FORWARD":
            twist.linear.x = speed
        elif direction == "BACKWARD":
            twist.linear.x = -speed
        elif direction == "LEFT":
            twist.linear.y = speed
        elif direction == "RIGHT":
            twist.linear.y = -speed
        elif direction == "ROTATE_LEFT":
            twist.angular.z = min(speed, self.limits.max_angular_speed)
        elif direction == "ROTATE_RIGHT":
            twist.angular.z = -min(speed, self.limits.max_angular_speed)
        return twist

    def _publish_stop(self) -> None:
        if not self._initialized or self._cmd_pub is None:
            return
        self._cmd_pub.publish(self.Twist())

    def _publish_mode(self, mode: str) -> None:
        if not self._initialized or self._mode_pub is None:
            return
        msg = self.String()
        msg.data = mode.upper()
        self._mode_pub.publish(msg)

    def _publish_estop(self, engaged: bool) -> None:
        if not self._initialized or self._estop_pub is None:
            return
        msg = self.Bool()
        msg.data = engaged
        self._estop_pub.publish(msg)

    def get_runtime_context(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "estop_engaged": self._estop_engaged,
                "obstacle_distance": self._obstacle_distance,
                "current_speed": self._current_speed,
                "current_torque": self._current_torque,
                "mode": self._mode,
                "ros_available": self._initialized,
                "last_sensor_timestamp": self._last_sensor_timestamp,
            }

    def execute_validated_command(self, command: dict[str, Any]) -> dict[str, Any]:
        intent = str(command.get("intent", "UNKNOWN")).upper()
        params = dict(command.get("parameters", {}))

        if not self._initialized:
            return {
                "executed": False,
                "intent": intent,
                "params": params,
                "timestamp": time.time(),
                "ros_available": False,
                "message": "ROS2 bridge is not available.",
            }

        with self._state_lock:
            if self._estop_engaged and intent not in {"STOP", "CLEAR_ESTOP"}:
                return {
                    "executed": False,
                    "intent": intent,
                    "params": params,
                    "timestamp": time.time(),
                    "ros_available": True,
                    "message": "Command blocked because emergency stop is active",
                }

        if intent == "MOVE":
            direction = str(params.get("direction", "FORWARD")).upper()
            speed = float(params.get("speed", self.limits.max_linear_speed))
            speed = max(0.0, min(speed, self.limits.max_linear_speed))
            duration = float(params.get("duration", 0.0))
            duration = max(0.0, duration)

            twist = self._build_twist(direction=direction, speed=speed)
            self._cmd_pub.publish(twist)
            if duration > 0.0:
                time.sleep(duration)
                self._publish_stop()
            with self._state_lock:
                self._mode = "MANUAL"
        elif intent == "STOP":
            self._publish_stop()
        elif intent == "SET_MODE":
            mode = str(params.get("mode", "IDLE")).upper()
            with self._state_lock:
                self._mode = mode
            self._publish_mode(mode)
        elif intent == "EMERGENCY_STOP":
            with self._state_lock:
                self._estop_engaged = True
                self._mode = "E_STOP"
            self._publish_stop()
            self._publish_estop(True)
        elif intent == "CLEAR_ESTOP":
            if bool(params.get("require_ack", False)):
                with self._state_lock:
                    self._estop_engaged = False
                    if self._mode == "E_STOP":
                        self._mode = "IDLE"
                self._publish_estop(False)

        return {
            "executed": True,
            "intent": intent,
            "params": params,
            "timestamp": time.time(),
            "ros_available": True,
            "message": f"Command {intent} executed",
        }

    def get_sensor_snapshot(self) -> dict[str, Any]:
        if not self._initialized:
            return {
                "timestamp": time.time(),
                "ros_available": False,
                "message": "ROS2 bridge is not available.",
            }

        with self._state_lock:
            obstacle_distance = self._obstacle_distance
            speed = self._current_speed
            mode = self._mode
            torque = self._current_torque

        return {
            "timestamp": time.time(),
            "laser_scan": {
                "nearest_obstacle_distance": obstacle_distance,
            },
            "odometry": {
                "speed": speed,
            },
            "joint_states": {
                "max_effort": torque,
            },
            "mode": mode,
            "ros_available": True,
        }

    def _cleanup_ros(self) -> None:
        if self._ros_executor is not None:
            try:
                self._ros_executor.shutdown()
            except Exception:
                pass
            self._ros_executor = None

        if self._ros_node is not None:
            try:
                self._ros_node.destroy_node()
            except Exception:
                pass
            self._ros_node = None

        if hasattr(self, "rclpy"):
            try:
                if self.rclpy.ok():
                    self.rclpy.shutdown()
            except Exception:
                pass

    def shutdown(self) -> None:
        self._initialized = False
        self._cleanup_ros()
