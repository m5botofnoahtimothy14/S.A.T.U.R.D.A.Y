                   
import asyncio
import psutil
import time
import os
import json
from collections import deque
import numpy as np
from core.event_bus import EventBus
from core.logging_config import SATURDAYLogger

logger = SATURDAYLogger.get_logger("Health", "health")

class HealthNeuralNetwork:
    
    def __init__(self, input_size: int = 15, hidden_size: int = 30, output_size: int = 5):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        np.random.seed(42)
        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
        
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def forward(self, inputs):
        self.hidden = self.relu(np.dot(inputs, self.weights1) + self.bias1)
        output = self.sigmoid(np.dot(self.hidden, self.weights2) + self.bias2)
        return output
    
    def predict_health(self, features):
        output = self.forward(features)[0]
        
        actions = ["healthy", "warning", "critical", "recover", "maintain"]
        results = []
        for i, action in enumerate(actions):
            results.append((action, float(output[i])))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def learn(self, features, actual_state, success):
        output = self.forward(features)[0]
        
        actions = ["healthy", "warning", "critical", "recover", "maintain"]
        expected = np.zeros(self.output_size)
        
        if actual_state in actions:
            idx = actions.index(actual_state)
            expected[idx] = 1.0 if success else 0.3
        
        error = expected - output
        output_delta = error
        hidden_error = np.dot(output_delta, self.weights2.T)
        hidden_delta = hidden_error * (self.hidden > 0).astype(float)
        
        self.weights2 += 0.01 * np.dot(self.hidden.T, output_delta)
        self.weights1 += 0.01 * np.dot(features.T, hidden_delta)
        self.bias2 += 0.01 * output_delta
        self.bias1 += 0.01 * hidden_delta

