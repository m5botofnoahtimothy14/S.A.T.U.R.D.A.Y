                           
import logging
import uuid
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Hybrid.SessionManager")

class SessionManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active_sessions = {}
        logger.info("Hybrid Session Manager initialized.")

    def create_session(self, user_id: str):
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {"user_id": user_id, "start_time": "now"}
        return session_id
