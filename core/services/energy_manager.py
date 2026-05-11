                            
import structlog
import psutil
import asyncio
from core.event_bus import EventBus

logger = structlog.get_logger("SATURDAY.Services.Energy")

class EnergyManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active = False

    async def start(self):
        self.active = True
        logger.info("Energy Manager started.")
        while self.active:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                is_plugged = battery.power_plugged
                logger.debug("Power Status", percent=percent, plugged=is_plugged)
                
                if percent < 20 and not is_plugged:
                    logger.warning("Low Power Mode Triggered")
                    self.event_bus.publish("voice_response", "Battery low. Switching SATURDAY to power-saving mode.")
                    self.event_bus.publish("system_state_change", "low_power")
            
            await asyncio.sleep(300)                     

    async def stop(self):
        self.active = False
