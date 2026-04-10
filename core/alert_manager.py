

import time
import structlog
logger = structlog.get_logger("AEGIS.AlertManager")
class AlertManager:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._last_health_alert_time = 0.0
        self._last_security_alert_time = 0.0
        self.event_bus.subscribe("health_update", self._on_health)
        self.event_bus.subscribe("security_alert", self._on_security)
        self.event_bus.subscribe("vision_event", self._on_vision)
        self.event_bus.subscribe("sound_detected", self._on_sound)
        self.event_bus.subscribe("loud_noise", self._on_loud)
        self.event_bus.subscribe("siren_detected", self._on_siren)
        self.event_bus.subscribe("alarm_tone", self._on_alarm)
    def _on_health(self, data):
        if not isinstance(data, dict):
            return
        cpu = data.get("cpu", 0)
        mem = data.get("memory", 0)
        now = time.monotonic()
        if (cpu > 90 or mem > 92) and (now - self._last_health_alert_time) >= 45:
            self._last_health_alert_time = now
            self._speak(f"Warning: system resources high. CPU {cpu:.0f} percent, memory {mem:.0f} percent.")
    def _on_security(self, data):
        if isinstance(data, dict):
            alert_type = data.get("type", "")
            if alert_type in ["intrusion", "breach", "unauthorized"]:
                now = time.monotonic()
                if (now - self._last_security_alert_time) >= 30:
                    self._last_security_alert_time = now
                    self._speak("Critical security alert detected!")
    def _on_vision(self, data):
        if not isinstance(data, dict):
            return
        if data.get("type") == "human_status":
            count = data.get("count", 0)
            if count >= 3:
                self._speak(f"I see {count} people nearby. Do you want me to engage privacy or alert mode?")
    def _on_sound(self, data):
        pass
    def _on_loud(self, data):
        self._speak("Loud impact detected. Should I record or call for help?")
    def _on_siren(self, data):
        self._speak("Siren detected. Do you want traffic updates or to call emergency contacts?")
    def _on_alarm(self, data):
        self._speak("Alarm tone detected. Should I check cameras or silence alarms?")
    def _speak(self, text: str):
        try:
            self.event_bus.publish("voice_response", text)
        except Exception as e:
            logger.warning("Failed to publish alert voice_response", error=str(e))
