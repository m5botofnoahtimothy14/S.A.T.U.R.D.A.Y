# health/fusion.py
import numpy as np

class HealthDataFusion:
    def __init__(self):
        self.weights = {
            "pose": 0.4,
            "accelerometer": 0.3,
            "vitals": 0.3
        }
        self.data = {}

    def update(self, source, value):
        self.data[source] = value

    def compute_risk_score(self):
        score = 0
        for k, w in self.weights.items():
            score += w * self.data.get(k, 0)
        return score

    def is_high_risk(self):
        return self.compute_risk_score() > 0.7
