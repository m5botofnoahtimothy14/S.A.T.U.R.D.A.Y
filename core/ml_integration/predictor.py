                             
import os
import json
import time
import structlog
from typing import Any, Dict, List
from collections import deque

import numpy as np

logger = structlog.get_logger("SATURDAY.ML.Predictor")

class PredictiveEngine:
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.data_dir = "data/ml_integration"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.prediction_history = deque(maxlen=100)
        self.time_series_buffers = {}
        
        self._init_predictors()
        
    def _init_predictors(self):
        
        self.predictors = {
            "health": self._predict_health,
            "behavior": self._predict_behavior,
            "system": self._predict_system,
            "communication": self._predict_communication,
            "resource": self._predict_resource
        }
        
    def add_data_point(self, predictor_type: str, value: float, metadata: Dict = None):
        
        if predictor_type not in self.time_series_buffers:
            self.time_series_buffers[predictor_type] = deque(maxlen=50)
            
        self.time_series_buffers[predictor_type].append({
            "value": value,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        
    def predict(self, predictor_type: str, horizon: int = 5) -> Dict[str, Any]:
        
        if predictor_type not in self.time_series_buffers:
            return {"error": "No data for prediction"}
            
        data = list(self.time_series_buffers[predictor_type])
        
        if len(data) < 10:
            return {"error": "Insufficient data for prediction"}
            
        values = [d["value"] for d in data]
        
        prediction = self._linear_predict(values, horizon)
        
        confidence = self._calculate_confidence(values)
        
        self.prediction_history.append({
            "type": predictor_type,
            "prediction": prediction,
            "horizon": horizon,
            "confidence": confidence,
            "timestamp": time.time()
        })
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "horizon": horizon,
            "type": predictor_type,
            "based_on": len(values)
        }
        
    def _linear_predict(self, values: List[float], horizon: int) -> float:
        
        n = len(values)
        if n < 2:
            return values[-1] if values else 0.0
            
        x = np.arange(n)
        y = np.array(values)
        
        coeffs = np.polyfit(x, y, 1)
        
        predicted = coeffs[0] * (n + horizon - 1) + coeffs[1]
        
        return float(np.clip(predicted, 0, 100))
        
    def _calculate_confidence(self, values: List[float]) -> float:
        
        if len(values) < 5:
            return 0.3
            
        std = np.std(values)
        mean = np.mean(values)
        
        if mean == 0:
            return 0.5
            
        cv = std / mean
        
        confidence = max(0.1, 1.0 - cv)
        
        return float(confidence)
        
    def _predict_health(self, data: Dict) -> Dict:
        
        return self.predict("health")
        
    def _predict_behavior(self, data: Dict) -> Dict:
        
        return self.predict("behavior")
        
    def _predict_system(self, data: Dict) -> Dict:
        
        return self.predict("system")
        
    def _predict_communication(self, data: Dict) -> Dict:
        
        return self.predict("communication")
        
    def _predict_resource(self, data: Dict) -> Dict:
        
        return self.predict("resource")
        
    def get_status(self) -> Dict:
        
        return {
            "predictors": list(self.predictors.keys()),
            "data_buffers": {k: len(v) for k, v in self.time_series_buffers.items()},
            "predictions_made": len(self.prediction_history)
        }
