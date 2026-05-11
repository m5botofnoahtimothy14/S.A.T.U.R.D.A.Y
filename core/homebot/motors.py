                   
import os
import paho.mqtt.client as mqtt
import logging

logger = logging.getLogger("SATURDAY.HomeBot.Motors")

class OmniMotors:
    def __init__(self, mqtt_broker=None):
        self.mqtt_broker = mqtt_broker or os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = mqtt.Client("SATURDAY-Motors")
        self.motors = {"FL": 0, "FR": 0, "BL": 0, "BR": 0}
        self.encoders = {"FL": 0, "FR": 0, "BL": 0, "BR": 0}
        
    def connect(self):
        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
            logger.info("Motors controller connected to MQTT broker")
        except Exception as e:
            logger.error("Failed to connect motors to MQTT", error=str(e))

    def set_motor(self, motor_name, speed):
        self.motors[motor_name] = speed
        self.client.publish(f"homebot/motor/{motor_name}", str(speed))
        logger.info(f"Motor {motor_name} set to {speed}")

    def move(self, x=0, y=0, rotation=0, duration=1):
        fl = y + x + rotation
        fr = y - x - rotation
        bl = y - x + rotation
        br = y + x - rotation

        max_speed = max(abs(fl), abs(fr), abs(bl), abs(br), 100)
        fl = int(fl / max_speed * 100)
        fr = int(fr / max_speed * 100)
        bl = int(bl / max_speed * 100)
        br = int(br / max_speed * 100)

        self.set_motor("FL", fl)
        self.set_motor("FR", fr)
        self.set_motor("BL", bl)
        self.set_motor("BR", br)

        logger.info(f"Omni move: x={x}, y={y}, rotation={rotation}, duration={duration}")
        import time
        time.sleep(duration)
        self.stop()

    def stop(self):
        for motor in self.motors:
            self.set_motor(motor, 0)
        logger.info("All motors stopped")
        
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
