"""
SecurityAssistant
-----------------
Safety-focused helper that interprets "ethical hacking / diagnostics" requests
and outlines safe steps instead of running intrusive actions automatically.
"""
import structlog
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.SecurityAssistant")


class SecurityAssistant:
    def __init__(self, event_bus: EventBus, ai_engine):
        self.event_bus = event_bus
        self.ai = ai_engine
        self.event_bus.subscribe("voice_command", self._on_voice)

    def _on_voice(self, text: str):
        if not text:
            return
        lower = text.lower()
        if any(k in lower for k in ["scan network", "security check", "ethical hack", "penetration test", "pentest"]):
            self.event_bus.publish("voice_response",
                                   "I’ll draft a safe diagnostic plan. No intrusive actions will run without your OK.")
            # Create an advisory task
            prompt = ("Create a short, safe diagnostic checklist for a local network (no active exploitation). "
                      "Include: 1) inventory devices, 2) check open ports with consent, 3) verify patches, "
                      "4) review credentials and MFA, 5) backup and logging review. Keep to 5 bullets.")
            self.event_bus.publish("task_request", {"type": "security_plan", "prompt": prompt})
