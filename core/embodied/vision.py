# embodied/vision.py
import logging
import cv2
import asyncio
import numpy as np
import threading
import time
from typing import Optional
from health.rppg_engine import RPPGEngine

try:
    import mss
except ImportError:
    mss = None

class EmotionDetector:
    def __init__(self):
        try:
            from deepface import DeepFace
            self.DeepFace = DeepFace
            # Run a dummy detect to download and cache the weights on init
            import numpy as np
            dummy_face = np.zeros((224, 224, 3), dtype=np.uint8)
            try:
                self.DeepFace.analyze(dummy_face, actions=['emotion'], enforce_detection=False)
            except Exception:
                pass
        except ImportError:
            self.DeepFace = None
            logger.warning("DeepFace not installed. Emotion detection will fallback to mock.")

    def detect(self, face_frame):
        if self.DeepFace:
            try:
                # Use enforce_detection=False because the cropped frame is already a face box
                results = self.DeepFace.analyze(face_frame, actions=['emotion'], enforce_detection=False)
                if isinstance(results, list):
                    res = results[0]
                else:
                    res = results
                dominant = res.get('dominant_emotion', 'neutral').capitalize()
                return {"primary": dominant, "confidence": res.get('emotion', {}).get(dominant.lower(), 50.0) / 100.0}
            except Exception as e:
                logger.debug(f"DeepFace analysis skipped/failed: {e}")
        return {"primary": "Calm", "confidence": 0.8}

logger = logging.getLogger("AEGIS.Vision")

class VisionModule:
    """
    Unified Vision System for AEGIS.
    Handles Camera, Screen, Heart Rate (rPPG), and Mood Detection.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_camera_frame = None
        self.last_screen_frame = None
        
        # Detectors
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.last_camera_frame = None  # Shared frame buffer for broadcast
        self.rppg = RPPGEngine(event_bus)
        self.emotions = EmotionDetector()
        
        self.power_mode = "performance"
        logger.info("Vision System Initialized with Health & Mood tracking.")

    async def start(self):
        if self.active: return
        self.active = True
        self.event_bus.subscribe("power_mode", self._on_power_mode)
        
        threading.Thread(target=self._camera_loop, daemon=True).start()
        threading.Thread(target=self._screen_loop, daemon=True).start()
        logger.info("Vision System: High-intensity observation active.")

    def _on_power_mode(self, data):
        self.power_mode = data.get("mode", "performance")

    def _camera_loop(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            logger.error("Vision System: Physical camera unavailable.")
            return
        
        while self.active:
            if self.power_mode == "low":
                time.sleep(2.0) # Ultra-low frequency in idle
            
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(1)
                continue
                
            self.last_camera_frame = frame
            
            # 1. Processing Pipeline
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) > 0:
                # Heart Rate Detection (rPPG)
                self.rppg.process_frame(frame, faces)
                
                # Mood Detection
                x, y, w, h = faces[0]
                face_crop = frame[y:y+h, x:x+w]
                mood = self.emotions.detect(face_crop)
                
                import base64
                _, buffer = cv2.imencode('.jpg', face_crop)
                face_b64 = base64.b64encode(buffer).decode('utf-8')
                
                self.event_bus.publish("vision_event", {
                    "type": "human_status", 
                    "count": len(faces),
                    "mood": mood["primary"],
                    "faces": faces.tolist(),
                    "face_image": face_b64
                })
            
            # 2. Surroundings/Noise Integration
            # We use frame difference for motion detection if needed
            self.event_bus.publish("environment_event", {"type": "surroundings_active"})
            
            time.sleep(0.05 if self.power_mode == "performance" else 1.0)

        self.cap.release()

    def _screen_loop(self):
        if not mss: return
        try:
            with mss.mss() as sct:
                while self.active:
                    if self.power_mode == "low":
                        time.sleep(10.0) # Save CPU during idle
                    
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    frame = np.array(sct_img)
                    self.last_screen_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    
                    self.event_bus.publish("screen_event", {"type": "desktop_analysis"})
                    time.sleep(5.0) # Periodic screen checks
        except: pass

    async def stop(self):
        self.active = False
