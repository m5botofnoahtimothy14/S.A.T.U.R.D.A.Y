from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


COMMAND_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "parameters"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["MOVE", "STOP", "SET_MODE", "EMERGENCY_STOP", "CLEAR_ESTOP"],
        },
        "parameters": {"type": "object"},
    },
    "allOf": [
        {
            "if": {"properties": {"intent": {"const": "MOVE"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["direction", "duration"],
                        "properties": {
                            "direction": {
                                "type": "string",
                                "enum": ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "ROTATE_LEFT", "ROTATE_RIGHT"],
                            },
                            "duration": {"type": "number", "exclusiveMinimum": 0, "maximum": 10},
                            "speed": {"type": "number", "exclusiveMinimum": 0, "maximum": 2.0},
                            "torque": {"type": "number", "minimum": 0, "maximum": 100.0},
                        },
                    }
                }
            },
        },
        {
            "if": {"properties": {"intent": {"const": "STOP"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"immediate": {"type": "boolean"}},
                    }
                }
            },
        },
        {
            "if": {"properties": {"intent": {"const": "SET_MODE"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["mode"],
                        "properties": {
                            "mode": {"type": "string", "enum": ["IDLE", "MANUAL", "AUTONOMOUS"]},
                        },
                    }
                }
            },
        },
        {
            "if": {"properties": {"intent": {"const": "EMERGENCY_STOP"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["reason"],
                        "properties": {"reason": {"type": "string", "minLength": 1, "maxLength": 256}},
                    }
                }
            },
        },
        {
            "if": {"properties": {"intent": {"const": "CLEAR_ESTOP"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["require_ack"],
                        "properties": {"require_ack": {"type": "boolean"}},
                    }
                }
            },
        },
    ],
}


ROLE_INTENT_POLICY: dict[str, set[str]] = {
    "viewer": set(),
    "operator": {"MOVE", "STOP", "SET_MODE"},
    "admin": {"MOVE", "STOP", "SET_MODE", "EMERGENCY_STOP", "CLEAR_ESTOP"},
}


@dataclass(frozen=True)
class SafetyLimits:
    max_linear_speed: float = 0.8
    max_angular_speed: float = 1.2
    max_torque: float = 60.0
    max_duration: float = 5.0
    min_obstacle_distance: float = 0.50


class PolicyViolation(Exception):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CommandPolicy:
    def __init__(self, limits: SafetyLimits | None = None) -> None:
        self.limits = limits or SafetyLimits()
        self.validator = Draft202012Validator(COMMAND_SCHEMA)

    def validate_schema(self, command: dict[str, Any]) -> None:
        errors = sorted(self.validator.iter_errors(command), key=lambda err: err.path)
        if not errors:
            return
        first = errors[0]
        raise PolicyViolation(
            "Command schema validation failed",
            details={"path": list(first.path), "error": first.message},
        )

    def enforce_role(self, command_intent: str, roles: tuple[str, ...] | list[str]) -> None:
        normalized_roles = [str(role).strip().lower() for role in roles]
        allowed = set()
        for role in normalized_roles:
            allowed.update(ROLE_INTENT_POLICY.get(role, set()))
        if command_intent not in allowed:
            raise PolicyViolation(
                "Role is not allowed to execute command intent",
                details={"intent": command_intent, "roles": normalized_roles},
            )

    def enforce_safety(self, command: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        intent = command["intent"]
        params = command["parameters"]

        estop = bool(runtime_context.get("estop_engaged", False))
        if estop and intent not in {"STOP", "CLEAR_ESTOP"}:
            raise PolicyViolation("Emergency stop is active", details={"intent": intent})

        if intent != "MOVE":
            return command

        direction = str(params["direction"]).upper()
        duration = float(params["duration"])
        speed = float(params.get("speed", self.limits.max_linear_speed))
        torque = float(params.get("torque", self.limits.max_torque))

        if duration > self.limits.max_duration:
            raise PolicyViolation(
                "Duration exceeds safety limit",
                details={"duration": duration, "max_duration": self.limits.max_duration},
            )

        if speed > self.limits.max_linear_speed:
            raise PolicyViolation(
                "Requested speed exceeds safety limit",
                details={"speed": speed, "max_linear_speed": self.limits.max_linear_speed},
            )

        if torque > self.limits.max_torque:
            raise PolicyViolation(
                "Requested torque exceeds safety limit",
                details={"torque": torque, "max_torque": self.limits.max_torque},
            )

        nearest_obstacle = runtime_context.get("obstacle_distance")
        if direction == "FORWARD" and nearest_obstacle is not None:
            nearest = float(nearest_obstacle)
            if nearest < self.limits.min_obstacle_distance:
                raise PolicyViolation(
                    "Obstacle too close for forward motion",
                    details={
                        "obstacle_distance": nearest,
                        "required_min_distance": self.limits.min_obstacle_distance,
                    },
                )

        return {
            "intent": intent,
            "parameters": {
                "direction": direction,
                "duration": duration,
                "speed": speed,
                "torque": torque,
            },
        }

    def validate_and_enforce(
        self,
        command: dict[str, Any],
        roles: tuple[str, ...] | list[str],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        self.validate_schema(command)

        normalized_command = {
            "intent": str(command["intent"]).upper(),
            "parameters": dict(command["parameters"]),
        }

        self.enforce_role(normalized_command["intent"], roles)
        return self.enforce_safety(normalized_command, runtime_context)
