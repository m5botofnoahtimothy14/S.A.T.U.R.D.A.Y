              
import structlog
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.UI")

class WebUI:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    def get_context(self):
        return {"status": "Online", "version": "1.1.0"}
