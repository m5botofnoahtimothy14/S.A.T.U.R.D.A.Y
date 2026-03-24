# hybrid/edith/voice_interface.py
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.EDITH.Voice")

class EdithVoiceInterface:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        logger.info("EDITH Voice Interface initialized.")

    def process_voice_input(self, text: str):
        logger.info(f"EDITH Voice Input: {text}")
        if "edith" in text.lower():
            self.event_bus.publish("edith_activated", {"command": text})
