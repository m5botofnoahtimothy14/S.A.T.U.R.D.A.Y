# hybrid/edith/screen_nav.py
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.EDITH.Navigation")

class EdithScreenNavigator:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        logger.info("EDITH Screen Navigator initialized.")

    def navigate_to(self, screen_id: str):
        logger.info(f"EDITH Navigating to: {screen_id}")
        # Screen navigation logic here
        self.event_bus.publish("screen_change", {"target": screen_id})
