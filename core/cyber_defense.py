                       

import logging
import threading
import time
logger = logging.getLogger("AEGIS.CyberDefense")
logger.setLevel(logging.INFO)
class CyberDefense:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False
        self.event_bus.subscribe("security_alert", self.handle_alert)
    def activate(self):
        self.active = True
        threading.Thread(target=self._active_monitor, daemon=True).start()
        logger.info("Cyber defense activated.")
    def _active_monitor(self):
        while self.active:
            time.sleep(5)
    def handle_alert(self, data):
        logger.info(f"Handling security alert: {data}")
        print(f"[CYBER DEFENSE] Taking action against abnormal usage: {data}")
