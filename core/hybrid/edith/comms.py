                       
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.EDITH.Comms")

class EdithComms:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        logger.info("EDITH Communications Module initialized.")

    def send_transmission(self, destination: str, message: str):
        logger.info(f"EDITH Transmitting to {destination}: {message}")
                                 
        self.event_bus.publish("transmission_sent", {"to": destination, "msg": message})
