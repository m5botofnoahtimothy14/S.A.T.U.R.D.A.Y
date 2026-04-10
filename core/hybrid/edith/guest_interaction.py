                                   
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.EDITH.Guests")

class EdithGuestInteraction:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        logger.info("EDITH Guest Interaction initialized.")

    def identify_guest(self, facial_features):
        logger.info("EDITH identifying guest...")
                                     
        return "Unknown Guest"

    def greet_guest(self, guest_name: str):
        logger.info(f"EDITH greeting guest: {guest_name}")
        self.event_bus.publish("voice_response", f"Welcome, {guest_name}. How can EDITH assist you today?")
