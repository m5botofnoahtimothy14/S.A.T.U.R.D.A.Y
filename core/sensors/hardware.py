# sensors/hardware.py
import structlog
import cv2

logger = structlog.get_logger("AEGIS.Sensors")

class HardwareInterface:
    def __init__(self):
        self.camera = None

    def get_camera(self):
        if self.camera is None:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                logger.error("Failed to open camera hardware.")
                self.camera = None
        return self.camera

    def release_all(self):
        if self.camera:
            self.camera.release()
            logger.info("Camera released.")
