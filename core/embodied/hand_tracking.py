                           
import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

DEFAULT_MODEL = os.getenv("HAND_LANDMARKER_PATH", "D:/SATURDAY/models/hand_landmarker.task")

class HandTracker:
    
    def __init__(self, model_path: str = DEFAULT_MODEL, num_hands: int = 2):
        if os.path.exists(model_path):
            base = mp.tasks.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base,
                num_hands=num_hands,
                running_mode=vision.RunningMode.IMAGE,
            )
            self.landmarker = vision.HandLandmarker.create_from_options(options)
        else:
            self.landmarker = None
        self.cap = cv2.VideoCapture(0)

    def detect(self):
        if self.landmarker is None:
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        return self.landmarker.detect(mp_image)
