# embodied/gesture_model.py
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

class GestureModel:
    def __init__(self, model_path="models/gesture_model.pkl"):
        self.model_path = model_path
        self.model = None

    def train(self, X, y):
        """
        X: list of flattened landmark vectors
        y: gesture labels
        """
        self.model = RandomForestClassifier(n_estimators=200)
        self.model.fit(X, y)
        joblib.dump(self.model, self.model_path)

    def load(self):
        self.model = joblib.load(self.model_path)

    def predict(self, landmarks):
        if self.model is None:
            return None
        landmarks = np.array(landmarks).reshape(1, -1)
        return self.model.predict(landmarks)[0]
