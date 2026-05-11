                  

import logging
import psutil
import threading
import time
logger = logging.getLogger("SATURDAY.Security")
logger.setLevel(logging.INFO)
class SecurityMonitor:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.monitoring = False
    def start_monitoring(self):
        self.monitoring = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("Security monitoring started.")
    def _monitor_loop(self):
        while self.monitoring:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            if cpu > 85 or mem > 90:
                logger.warning(f"High resource usage detected - CPU: {cpu}% MEM: {mem}%")
                self.event_bus.publish("security_alert", {"cpu": cpu, "mem": mem})
            time.sleep(2)
