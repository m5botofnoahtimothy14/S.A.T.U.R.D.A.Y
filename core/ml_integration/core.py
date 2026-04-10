                        
import os
import json
import time
import threading
import asyncio
from typing import Any, Dict, List, Optional
from collections import deque, defaultdict
import numpy as np
from core.logging_config import AEGISLogger

logger = AEGISLogger.get_logger("ML.Core", "ml")

class SubsystemNeuralNetwork:
    
    def __init__(self, name: str, input_size: int = 15, hidden_size: int = 30, output_size: int = 5):
        self.name = name
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        np.random.seed(hash(name) % 10000)
        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
        
        self.training_buffer = deque(maxlen=200)
        
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def relu_derivative(self, x):
        return (x > 0).astype(float)
    
    def softmax(self, x):
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()
    
    def forward(self, inputs: np.ndarray) -> np.ndarray:
        self.hidden = self.relu(np.dot(inputs, self.weights1) + self.bias1)
        output = self.softmax(np.dot(self.hidden, self.weights2) + self.bias2)
        return output
    
    def predict(self, features: np.ndarray) -> tuple:
        output = self.forward(features)[0]
        return output
    
    def train(self, X: np.ndarray, y: np.ndarray, epochs: int = 20, lr: float = 0.01):
        for _ in range(epochs):
            output = self.forward(X)
            error = y - output
            
            output_delta = error
            hidden_error = np.dot(output_delta, self.weights2.T)
            hidden_delta = hidden_error * self.relu_derivative(self.hidden)
            
            self.weights2 += lr * np.dot(self.hidden.T, output_delta)
            self.weights1 += lr * np.dot(X.T, hidden_delta)
            self.bias2 += lr * output_delta
            self.bias1 += lr * hidden_delta
    
    def add_experience(self, features: np.ndarray, label: int):
        self.training_buffer.append((features, label))
    
    def learn_from_buffer(self):
        if len(self.training_buffer) < 10:
            return False
            
        X = np.array([e[0] for e in self.training_buffer])
        y = np.array([e[1] for e in self.training_buffer])
        
        y_onehot = np.zeros((len(y), self.output_size))
        for i, label in enumerate(y):
            if label < self.output_size:
                y_onehot[i, label] = 1.0
        
        self.train(X, y_onehot, epochs=10, lr=0.01)
        return True

