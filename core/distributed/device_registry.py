# distributed/device_registry.py
import structlog
from core.event_bus import EventBus
import uuid

logger = structlog.get_logger("AEGIS.Distributed.Registry")

class DeviceRegistry:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.devices = {}
        self.local_id = str(uuid.uuid4())
        logger.info("Local Device ID Generated", id=self.local_id)

    async def register_device(self, device_info: dict):
        device_id = device_info.get("id")
        self.devices[device_id] = device_info
        logger.info("New device registered in AEGIS mesh", device=device_id)
        self.event_bus.publish("mesh_update", {"total_devices": len(self.devices)})

    def get_all_devices(self):
        return self.devices
