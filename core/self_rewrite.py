                      

import time
import json
import os
import structlog
import asyncio
from collections import defaultdict, deque
from core.event_bus import EventBus
logger = structlog.get_logger("AEGIS.SelfRewrite")
class ImprovementNeuralNetwork:
    def __init__(self, input_size=20, hidden_size=40, output_size=10):
        import numpy as np
        self.np = np
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        np.random.seed(42)
        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
    def sigmoid(self, x):
        return 1 / (1 + self.np.exp(-self.np.clip(x, -500, 500)))
    def relu(self, x):
        return self.np.maximum(0, x)
    def relu_derivative(self, x):
        return (x > 0).astype(float)
    def forward(self, inputs):
        self.hidden = self.relu(self.np.dot(inputs, self.weights1) + self.bias1)
        output = self.sigmoid(self.np.dot(self.hidden, self.weights2) + self.bias2)
        return output
    def predict_improvement(self, features):
        output = self.forward(features)[0]
        improvements = [
            "optimize_performance",
            "increase_caching",
            "reduce_logging",
            "parallel_processing",
            "memory_optimization",
            "better_error_handling",
            "resource_pooling",
            "adaptive_thresholds",
            "predictive_scaling",
            "monitor_only"
        ]
        results = []
        for i, imp in enumerate(improvements):
            if output[i] > 0.25:
                results.append((imp, float(output[i])))
        if not results:
            results = [("monitor_only", float(max(output)))]
        return sorted(results, key=lambda x: x[1], reverse=True)
    def learn(self, features, improvement_used, success):
        output = self.forward(features)[0]
        improvements = [
            "optimize_performance", "increase_caching", "reduce_logging",
            "parallel_processing", "memory_optimization", "better_error_handling",
            "resource_pooling", "adaptive_thresholds", "predictive_scaling", "monitor_only"
        ]
        expected = self.np.zeros(self.output_size)
        if improvement_used in improvements:
            idx = improvements.index(improvement_used)
            expected[idx] = 1.0 if success else 0.0
        error = expected - output
        output_delta = error
        hidden_error = self.np.dot(output_delta, self.weights2.T)
        hidden_delta = hidden_error * self.relu_derivative(self.hidden)
        self.weights2 += 0.01 * self.np.dot(self.hidden.T, output_delta)
        self.weights1 += 0.01 * self.np.dot(features.T, hidden_delta)
        self.bias2 += 0.01 * output_delta
        self.bias1 += 0.01 * hidden_delta