class MLIntegrationCore:
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, event_bus=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, event_bus=None):
        if hasattr(self, '_initialized'):
            return
            
        self.event_bus = event_bus
        self.data_dir = "data/ml_integration"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.subsystem_networks: Dict[str, SubsystemNeuralNetwork] = {}
        self.subsystem_stats: Dict[str, Dict] = defaultdict(dict)
        
        self._register_default_subsystems()
        self._load_models()
        
        self.running = True
        
        logger.info("ML Integration Core initialized - ALL subsystems now use DL/ML")
        self._initialized = True
        
    def _register_default_subsystems(self):
        
        subsystems = [
            ("health", 15, 30, 5),
            ("identity", 20, 40, 8),
            ("communication", 25, 50, 10),
            ("vision", 30, 60, 12),
            ("voice", 20, 40, 8),
            ("gesture", 15, 30, 6),
            ("security", 20, 40, 8),
            ("christianity", 15, 30, 5),
            ("homebot", 20, 40, 8),
            ("ui", 15, 30, 6),
            ("music", 10, 20, 4),
            ("calendar", 15, 30, 5),
            ("email", 20, 40, 8),
            ("social", 15, 30, 6),
            ("sensors", 20, 40, 8),
            ("distributed", 15, 30, 5),
        ]
        
        for name, inp, hid, out in subsystems:
            self.register_subsystem(name, inp, hid, out)
            
    def register_subsystem(self, name: str, input_size: int = 15, hidden_size: int = 30, output_size: int = 5):
        
        if name not in self.subsystem_networks:
            self.subsystem_networks[name] = SubsystemNeuralNetwork(name, input_size, hidden_size, output_size)
            self.subsystem_stats[name] = {
                "experiences": 0,
                "predictions": 0,
                "accuracy": 0.0,
                "last_update": time.time()
            }
            logger.info(f"Registered subsystem with ML: {name}")
            
    def predict(self, subsystem: str, features: List[float]) -> Dict[str, Any]:
        
        if subsystem not in self.subsystem_networks:
            self.register_subsystem(subsystem)
            
        nn = self.subsystem_networks[subsystem]
        
        while len(features) < nn.input_size:
            features.append(0.5)
            
        X = np.array([features[:nn.input_size]])
        
        try:
            output = nn.predict(X)
            self.subsystem_stats[subsystem]["predictions"] += 1
            self.subsystem_stats[subsystem]["last_update"] = time.time()
            
            return {
                "success": True,
                "predictions": output.tolist(),
                "subsystem": subsystem,
                "confidence": float(np.max(output))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def learn(self, subsystem: str, features: List[float], label: int):
        
        if subsystem not in self.subsystem_networks:
            self.register_subsystem(subsystem)
            
        nn = self.subsystem_networks[subsystem]
        
        while len(features) < nn.input_size:
            features.append(0.5)
            
        X = np.array([features[:nn.input_size]])
        
        nn.add_experience(X, label)
        self.subsystem_stats[subsystem]["experiences"] += 1
        
        if len(nn.training_buffer) >= 20:
            nn.learn_from_buffer()
            logger.info(f"ML model updated for {subsystem}")
            
    def batch_learn(self, subsystem: str, data: List[tuple]):
        
        if subsystem not in self.subsystem_networks:
            self.register_subsystem(subsystem)
            
        nn = self.subsystem_networks[subsystem]
        
        for features, label in data:
            while len(features) < nn.input_size:
                features.append(0.5)
            X = np.array([features[:nn.input_size]])
            nn.add_experience(X, label)
            
        nn.learn_from_buffer()
        self.subsystem_stats[subsystem]["experiences"] += len(data)
        
    def analyze_and_decide(self, subsystem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        
        features = self._context_to_features(context)
        
        result = self.predict(subsystem, features)
        
        if result.get("success"):
            predictions = result["predictions"]
            best_action_idx = int(np.argmax(predictions))
            confidence = float(predictions[best_action_idx])
            
            actions = self._get_subsystem_actions(subsystem)
            action = actions[best_action_idx] if best_action_idx < len(actions) else "monitor"
            
            return {
                "action": action,
                "confidence": confidence,
                "reasoning": f"DL analysis of {subsystem}: {action}",
                "subsystem": subsystem,
                "neural_output": predictions
            }
        
        return {"action": "fallback", "confidence": 0.0, "subsystem": subsystem}
        
    def _context_to_features(self, context: Dict) -> List[float]:
        
        features = []
        
        numeric_keys = [
            "value", "score", "level", "percent", "count", "temp", 
            "humidity", "pressure", "battery", "cpu", "memory"
        ]
        
        for key in numeric_keys:
            if key in context:
                features.append(float(context[key]) / 100.0 if float(context[key]) <= 100 else 0.5)
            else:
                features.append(0.5)
                
        if "status" in context:
            status_vals = {"ok": 0.8, "warning": 0.5, "error": 0.2, "critical": 0.1}
            features.append(status_vals.get(str(context["status"]).lower(), 0.5))
        else:
            features.append(0.5)
            
        features.append(time.time() % 86400 / 86400.0)
        
        return features
        
    def _get_subsystem_actions(self, subsystem: str) -> List[str]:
        
        actions = {
            "health": ["monitor", "alert", "treat", "escalate", "ignore"],
            "identity": ["verify", "deny", "review", "escalate", "allow"],
            "communication": ["send", "queue", "delay", "block", "prioritize"],
            "vision": ["track", "recognize", "alert", "record", "ignore"],
            "voice": ["process", "ignore", "clarify", "respond", "wait"],
            "security": ["block", "allow", "log", "escalate", "monitor"],
            "christianity": ["pray", "reflect", "study", "share", "meditate"],
            "homebot": ["move", "stop", "charge", "scan", "wait"],
            "ui": ["show", "hide", "animate", "update", "keep"],
            "music": ["play", "skip", "pause", "volume_up", "volume_down"],
            "default": ["proceed", "wait", "stop", "adapt", "learn"]
        }
        
        return actions.get(subsystem, actions["default"])
        
    def get_subsystem_status(self, subsystem: str) -> Dict[str, Any]:
        
        if subsystem not in self.subsystem_networks:
            return {"error": "Subsystem not registered"}
            
        nn = self.subsystem_networks[subsystem]
        
        return {
            "subsystem": subsystem,
            "input_size": nn.input_size,
            "hidden_size": nn.hidden_size,
            "output_size": nn.output_size,
            "experiences": self.subsystem_stats[subsystem]["experiences"],
            "predictions": self.subsystem_stats[subsystem]["predictions"],
            "model_ready": len(nn.training_buffer) >= 10
        }
        
    def get_all_status(self) -> Dict[str, Any]:
        
        return {
            "total_subsystems": len(self.subsystem_networks),
            "subsystems": {name: self.get_subsystem_status(name) for name in self.subsystem_networks}
        }
        
    def save_models(self):
        
        for name, nn in self.subsystem_networks.items():
            try:
                model_data = {
                    "weights1": nn.weights1.tolist(),
                    "weights2": nn.weights2.tolist(),
                    "bias1": nn.bias1.tolist(),
                    "bias2": nn.bias2.tolist(),
                    "training_buffer_size": len(nn.training_buffer)
                }
                
                with open(f"{self.data_dir}/{name}_model.json", "w") as f:
                    json.dump(model_data, f)
                    
            except Exception as e:
                logger.warning(f"Failed to save {name} model: {e}")
                
        logger.info(f"Saved ML models for {len(self.subsystem_networks)} subsystems")
        
    def _load_models(self):
        
        for name in self.subsystem_networks.keys():
            try:
                model_file = f"{self.data_dir}/{name}_model.json"
                if os.path.exists(model_file):
                    with open(model_file, "r") as f:
                        model_data = json.load(f)
                        
                    nn = self.subsystem_networks[name]
                    nn.weights1 = np.array(model_data.get("weights1"))
                    nn.weights2 = np.array(model_data.get("weights2"))
                    nn.bias1 = np.array(model_data.get("bias1"))
                    nn.bias2 = np.array(model_data.get("bias2"))
                    
                    logger.info(f"Loaded ML model for {name}")
                    
            except Exception as e:
                logger.warning(f"Failed to load {name} model: {e}")
                
    async def start_autonomous_learning(self):
        
        while self.running:
            try:
                for name, nn in self.subsystem_networks.items():
                    if len(nn.training_buffer) >= 15:
                        nn.learn_from_buffer()
                        
                await asyncio.sleep(60)
            except Exception as e:
                logger.warning(f"Autonomous learning error: {e}")
                await asyncio.sleep(60)
                
    async def start_periodic_save(self):
        
        while self.running:
            try:
                await asyncio.sleep(300)
                self.save_models()
            except Exception as e:
                logger.warning(f"Model save error: {e}")
                
    def shutdown(self):
        
        self.running = False
        self.save_models()
        logger.info("ML Integration Core shutdown - Models saved")
