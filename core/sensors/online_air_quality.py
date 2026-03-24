# sensors/online_air_quality.py
import logging
import aiohttp
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Sensors.AirQuality")

class AirQualitySensor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.api_url = "https://api.waqi.info/feed/here/?token=demo" # Example
        logger.info("Online Air Quality module initialized.")

    async def fetch_current_aqi(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        aqi = data.get('data', {}).get('aqi')
                        self.event_bus.publish("environment_info", {"type": "AQI", "value": aqi})
                        logger.info(f"Current AQI: {aqi}")
        except Exception as e:
            logger.error(f"Failed to fetch air quality: {e}")
