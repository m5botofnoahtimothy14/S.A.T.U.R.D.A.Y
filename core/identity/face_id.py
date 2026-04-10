                     
import logging
import asyncio
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Identity.FaceID")

class FaceID:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active = False
        self.known_faces = []                           
        
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
            from core.deep_learning import setup_for_deepface
            setup_for_deepface()
            
            from deepface import DeepFace
            import cv2
            import base64
            import numpy as np
            import os

            img_data = base64.b64decode(face_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            db_path = "data/faces"
            os.makedirs(db_path, exist_ok=True)
            
            if not any(f.endswith(('.jpg', '.jpeg', '.png')) for f in os.listdir(db_path)):
                return ""

            dfs = DeepFace.find(img_path=img, db_path=db_path, enforce_detection=False, silent=True)
            if len(dfs) > 0 and not dfs[0].empty:
                                                                     
                match_path = dfs[0].iloc[0]['identity']
                                                                  
                name = os.path.basename(match_path).split('.')[0].replace('_', ' ').title()
                logger.debug(f"Real verification successful: Found {name}")
                return name
        except ImportError:
            logger.debug("DeepFace not available for face verification")
        except Exception as e:
            logger.debug(f"Face verification failed: {e}")
            
        return ""

    def start_recognition(self):
        self.active = True
        logger.info("Face identification logic active.")

    def stop_recognition(self):
        self.active = False
