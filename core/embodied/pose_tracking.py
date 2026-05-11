                           
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

DEFAULT_MODEL = os.getenv("POSE_LANDMARKER_PATH", "D:/SATURDAY/models/pose_landmarker_lite.task")

class PoseTracker:
    
    def __init__(self, model_path: str = DEFAULT_MODEL):
        if os.path.exists(model_path):
            base = mp.tasks.BaseOptions(model_asset_path=model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base,
                running_mode=vision.RunningMode.IMAGE,
            )
            self.landmarker = vision.PoseLandmarker.create_from_options(options)
        else:
            self.landmarker = None

    def detect(self, frame):
        if not self.landmarker:
            return None
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        return self.landmarker.detect(mp_image)
