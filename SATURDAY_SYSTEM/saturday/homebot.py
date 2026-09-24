"""SATURDAY HomeBot link — M5Stack Core2 (firmware v3, flash/) connection.

Protocol mirror of core/homebot_integration.py + firmware topics:
  saturday/saturday_homebot_01/{command,telemetry,status,events,heartbeat}
Motion payloads: {"motion": {"vx","vy","wz" in -1..1}}, {"stop": true}, etc.

Transports:
- MQTT (primary): unlimited reconnect with capped backoff, background
  supervisor thread, thread-safe publish, auto-STOP timer per move.
- Serial (best-effort): auto-scans COM ports for USB-UART bridges
  (CP210x/CH9102/M5Stack); sends firmware line commands.

No hardware present → every command returns {"status": "unavailable",
...} and status() reports it. Nothing here raises on expected failures,
so the dashboard/CLI stay alive for months with the bot offline.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.HomeBot")

DEVICE_ID = "saturday_homebot_01"
ROOT = "saturday"
CMD_TOPIC = f"{ROOT}/{DEVICE_ID}/command"
TELE_TOPIC = f"{ROOT}/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"{ROOT}/{DEVICE_ID}/status"
EVENTS_TOPIC = f"{ROOT}/{DEVICE_ID}/events"
HEARTBEAT_TOPIC = f"{ROOT}/{DEVICE_ID}/heartbeat"
SUB_WILDCARD = f"{ROOT}/{DEVICE_ID}/#"

try:
    import paho.mqtt.client as mqtt

    _MQTT_AVAILABLE = True
except Exception:
    mqtt = None
    _MQTT_AVAILABLE = False

try:
    import serial
    import serial.tools.list_ports as list_ports

    _SERIAL_AVAILABLE = True
except Exception:
    serial = None
    list_ports = None
    _SERIAL_AVAILABLE = False

USB_UART_HINTS = ("cp210", "ch910", "ch340", "m5stack", "usb serial", "uart")


def scan_ports() -> List[Dict[str, str]]:
    if not _SERIAL_AVAILABLE:
        return []
    found = []
    try:
        for p in list_ports.comports():
            found.append({"device": p.device, "description": p.description or "",
                          "likely_bot": any(h in (p.description or "").lower()
                                            for h in USB_UART_HINTS)})
    except Exception as e:
        logger.debug(f"COM scan failed: {e}")
    return found


class HomeBotLink:
    """Long-running Core2 connection. start() once, command anytime."""

    def __init__(self, broker: str = "", port: int = 1883,
                 com_port: str = "", autostart: bool = True):
        self.broker = (broker or os.getenv("MQTT_BROKER", "")).strip()
        self.port = int(port or os.getenv("MQTT_PORT", "1883"))
        self.com_port = (com_port or os.getenv("HOMEBOT_COM_PORT", "")).strip()
        self.client = None
        self.serial_conn = None
        self.lock = threading.RLock()  # reentrant: status() nests link_quality()
        self.broker_connected = False
        self.serial_connected = False
        self.connected = False  # True when the BOT itself was heard from
        self.last_seen = 0.0
        self.current_command = "idle"
        self.latest_status: Dict[str, Any] = {}
        self.latest_sensors: Dict[str, Any] = {}
        self.logs: List[Dict[str, Any]] = []
        self._stop_event = threading.Event()
        self._supervisor = None
        if autostart:
            self.start()

    # -- lifecycle -------------------------------------------------------
    def start(self):
        if self._supervisor and self._supervisor.is_alive():
            return
        self._stop_event.clear()
        self._supervisor = threading.Thread(target=self._supervise, daemon=True,
                                            name="homebot-supervisor")
        self._supervisor.start()

    def stop(self):
        self._stop_event.set()
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
        except Exception:
            pass
        self.broker_connected = False
        self.serial_connected = False

    def _log(self, level: str, message: str):
        self.logs.append({"ts": time.time(), "level": level, "message": message})
        self.logs = self.logs[-200:]
        getattr(logger, level, logger.info)(message)

    def _supervise(self):
        backoff = 5.0
        self._try_serial()
        while not self._stop_event.is_set():
            if self.broker and not self.broker_connected:
                if self._try_mqtt():
                    backoff = 5.0
                else:
                    backoff = min(120.0, backoff * 1.6)
            if not self.serial_connected and not self.com_port:
                self._try_serial()  # pick up a freshly plugged Core2
            self._stop_event.wait(min(backoff, 20.0))

    # -- transports --------------------------------------------------------
    def _try_mqtt(self) -> bool:
        if not _MQTT_AVAILABLE:
            return False
        try:
            client = mqtt.Client(client_id="SATURDAY-PROD-HomeBot")
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.on_disconnect = self._on_disconnect
            client.connect(self.broker, self.port, 60)
            client.loop_start()
            with self.lock:
                self.client = client
            self.broker_connected = True
            self._log("info", f"HomeBot MQTT up at {self.broker}:{self.port}.")
            return True
        except Exception as e:
            self.broker_connected = False
            logger.debug(f"HomeBot MQTT connect failed: {e}")
            return False

    def _try_serial(self):
        if not _SERIAL_AVAILABLE or self.serial_connected:
            return
        target = self.com_port
        if not target:
            cands = [p["device"] for p in scan_ports() if p["likely_bot"]]
            if not cands:
                return
            target = cands[0]
        try:
            conn = serial.Serial(port=target, baudrate=115200, timeout=1)
            time.sleep(1.5)
            with self.lock:
                self.serial_conn = conn
                self.com_port = target
            self.serial_connected = True
            self._log("info", f"HomeBot serial up on {target}.")
        except Exception as e:
            logger.debug(f"HomeBot serial failed on {target}: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.broker_connected = True
            client.subscribe(SUB_WILDCARD)
            self._publish(STATUS_TOPIC, {"type": "status_request"})
        else:
            self.broker_connected = False
            self._log("warning", f"HomeBot MQTT refused, rc={rc}.")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.broker_connected = False
        self._log("warning", f"HomeBot MQTT disconnected (rc={rc}); supervisor will retry.")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
            data = json.loads(payload) if payload else {}
        except Exception:
            data = {"raw": str(getattr(msg.payload, "decode", lambda *a: "?")())}
        if not isinstance(data, dict):
            data = {"raw": str(data)[:200]}
        # Ignore our own status_request echo (we subscribe to our own
        # namespace) — only genuine bot traffic marks the bot seen.
        if data == {"type": "status_request"}:
            return
        with self.lock:
            self.last_seen = time.time()
            self.connected = True
            if msg.topic == TELE_TOPIC:
                self.latest_status = data
                s = data.get("sensors")
                self.latest_sensors = s if isinstance(s, dict) else data
            elif msg.topic in (STATUS_TOPIC, HEARTBEAT_TOPIC, EVENTS_TOPIC):
                self.latest_status = data

    def _publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        with self.lock:
            client = self.client
            ok = self.broker_connected
        if not client or not ok:
            return False
        try:
            info = client.publish(topic, json.dumps(payload))
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.debug(f"HomeBot publish failed: {e}")
            return False

    # -- commands ------------------------------------------------------------
    MOTIONS = {
        "forward": {"vx": 1.0}, "back": {"vx": -1.0},
        "left": {"vy": -1.0}, "right": {"vy": 1.0},
        "spinleft": {"wz": 1.0}, "spinright": {"wz": -1.0},
    }

    def command(self, name: str, duration: float = 1.0, speed: int = 80) -> Dict[str, Any]:
        name = (name or "").strip().lower()
        if name in ("stop", "halt", "estop"):
            return self._send({"stop": True} if name == "stop" else
                              ({"emergency_stop": True} if name == "estop" else {"stop": True}),
                              label="STP", duration=0)
        if name in self.MOTIONS:
            mag = round(max(0, min(int(speed), 100)) / 100.0, 3)
            motion = {k: round(v * mag, 3) for k, v in self.MOTIONS[name].items()}
            full = {"vx": 0.0, "vy": 0.0, "wz": 0.0}
            full.update(motion)
            return self._send({"motion": full}, label=name.upper()[:3], duration=duration)
        if name == "autonomy_on":
            return self._send({"autonomy": True}, label="AUTO+", duration=0)
        if name == "autonomy_off":
            return self._send({"autonomy": False}, label="AUTO-", duration=0)
        if name.startswith("say ") or name.startswith("express "):
            return self._send({"expression": name.split(None, 1)[1]}, label="EXPR", duration=0)
        if name == "status_refresh":
            ok = self._publish(STATUS_TOPIC, {"type": "status_request"})
            return {"status": "success" if ok else "unavailable",
                    "message": "Sensor refresh requested." if ok else "No MQTT link."}
        return {"status": "unavailable",
                "reason": f"Unknown bot command '{name}'. Try forward/back/left/right/spinleft/spinright/stop."}

    def _send(self, payload: Dict[str, Any], label: str, duration: float) -> Dict[str, Any]:
        if self._publish(CMD_TOPIC, payload):
            with self.lock:
                self.current_command = label
            if duration and duration > 0:
                t = threading.Timer(duration, lambda: self._send({"stop": True}, "STP", 0))
                t.daemon = True
                t.start()
            return {"status": "success", "command": label, "via": "mqtt"}
        # Serial fallback: firmware line commands (best-effort).
        with self.lock:
            conn = self.serial_conn
            ok = self.serial_connected
        if conn and ok:
            try:
                conn.write(f"{label}\n".encode())
                conn.flush()
                with self.lock:
                    self.current_command = label
                return {"status": "success", "command": label, "via": "serial"}
            except Exception as e:
                return {"status": "error", "reason": str(e)}
        return {"status": "unavailable",
                "reason": "Core2 not linked (no MQTT broker / no USB serial). "
                          "Plug the Core2 in or set MQTT_BROKER."}

    def link_quality(self) -> str:
        """live: bot heard <30s ago. stale: heard before, now quiet. never."""
        with self.lock:
            if not self.last_seen:
                return "never"
            age = time.time() - self.last_seen
        if age < 30:
            return "live"
        return "stale"

    def status(self) -> Dict[str, Any]:
        with self.lock:
            age = round(time.time() - self.last_seen, 1) if self.last_seen else None
            return {"transport": ("mqtt" if self.broker else "serial" if self.com_port else "none"),
                    "broker": self.broker or None,
                    "com_port": self.com_port or None,
                    "broker_connected": self.broker_connected,
                    "serial_connected": self.serial_connected,
                    "bot_seen": self.connected,
                    "link": self.link_quality() if self.connected else "never",
                    "last_seen_age_s": age,
                    "current_command": self.current_command,
                    "telemetry": self.latest_status,
                    "sensors": self.latest_sensors,
                    "ports": scan_ports(),
                    "recent_logs": self.logs[-10:]}
