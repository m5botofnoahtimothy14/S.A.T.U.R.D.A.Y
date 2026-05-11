                      
import logging
import threading
import time
import random

logger = logging.getLogger("SATURDAY.Health.Hub")

class SensorHub:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False

    def start_polling(self):
        self.active = True
        threading.Thread(target=self._hub_loop, daemon=True).start()

    def _hub_loop(self):
        while self.active:
                                               
            time.sleep(10)