class HealthMonitor:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active = False
        
        self._init_deep_learning()
        
    def _init_deep_learning(self):
        
        try:
            self.health_nn = HealthNeuralNetwork()
            self.health_history = deque(maxlen=100)
            self.prediction_buffer = deque(maxlen=50)
            
            self._load_model()
            
            self.dl_active = True
            logger.info("DEEP LEARNING Health Monitor initialized")
            
        except Exception as e:
            logger.warning(f"DL Health init failed: {e}")
            self.dl_active = False

    def _extract_features(self, stats):
        
        cpu = stats.get("cpu", 0)
        memory = stats.get("memory", 0)
        disk = stats.get("disk", 0)
        
        features = [
            cpu / 100.0,
            memory / 100.0,
            disk / 100.0,
            len(self.health_history) / 100.0,
            self._get_trend(),
            self._get_variance(),
            self._get_health_score(),
            time.time() % 86400 / 86400.0,
            self._get_cpu_acceleration(),
            self._get_memory_pressure(),
            self._get_prediction_accuracy(),
            self._get_recovery_rate(),
            self._get_stability_score(),
            self._get_resource_efficiency(),
            self._get_anomaly_count()
        ]
        
        return np.array([features[:15]])

    def _get_trend(self):
        if len(self.health_history) < 5:
            return 0.5
        recent = list(self.health_history)[-5:]
        cpus = [h.get("cpu", 50) for h in recent]
        return (cpus[-1] - cpus[0]) / 100.0

    def _get_variance(self):
        if len(self.health_history) < 3:
            return 0.0
        cpus = [h.get("cpu", 50) for h in list(self.health_history)[-10:]]
        return np.std(cpus) / 100.0

    def _get_health_score(self):
        if not self.health_history:
            return 0.8
        return sum(1 for h in self.health_history if h.get("state") == "healthy") / len(self.health_history)

    def _get_cpu_acceleration(self):
        if len(self.health_history) < 3:
            return 0.0
        cpus = [h.get("cpu", 50) for h in list(self.health_history)[-3:]]
        return (cpus[-1] - cpus[0]) / 30.0

    def _get_memory_pressure(self):
        return psutil.virtual_memory().percent / 100.0

    def _get_prediction_accuracy(self):
        if len(self.prediction_buffer) < 5:
            return 0.5
        correct = sum(1 for p in self.prediction_buffer if p.get("correct", False))
        return correct / len(self.prediction_buffer)

    def _get_recovery_rate(self):
        if len(self.health_history) < 10:
            return 0.5
        recoveries = 0
        history = list(self.health_history)[-10:]
        for i in range(1, len(history)):
            if history[i-1].get("state") in ["warning", "critical"] and history[i].get("state") == "healthy":
                recoveries += 1
        return recoveries / 5.0

    def _get_stability_score(self):
        if len(self.health_history) < 5:
            return 0.7
        cpus = [h.get("cpu", 50) for h in list(self.health_history)[-5:]]
        return 1.0 - min(1.0, np.std(cpus) / 30.0)

    def _get_resource_efficiency(self):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        return 1.0 - ((cpu + mem) / 200.0)

    def _get_anomaly_count(self):
        return min(1.0, len([h for h in self.health_history if h.get("state") == "critical"]) / 10.0)

    async def check(self):
        stats = {
            "cpu": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage(os.getenv('SystemDrive', 'C:\\')).percent
        }
        
        if self.dl_active:
            features = self._extract_features(stats)
            predictions = self.health_nn.predict_health(features)
            
            health_record = {
                "cpu": stats["cpu"],
                "memory": stats["memory"],
                "disk": stats["disk"],
                "prediction": predictions[0][0],
                "confidence": predictions[0][1],
                "timestamp": time.time()
            }
            
            if predictions[0][0] in ["warning", "critical"]:
                health_record["state"] = predictions[0][0]
            else:
                health_record["state"] = "healthy"
                
            self.health_history.append(health_record)
            self.prediction_buffer.append({
                "predicted": predictions[0][0],
                "actual": "healthy" if stats["cpu"] < 70 else "warning"
            })
            
            return health_record
        
        return stats

    async def start(self):
        self.active = True
        logger.info("DL-POWERED Health monitoring loop started.")
        
        while self.active:
            stats = await self.check()
            
            if self.dl_active:
                if stats.get("state") in ["warning", "critical"] or stats.get("cpu", 0) > 85 or stats.get("memory", 0) > 90:
                    self.event_bus.publish("security_alert", {
                        "type": "health",
                        "state": stats.get("state", "unknown"),
                        "cpu": stats.get("cpu"),
                        "memory": stats.get("memory"),
                        "prediction": stats.get("prediction")
                    })
            else:
                if stats["cpu"] > 85 or stats["memory"] > 90:
                    self.event_bus.publish("security_alert", stats)
                    
            self.event_bus.publish("health_update", stats)
            await asyncio.sleep(5)

    async def stop(self):
        self.active = False
        self._save_model()
        
    def _save_model(self):
        if not hasattr(self, 'health_nn'):
            return
        try:
            data_dir = "data/deep_learning"
            os.makedirs(data_dir, exist_ok=True)
            
            model_data = {
                "weights1": self.health_nn.weights1.tolist(),
                "weights2": self.health_nn.weights2.tolist(),
                "bias1": self.health_nn.bias1.tolist(),
                "bias2": self.health_nn.bias2.tolist()
            }
            
            with open(f"{data_dir}/health_nn.json", "w") as f:
                json.dump(model_data, f)
                
        except Exception as e:
            logger.warning(f"Failed to save health model: {e}")

    def _load_model(self):
        try:
            model_file = "data/deep_learning/health_nn.json"
            if os.path.exists(model_file):
                with open(model_file, "r") as f:
                    model_data = json.load(f)
                    
                self.health_nn.weights1 = np.array(model_data.get("weights1"))
                self.health_nn.weights2 = np.array(model_data.get("weights2"))
                self.health_nn.bias1 = np.array(model_data.get("bias1"))
                self.health_nn.bias2 = np.array(model_data.get("bias2"))
                
                logger.info("DL Health model loaded")
        except Exception as e:
            logger.warning(f"Failed to load health model: {e}")
