                             

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

# ============================================================
# SATURDAY HOME BOT - FIRMWARE V3 MQTT PROTOCOL
#
# Firmware: core/homebot/firmware/flash (v3.0.0, config.py)
#
# Per-device topic namespace using MQTT_ROOT + DEVICE_ID:
#   command   saturday/saturday_homebot_01/command
#   telemetry saturday/saturday_homebot_01/telemetry
#   status    saturday/saturday_homebot_01/status
#   intent    saturday/saturday_homebot_01/intent
#   voice     saturday/saturday_homebot_01/voice
#   events    saturday/saturday_homebot_01/events
#   heartbeat saturday/saturday_homebot_01/heartbeat
#
# Command payloads expected by the firmware:
#   {"motion": {"vx": -1..1, "vy": -1..1, "wz": -1..1}}
#   {"stop": true}
#   {"emergency_stop": true}
#   {"clear_emergency": true}
#   {"autonomy": true|false}
#   {"expression": "..."}
# ============================================================

HOMEBOT_MQTT_ROOT = "saturday"
HOMEBOT_DEVICE_ID = "saturday_homebot_01"

HOMEBOT_CMD_TOPIC = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/command"
HOMEBOT_TELE_TOPIC = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/telemetry"
HOMEBOT_STATUS_TOPIC = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/status"
HOMEBOT_EVENTS_TOPIC = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/events"
HOMEBOT_HEARTBEAT_TOPIC = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/heartbeat"
HOMEBOT_SUB_WILDCARD = f"{HOMEBOT_MQTT_ROOT}/{HOMEBOT_DEVICE_ID}/#"


class HomeBotIntegration:
    def __init__(self, event_bus: EventBus, com_port: str | None = None, mqtt_broker: str | None = None, mqtt_port: int | None = None):
        self.event_bus = event_bus
        self.backend = os.getenv("HOMEBOT_BACKEND", "auto").strip().lower()
        self.com_port = com_port or os.getenv("HOMEBOT_COM_PORT", "").strip()
        self.mqtt_broker = mqtt_broker or os.getenv("MQTT_BROKER", "").strip()
        self.mqtt_port = mqtt_port or int(os.getenv("MQTT_PORT", "1883"))
        self.device_id = HOMEBOT_DEVICE_ID
        self.command_topic = HOMEBOT_CMD_TOPIC
        self.telemetry_topic = HOMEBOT_TELE_TOPIC
        self.status_topic = HOMEBOT_STATUS_TOPIC
        self.events_topic = HOMEBOT_EVENTS_TOPIC
        self.heartbeat_topic = HOMEBOT_HEARTBEAT_TOPIC
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
        client.subscribe(HOMEBOT_SUB_WILDCARD)
        client.subscribe("saturday/#")
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
        if msg.topic == HOMEBOT_TELE_TOPIC:
            self.latest_status = data
            self.latest_sensors = self._extract_sensors(data)
            self.event_bus.publish("homebot_telemetry", data)
        elif msg.topic == HOMEBOT_HEARTBEAT_TOPIC:
            self.latest_status = data
        elif msg.topic == HOMEBOT_STATUS_TOPIC:
            self.latest_status = data
        elif msg.topic == HOMEBOT_EVENTS_TOPIC:
            self.latest_status = data
            self.event_bus.publish("homebot_event", data)
    @staticmethod
    def _extract_sensors(data):
        if not isinstance(data, dict):
            return {}
        sensors = data.get("sensors")
        if isinstance(sensors, dict):
            return sensors
        return data
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
        magnitude = round(speed / 100.0, 3)
        if command == "FWD":
            topic = self.command_topic
            payload = {"motion": {"vx": magnitude, "vy": 0.0, "wz": 0.0}}
        elif command == "REV":
            topic = self.command_topic
            payload = {"motion": {"vx": -magnitude, "vy": 0.0, "wz": 0.0}}
        elif command == "LFT":
            topic = self.command_topic
            payload = {"motion": {"vx": 0.0, "vy": -magnitude, "wz": 0.0}}
        elif command == "RGT":
            topic = self.command_topic
            payload = {"motion": {"vx": 0.0, "vy": magnitude, "wz": 0.0}}
        elif command == "RTL":
            topic = self.command_topic
            payload = {"motion": {"vx": 0.0, "vy": 0.0, "wz": magnitude}}
        elif command == "RTR":
            topic = self.command_topic
            payload = {"motion": {"vx": 0.0, "vy": 0.0, "wz": -magnitude}}
        elif command == "STP":
            topic = self.command_topic
            payload = {"stop": True}
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
            self.mqtt_client.publish(self.status_topic, json.dumps({"type": "status_request"}))
    def autonomous_navigation(self, target_pos):
        if self.transport == "serial":
            return {"status": "unavailable", "reason": "Autonomous navigation is only implemented on MQTT HomeBot firmware."}
        if not self.mqtt_client or not self.broker_connected:
            return {"status": "unavailable", "reason": "HomeBot MQTT transport is not connected."}
        try:
            payload = json.dumps({"intent": {"action": "navigate", "target": [int(target_pos[0]), int(target_pos[1])]}})
            info = self.mqtt_client.publish(self.command_topic, payload)
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
