# health/sensor_hub.py
import logging
import threading
import time
import random

logger = logging.getLogger("AEGIS.Health.Hub")

class SensorHub:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False

    def start_polling(self):
        self.active = True
        threading.Thread(target=self._hub_loop, daemon=True).start()

    def _hub_loop(self):
        while self.active:
            # Removed mock random simulations. 
            # In a fully real architecture, this hub should wait for Bluetooth/WiFi 
            # health peripherals (like an Apple Watch or Garmin over API) instead of generating rand data.
            # Real camera heart-rate (rPPG) is handled by the Vision system simultaneously.
            time.sleep(10)
