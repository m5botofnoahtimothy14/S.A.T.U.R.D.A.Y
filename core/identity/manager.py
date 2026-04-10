                     
import uuid
from core.event_bus import EventBus
from core.logging_config import AEGISLogger

logger = AEGISLogger.get_logger("Identity", "identity")

class IdentityManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.sessions = {}

    async def create_session(self, user_profile: dict):
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = user_profile
        logger.info("Session created", session_id=session_id)
        return session_id

    async def get_session(self, session_id: str):
        return self.sessions.get(session_id)
