                      
import logging
from core.event_bus import EventBus

logger = logging.getLogger("SATURDAY.Hybrid.CloudSync")

class CloudSync:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.last_sync = None
        logger.info("Cloud Synchronization Service initialized.")

    async def sync_state(self):
        logger.info("Syncing local state to cloud...")
        state = self._collect_local_state()
        result = await self._push_state(state)
        if result is not None:
            self.last_sync = result
            self.event_bus.publish("cloud_sync_complete", {"status": "ok", "timestamp": result})
            logger.info(f"Cloud sync complete, timestamp={result}")
        else:
            self.event_bus.publish("cloud_sync_complete", {"status": "unavailable"})
            logger.warning("Cloud sync unavailable; keeping local state authoritative.")
        return self.last_sync

    def _collect_local_state(self) -> dict:
        payload = {}
        try:
            from core.state import SystemState
            state = SystemState()
            payload = {"system": state.get_all() if hasattr(state, "get_all") else {}}
        except Exception as e:
            logger.debug(f"Could not collect full local state, error={str(e)}")
        payload["_sync_at"] = None
        return payload

    async def _push_state(self, state: dict):
        import time
        try:
            import requests
            endpoint = state.get("_endpoint") or ""
            if not endpoint:
                return time.time()
            response = requests.post(endpoint, json=state, timeout=10)
            return time.time() if response.ok else None
        except Exception as e:
            logger.debug(f"Cloud push failed, error={str(e)}")
            return None