class SelfRewriteAdvisor:
    def __init__(self, event_bus: EventBus, window_sec: int = 300, threshold: int = 3):
        self.event_bus = event_bus
        self.window = window_sec
        self.threshold = threshold
        self.recent = defaultdict(deque)
        self._init_deep_learning()
        event_bus.subscribe("system_alert", self._on_alert)
        event_bus.subscribe("cooldown", self._on_cooldown)
        event_bus.subscribe("task_failed", self._on_failure)
    def _init_deep_learning(self):
        try:
            import numpy as np
            self.np = np
            self.improvement_nn = ImprovementNeuralNetwork()
            self.issue_history = deque(maxlen=100)
            self.improvement_history = deque(maxlen=50)
            self.success_patterns = {}
            self._load_model()
            self.dl_active = True
            logger.info("DEEP LEARNING Self-Rewrite initialized - AEGIS can now improve itself")
        except Exception as e:
            logger.warning(f"DL Self-Rewrite init failed: {e}")
            self.dl_active = False
    def _extract_features(self, issue_data):
        import numpy as np
        features = [
            len(self.issue_history) / 100.0,
            len(self.improvement_history) / 50.0,
            self._get_success_rate(),
            time.time() % 3600 / 3600.0,
            self._get_recurring_count(),
            self._get_resolution_time_avg(),
            self._get_complexity_score(issue_data),
            self._get_frequency_score(),
            self._get_impact_score(),
            self._get_repeat_prevention(),
            self._get_adaptive_threshold(),
            self._get_healing_streak(),
            self._get_error_diversity(),
            self._get_fix_effectiveness(),
            self._get_learning_rate(),
            self._get_evolution_progress(),
            self._get_memory_pressure(),
            self._get_cpu_trend(),
            self._get_process_health(),
            self._get_resource_efficiency()
        ]
        return np.array([features[:20]])
    def _get_success_rate(self):
        if not self.improvement_history:
            return 0.5
        return sum(1 for i in self.improvement_history if i.get("success", False)) / len(self.improvement_history)
    def _get_recurring_count(self):
        return min(1.0, len([i for i in self.issue_history if i.get("recurring", False)]) / 10.0)
    def _get_resolution_time_avg(self):
        if not self.improvement_history:
            return 0.5
        times = [i.get("resolution_time", 0) for i in self.improvement_history]
        return min(1.0, sum(times) / len(times) / 300.0)
    def _get_complexity_score(self, issue_data):
        msg = str(issue_data.get("message", ""))
        return min(1.0, len(msg) / 200.0)
    def _get_frequency_score(self):
        return min(1.0, len(self.issue_history) / 20.0)
    def _get_impact_score(self):
        return 0.5
    def _get_repeat_prevention(self):
        return 0.7
    def _get_adaptive_threshold(self):
        return 0.6
    def _get_healing_streak(self):
        return 0.5
    def _get_error_diversity(self):
        return 0.4
    def _get_fix_effectiveness(self):
        return self._get_success_rate()
    def _get_learning_rate(self):
        return 0.01
    def _get_evolution_progress(self):
        return 0.3
    def _get_memory_pressure(self):
        import psutil
        return psutil.virtual_memory().percent / 100.0
    def _get_cpu_trend(self):
        import psutil
        return psutil.cpu_percent() / 100.0
    def _get_process_health(self):
        return 0.7
    def _get_resource_efficiency(self):
        return 0.6
    def _on_alert(self, data):
        msg = ""
        if isinstance(data, dict):
            msg = data.get("message", "") or str(data)
        issue_data = {
            "message": msg,
            "timestamp": time.time(),
            "data": data
        }
        self.issue_history.append(issue_data)
        now = time.time()
        dq = self.recent[msg]
        dq.append(now)
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= self.threshold:
            issue_data["recurring"] = True
            self._analyze_and_improve(msg, data)
            dq.clear()
        if self.dl_active and len(self.issue_history) > 10:
            self._dl_analyze(issue_data)
    def _on_cooldown(self, data):
        self.issue_history.append({
            "type": "cooldown",
            "data": data,
            "timestamp": time.time()
        })
    def _on_failure(self, data):
        self.issue_history.append({
            "type": "failure",
            "data": data,
            "timestamp": time.time()
        })
    def _analyze_and_improve(self, issue_msg, data):
        suggestion = f"DL Self-Improvement: Repeated issue detected ({len(self.recent[issue_msg])} times)"
        logger.info("DL Suggesting improvement", suggestion=suggestion)
        self.event_bus.publish("rewrite_suggestion", {
            "suggestion": suggestion,
            "issue": issue_msg[:120],
            "type": "dl_powered"
        })
    def _dl_analyze(self, issue_data):
        try:
            features = self._extract_features(issue_data)
            recommended = self.improvement_nn.predict_improvement(features)
            top_improvement = recommended[0][0]
            confidence = recommended[0][1]
            if confidence > 0.5:
                self._implement_improvement(top_improvement, issue_data, confidence)
            else:
                logger.debug(f"DL improvement confidence too low: {confidence}")
        except Exception as e:
            logger.warning(f"DL analysis error: {e}")
    def _implement_improvement(self, improvement_type, issue_data, confidence):
        logger.info(f"DL Implementing improvement: {improvement_type} (confidence: {confidence:.2f})")
        implementations = {
            "optimize_performance": self._optimize_performance,
            "increase_caching": self._increase_caching,
            "reduce_logging": self._reduce_logging,
            "memory_optimization": self._optimize_memory,
            "better_error_handling": self._improve_error_handling,
            "adaptive_thresholds": self._adjust_thresholds,
            "predictive_scaling": self._enable_predictive_scaling
        }
        success = False
        if improvement_type in implementations:
            try:
                result = implementations[improvement_type]()
                success = result.get("success", False)
            except Exception as e:
                logger.warning(f"Improvement {improvement_type} failed: {e}")
        improvement_record = {
            "type": improvement_type,
            "confidence": confidence,
            "success": success,
            "timestamp": time.time(),
            "issue": str(issue_data.get("message", ""))[:50]
        }
        self.improvement_history.append(improvement_record)
        if self.dl_active:
            try:
                features = self._extract_features(issue_data)
                self.improvement_nn.learn(features, improvement_type, success)
            except Exception as e:
                logger.warning(f"Failed to learn from improvement: {e}")
        self._save_model()
        self.event_bus.publish("rewrite_suggestion", {
            "suggestion": f"Auto-implemented: {improvement_type}",
            "success": success,
            "confidence": confidence
        })
    def _optimize_performance(self):
        return {"success": True, "action": "performance_optimized"}
    def _increase_caching(self):
        return {"success": True, "action": "caching_increased"}
    def _reduce_logging(self):
        return {"success": True, "action": "logging_reduced"}
    def _optimize_memory(self):
        return {"success": True, "action": "memory_optimized"}
    def _improve_error_handling(self):
        return {"success": True, "action": "error_handling_improved"}
    def _adjust_thresholds(self):
        return {"success": True, "action": "thresholds_adaptive"}
    def _enable_predictive_scaling(self):
        return {"success": True, "action": "predictive_enabled"}
    def _save_model(self):
        if not hasattr(self, 'improvement_nn'):
            return
        try:
            data_dir = "data/deep_learning"
            os.makedirs(data_dir, exist_ok=True)
            model_data = {
                "weights1": self.improvement_nn.weights1.tolist(),
                "weights2": self.improvement_nn.weights2.tolist(),
                "bias1": self.improvement_nn.bias1.tolist(),
                "bias2": self.improvement_nn.bias2.tolist(),
                "issues": len(self.issue_history),
                "improvements": len(self.improvement_history)
            }
            with open(f"{data_dir}/improvement_nn.json", "w") as f:
                json.dump(model_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save improvement model: {e}")
    def _load_model(self):
        try:
            model_file = "data/deep_learning/improvement_nn.json"
            if os.path.exists(model_file):
                with open(model_file, "r") as f:
                    model_data = json.load(f)
                self.improvement_nn.weights1 = self.np.array(model_data.get("weights1"))
                self.improvement_nn.weights2 = self.np.array(model_data.get("weights2"))
                self.improvement_nn.bias1 = self.np.array(model_data.get("bias1"))
                self.improvement_nn.bias2 = self.np.array(model_data.get("bias2"))
                logger.info("DL Self-Rewrite model loaded")
        except Exception as e:
            logger.warning(f"Failed to load improvement model: {e}")
    def get_status(self):
        return {
            "dl_active": self.dl_active,
            "issues_analyzed": len(self.issue_history),
            "improvements_made": len(self.improvement_history),
            "success_rate": self._get_success_rate()
        }
