# identity/face_id.py
import logging
import asyncio
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Identity.FaceID")

class FaceID:
    """
    Subsystem for personalizing recognition.
    Subscribes to vision_events rather than opening its own camera.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active = False
        self.known_faces = [] # Placeholder for database
        
        # Subscribe to vision events from the central provider
        self.event_bus.subscribe("vision_event", self._on_vision_event)
        logger.info("FaceID (Subsystem) initialized.")

    def _on_vision_event(self, data):
        if not data or data.get("type") != "human_status":
            return
            
        count = data.get("count", 0)
        face_b64 = data.get("face_image")
        
        recognized_name = ""
        recognized = False
        
        if count > 0 and face_b64 and self.active:
            recognized_name = self._verify_face(face_b64)
            recognized = bool(recognized_name)

        self.event_bus.publish("identity_event", {
            "type": "human_presence",
            "count": count,
            "recognized": recognized,
            "name": recognized_name or "Unknown"
        })

    def _verify_face(self, face_b64: str) -> str:
        try:
            from deepface import DeepFace
            import cv2
            import base64
            import numpy as np
            import os

            # Decode the base64 string
            img_data = base64.b64decode(face_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # DeepFace needs a persistent directory of known face images
            db_path = "data/faces"
            os.makedirs(db_path, exist_ok=True)
            
            # Fast abort if no faces are registered
            if not any(f.endswith(('.jpg', '.jpeg', '.png')) for f in os.listdir(db_path)):
                return ""

            # Perform neural verification
            dfs = DeepFace.find(img_path=img, db_path=db_path, enforce_detection=False, silent=True)
            if len(dfs) > 0 and not dfs[0].empty:
                # The 'identity' column holds the matched image path.
                match_path = dfs[0].iloc[0]['identity']
                # e.g. "data/faces/tony_stark.jpg" -> "Tony Stark"
                name = os.path.basename(match_path).split('.')[0].replace('_', ' ').title()
                logger.debug(f"Real verification successful: Found {name}")
                return name
        except Exception as e:
            logger.debug(f"Face verification failed: {e}")
            
        return ""

    def start_recognition(self):
        self.active = True
        logger.info("Face identification logic active.")

    def stop_recognition(self):
        self.active = False
