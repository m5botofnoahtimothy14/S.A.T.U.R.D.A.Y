
import time
import threading
import psutil
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.USBWatchdog")

class USBWatchdog:
    def __init__(self, event_bus: EventBus, interval: float = 5.0):
        self.event_bus = event_bus
        self.interval = interval
        self.running = False
        self._seen = set(p.device for p in psutil.disk_partitions(all=False))

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        logger.info("USB watchdog started.")

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                current = set(p.device for p in psutil.disk_partitions(all=False))
                new = current - self._seen
                removed = self._seen - current
                for dev in new:
                    self.event_bus.publish("usb_attached", {"device": dev})
                    logger.info(f"USB attached: {dev}")
                for dev in removed:
                    self.event_bus.publish("usb_detached", {"device": dev})
                    logger.info(f"USB detached: {dev}")
                self._seen = current
            except Exception as e:
                logger.warning(f"USB watchdog error: {e}")
            time.sleep(self.interval)
