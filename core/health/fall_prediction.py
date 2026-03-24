# health/fall_prediction.py
import time
import numpy as np

class FallPredictor:
    def __init__(self):
        self.prev_hip_y = None
        self.prev_time = None
        self.fall_detected = False

    def detect_fall(self, pose_landmarks):
        if pose_landmarks is None:
            return False

        hip = pose_landmarks.landmark[23]  # left hip
        current_time = time.time()

        if self.prev_hip_y is not None:
            dy = hip.y - self.prev_hip_y
            dt = current_time - self.prev_time

            velocity = dy / dt if dt > 0 else 0

            # Threshold logic
            if velocity > 0.8:  # sudden downward movement
                self.fall_detected = True

        self.prev_hip_y = hip.y
        self.prev_time = current_time

        return self.fall_detected
