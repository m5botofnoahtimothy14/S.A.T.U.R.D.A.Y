# ui/bridge.py
import structlog
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.UI")

class WebUI:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    # In a real app, this would mount Jinja2 templates to the FastAPI app 
    # but for this script we provide the bridge logic.
    def get_context(self):
        return {"status": "Online", "version": "1.1.0"}
