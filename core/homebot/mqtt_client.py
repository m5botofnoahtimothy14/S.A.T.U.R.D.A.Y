# homebot/mqtt_client.py
import os
import paho.mqtt.client as mqtt
import structlog
import asyncio

logger = structlog.get_logger("AEGIS.HomeBot")

class HomeBotClient:
    def __init__(self, broker=None, port=None):
        self.client = mqtt.Client()
        self.broker = broker or os.getenv("MQTT_BROKER", "localhost")
        self.port = int(port or os.getenv("MQTT_PORT", 1883))

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logger.info("Connected to HomeBot MQTT Broker")
        except Exception as e:
            logger.error("Failed to connect to MQTT broker", error=str(e))

    def publish(self, topic, message):
        self.client.publish(topic, message)
        logger.debug("Published message", topic=topic, message=message)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
