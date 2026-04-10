                    

import structlog
from core.event_bus import EventBus
logger = structlog.get_logger("AEGIS.AdminMood")
class AdminMood:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.score = 0                                         
        self.mood = "focused"
        event_bus.subscribe("system_alert", self._on_system_alert)
        event_bus.subscribe("vitals_update", self._on_vitals)
        event_bus.subscribe("cooldown", self._on_cooldown)
        event_bus.subscribe("voice_command", self._on_voice_cmd)
    def _on_system_alert(self, data):
        self.score -= 2
        self._update("system_alert")
    def _on_cooldown(self, data):
        self.score -= 3
        self._update("cooldown")
    def _on_vitals(self, data):
        hr = data.get("value", 75) if data.get("type") == "heart_rate" else 75
        if hr > 110:
            self.score -= 0.8                       
        elif hr > 95:
            self.score -= 0.3                   
        else:
            self.score += 0.1             
        self._update("vitals")
    def _on_voice_cmd(self, data):
        self.score += 0.2
        self._update("voice")
    def _update(self, reason: str):
        self.score = max(-10, min(10, self.score))
        if self.score >= 4:
            self.mood = "happy"
        elif self.score >= 0:
            self.mood = "focused"
        elif self.score >= -4:
            self.mood = "stressed"
        else:
            self.mood = "critical"
        self.event_bus.publish(
            "admin_mood_update",
            {"mood": self.mood, "score": round(self.score, 1), "reason": reason},
        )
        logger.info("Admin mood updated", mood=self.mood, score=self.score, reason=reason)
