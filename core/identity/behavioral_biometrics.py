                                   
import structlog
import time
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.Identity.Biometrics")

class BehavioralBiometrics:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.key_press_times = []
        self.event_bus.subscribe("keystroke_event", self.record_event)

    async def record_event(self, event_data: dict):
                                            
        timestamp = time.time()
        self.key_press_times.append(timestamp)
        
        if len(self.key_press_times) > 10:
            diffs = [self.key_press_times[i] - self.key_press_times[i-1] for i in range(1, len(self.key_press_times))]
            avg_speed = sum(diffs) / len(diffs)
            logger.debug("Typing cadence analyzed", avg_speed=avg_speed)
            
            if avg_speed < 0.05:                                    
                self.event_bus.publish("security_alert", {"reason": "Anomalous typing speed detected"})
            
            self.key_press_times = self.key_press_times[-10:]                    
