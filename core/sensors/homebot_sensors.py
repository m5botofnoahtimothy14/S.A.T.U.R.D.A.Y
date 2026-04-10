                            
import logging
import paho.mqtt.client as mqtt
from core.event_bus import EventBus
import json
import threading
import asyncio
import os

logger = logging.getLogger("AEGIS.Sensors.HomeBot")

class HomeBotSensors:
    def __init__(self, event_bus: EventBus, mqtt_broker="localhost"):
        self.event_bus = event_bus
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = mqtt.Client("AEGIS-Sensors")
        self.client.on_message = self._on_mqtt_message
        self.latest_readings = {}
        
    def connect(self):
        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.subscribe("homebot/sensors/#")
            self.client.loop_start()
            logger.info("Sensors connected to MQTT broker")
        except Exception as e:
            logger.error("Failed to connect sensors to MQTT", error=str(e))

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload)
            sensor_id = topic.split('/')[-1]
            self.latest_readings[sensor_id] = payload
                                                    
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.event_bus.publish("sensor_update", {"id": sensor_id, "value": payload}))
            loop.close()
            logger.debug(f"Sensor update: {sensor_id} = {payload}")
        except Exception as e:
            logger.error(f"Error processing sensor message: {e}")

    def read_ultrasonic(self) -> float:
        return self.latest_readings.get("ultrasonic", {}).get("distance", 0.0)

    def read_vibration(self) -> float:
        return self.latest_readings.get("vibration", {}).get("value", 0.0)

    def scan_wifi_heatmap(self) -> dict:
        return self.latest_readings.get("wifi", {})

    async def update_sensor_data(self, sensor_id: str, value: float):
        self.event_bus.publish("sensor_update", {"id": sensor_id, "value": value})
        logger.debug(f"Sensor {sensor_id} updated: {value}")
        
    def request_reading(self, sensor_type: str):
        self.client.publish(f"homebot/sensors/{sensor_type}/read", "1")
        logger.debug(f"Requested {sensor_type} reading")
        
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
