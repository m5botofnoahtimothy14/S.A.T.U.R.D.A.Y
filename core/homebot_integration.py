                             

import json
import logging
import os
import threading
import time
from core.event_bus import EventBus
try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None
try:
    import serial
except ImportError:
    serial = None
logger = logging.getLogger("SATURDAY.HomeBotIntegration")
class HomeBotIntegration:
    def __init__(self, event_bus: EventBus, com_port: str | None = None):
        self.event_bus = event_bus
        self.backend = os.getenv("HOMEBOT_BACKEND", "auto").strip().lower()
        self.com_port = com_port or os.getenv("HOMEBOT_COM_PORT", "").strip()
        self.mqtt_broker = os.getenv("MQTT_BROKER", "").strip()
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.serial_conn = None
        self.mqtt_client = None
        self.connected = False
        self.broker_connected = False
        self.raw_voice_subscription = os.getenv("HOMEBOT_SUBSCRIBE_RAW_VOICE", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.last_seen = 0.0
        self.current_command = "idle"
        self.logs = []
        self.latest_status = {}
        self.latest_sensors = {}
        self.latest_nav_scan = {}
        self.transport = self._select_transport()
        self._connect()
        if self.raw_voice_subscription:
            self.event_bus.subscribe("voice_command", self._process_command)
        threading.Thread(target=self._telemetry_loop, daemon=True).start()
    def _select_transport(self) -> str:
        if self.backend in {"serial", "mqtt"}:
            return self.backend
        if self.com_port:
            return "serial"
        return "mqtt"
    def _connect(self):
        if self.transport == "serial":
            self._connect_serial()
        else:
            self._connect_mqtt()
    def _connect_serial(self):
        if not serial:
            self._log("error", "pyserial is not installed; serial HomeBot transport is unavailable.")
            return
        if not self.com_port:
            self._log("error", "HOMEBOT_COM_PORT is not configured for serial HomeBot transport.")
            return
        try:
            self.serial_conn = serial.Serial(
                port=self.com_port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            time.sleep(2)
            self.connected = True
            self.last_seen = time.time()
            self._log("info", f"HomeBot serial connection established on {self.com_port}.")
        except Exception as e:
            self._log("error", f"Failed to connect HomeBot on serial port {self.com_port}: {e}")
    def _connect_mqtt(self):
        if not mqtt:
            self._log("error", "paho-mqtt is not installed; MQTT HomeBot transport is unavailable.")
            return
        if not self.mqtt_broker:
            self._log("error", "MQTT_BROKER is not configured for HomeBot MQTT transport.")
            return
        self.mqtt_client = mqtt.Client(client_id="SATURDAY-HomeBot")
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_log = self._on_mqtt_log
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            self.broker_connected = True
            self._log("info", f"Connected to HomeBot MQTT broker at {self.mqtt_broker}:{self.mqtt_port}.")
        except ConnectionRefusedError:
            self._log("warning", f"HomeBot MQTT broker connection refused at {self.mqtt_broker}:{self.mqtt_port}. Broker may not be running. Will retry in background.")
            self._retry_mqtt_connection()
        except Exception as e:
            self._log("error", f"Failed to connect to HomeBot MQTT broker {self.mqtt_broker}:{self.mqtt_port}: {e}")
            self._retry_mqtt_connection()
    def _retry_mqtt_connection(self):
        def retry_thread():
            for attempt in range(3):
                time.sleep(10 * (attempt + 1))
                try:
                    if self.mqtt_client:
                        self.mqtt_client.reconnect()
                        self._log("info", f"Reconnected to HomeBot MQTT broker (attempt {attempt + 1})")
                        return
                except Exception as e:
                    self._log("warning", f"MQTT reconnect attempt {attempt + 1} failed: {e}")
        threading.Thread(target=retry_thread, daemon=True).start()
    def _on_mqtt_log(self, client, userdata, level, buf):
        if level == mqtt.MQTT_LOG_ERR:
            logger.error(f"MQTT: {buf}")
    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc != 0:
            self._log("error", f"HomeBot MQTT connect failed with rc={rc}.")
            self.broker_connected = False
            return
        self.broker_connected = True
        client.subscribe("homebot/status")
        client.subscribe("homebot/sensors/data")
        client.subscribe("homebot/nav/scan")
        self.request_sensor_refresh()
    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        self.broker_connected = False
        self.connected = False
        self._log("warning", f"HomeBot MQTT disconnected with rc={rc}.")
    def _on_mqtt_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="ignore")
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"raw": payload}
        self.last_seen = time.time()
        self.connected = True
        if msg.topic == "homebot/status":
            self.latest_status = data
        elif msg.topic == "homebot/sensors/data":
            self.latest_sensors = data
            self.event_bus.publish("homebot_telemetry", data)
        elif msg.topic == "homebot/nav/scan":
            self.latest_nav_scan = data
    def _process_command(self, command_str):
        if isinstance(command_str, dict):
            command_str = command_str.get("command", "")
        self.execute_voice_command(str(command_str))
    def execute_voice_command(self, command_str: str) -> dict:
        command_str = (command_str or "").strip().lower()
        if not command_str:
            return {"status": "unavailable", "reason": "No HomeBot command was provided."}
        self._log("info", f"HomeBot received command: {command_str}")
        movement_map = [
            ("rotate left", "RTL"),
            ("spin left", "RTL"),
            ("rotate right", "RTR"),
            ("spin right", "RTR"),
            ("forward", "FWD"),
            ("ahead", "FWD"),
            ("backward", "REV"),
            ("back", "REV"),
            ("reverse", "REV"),
            ("left", "LFT"),
            ("right", "RGT"),
            ("stop", "STP"),
            ("halt", "STP"),
        ]
        if "go to" in command_str:
            parts = command_str.split()
            try:
                idx = parts.index("to")
                target = (int(parts[idx + 1]), int(parts[idx + 2]))
            except Exception:
                return {"status": "unavailable", "reason": "Navigation command must be in the form 'go to X Y'."}
            return self.autonomous_navigation(target)
        if "homebot" not in command_str and "bot" not in command_str and not any(key in command_str for key, _ in movement_map):
            return {"status": "unavailable", "reason": "Command does not target HomeBot."}
        for key, command in movement_map:
            if key in command_str:
                return self.execute_command(command)
        return {"status": "unavailable", "reason": f"No mapped HomeBot action found for '{command_str}'."}
    def execute_command(self, command: str, duration: float = 1, speed: int = 80) -> dict:
        if self.transport == "serial":
            return self._execute_serial(command)
        return self._execute_mqtt(command, duration=duration, speed=speed)
    def _execute_serial(self, command: str) -> dict:
        if not self.serial_conn or not self.serial_conn.is_open:
            return {"status": "unavailable", "reason": "HomeBot serial transport is not connected."}
        try:
            self.serial_conn.write(f"{command}\n".encode("utf-8"))
            self.serial_conn.flush()
            self.current_command = command
            self.last_seen = time.time()
            return {"status": "success", "command": command, "message": f"HomeBot command {command} sent over serial."}
        except Exception as e:
            self._log("error", f"Serial send failed: {e}")
            return {"status": "error", "reason": str(e)}
    def _execute_mqtt(self, command: str, duration: float = 1, speed: int = 80) -> dict:
        if not self.mqtt_client or not self.broker_connected:
            return {"status": "unavailable", "reason": "HomeBot MQTT transport is not connected."}
        topic = None
        payload = None
        speed = max(0, min(int(speed), 100))
        if command == "FWD":
            topic = "homebot/motors/omni"
            payload = {"x": 0, "y": speed, "rotation": 0}
        elif command == "REV":
            topic = "homebot/motors/omni"
            payload = {"x": 0, "y": -speed, "rotation": 0}
        elif command == "LFT":
            topic = "homebot/motors/omni"
            payload = {"x": -speed, "y": 0, "rotation": 0}
        elif command == "RGT":
            topic = "homebot/motors/omni"
            payload = {"x": speed, "y": 0, "rotation": 0}
        elif command == "RTL":
            topic = "homebot/motors/omni"
            payload = {"x": 0, "y": 0, "rotation": -speed}
        elif command == "RTR":
            topic = "homebot/motors/omni"
            payload = {"x": 0, "y": 0, "rotation": speed}
        elif command == "STP":
            topic = "homebot/motors/stop"
            payload = "1"
        if not topic:
            return {"status": "unavailable", "reason": f"Unsupported HomeBot command '{command}'."}
        try:
            wire_payload = json.dumps(payload) if isinstance(payload, dict) else str(payload)
            info = self.mqtt_client.publish(topic, wire_payload)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed with rc={info.rc}")
            self.current_command = command
            if command != "STP" and duration and duration > 0:
                threading.Timer(duration, lambda: self._execute_mqtt("STP", duration=0, speed=speed)).start()
            return {"status": "success", "command": command, "message": f"HomeBot command {command} sent over MQTT."}
        except Exception as e:
            self._log("error", f"MQTT command publish failed: {e}")
            return {"status": "error", "reason": str(e)}
    def request_sensor_refresh(self):
        if self.mqtt_client and self.broker_connected:
            self.mqtt_client.publish("homebot/sensors/read", "1")
    def autonomous_navigation(self, target_pos):
        if self.transport == "serial":
            return {"status": "unavailable", "reason": "Autonomous navigation is only implemented on MQTT HomeBot firmware."}
        if not self.mqtt_client or not self.broker_connected:
            return {"status": "unavailable", "reason": "HomeBot MQTT transport is not connected."}
        try:
            payload = json.dumps({"x": int(target_pos[0]), "y": int(target_pos[1])})
            info = self.mqtt_client.publish("homebot/nav/autonomous", payload)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed with rc={info.rc}")
            self.current_command = f"NAV {target_pos[0]} {target_pos[1]}"
            return {"status": "success", "target": list(target_pos), "message": f"HomeBot navigating to {target_pos}."}
        except Exception as e:
            self._log("error", f"HomeBot navigation publish failed: {e}")
            return {"status": "error", "reason": str(e)}
    def get_status(self) -> dict:
        return {
            "connected": self.connected,
            "broker_connected": self.broker_connected,
            "backend": self.transport,
            "last_seen": self.last_seen,
            "current_command": self.current_command,
            "status": self.latest_status,
            "sensors": self.latest_sensors,
            "navigation": self.latest_nav_scan,
        }
    def _telemetry_loop(self):
        while True:
            try:
                if self.transport == "mqtt" and self.broker_connected:
                    self.request_sensor_refresh()
                if self.connected and self.latest_sensors:
                    self.event_bus.publish("homebot_telemetry", self.latest_sensors)
            except Exception as e:
                logger.debug(f"HomeBot telemetry loop error: {e}")
            time.sleep(10)
    def _log(self, level: str, message: str):
        self.logs.append({"ts": time.time(), "level": level, "message": message})
        self.logs = self.logs[-200:]
        getattr(logger, level, logger.info)(message)
    def shutdown(self):
        self._log("info", "HomeBot integration shutting down.")
        try:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except Exception:
            pass
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
        except Exception:
            pass
