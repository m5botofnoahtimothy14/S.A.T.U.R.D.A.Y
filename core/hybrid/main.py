# hybrid/main.py
from core.event_bus import EventBus
from core.logging_config import AEGISLogger
from .virtual_ai import VirtualAI
from .session_manager import SessionManager
from .wake_service import WakeService
from .cloud_sync import CloudSync

logger = AEGISLogger.get_logger("Hybrid", "hybrid")

class HybridManager:
    def __init__(self, event_bus: EventBus, llm_engine=None):
        self.event_bus = event_bus
        self.virtual_ai = VirtualAI(event_bus, llm_engine)
        self.session_manager = SessionManager(event_bus)
        self.wake_service = WakeService(event_bus)
        self.cloud_sync = CloudSync(event_bus)
        
        logger.info("Hybrid Manager initialized.")

    async def start(self):
        logger.info("Starting Hybrid services...")
        await self.wake_service.listen_for_wake_word()
