                            
from embodied.gesture_model import GestureModel
import numpy as np

class GestureMapper:
    def __init__(self):
        self.model = GestureModel()
        try:
            self.model.load()
        except:
            self.model = None

    def map_gesture(self, landmarks):
        if not landmarks or not self.model:
            return None

        flat = []
        for lm in landmarks[0].landmark:
            flat.extend([lm.x, lm.y, lm.z])

        return self.model.predict(flat)
