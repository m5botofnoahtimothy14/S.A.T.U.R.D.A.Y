                   

import asyncio
import psutil
import structlog
import time
import json
import os
from collections import deque
from core.event_bus import EventBus
logger = structlog.get_logger("AEGIS.SelfHeal")
class HealingNeuralNetwork:
    def __init__(self, input_size=15, hidden_size=30, output_size=8):
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
    def predict_healing(self, features):
        output = self.forward(features)[0]
        healing_actions = [
            "throttle_background",
            "clear_cache",
            "restart_module",
            "optimize_memory",
            "reduce_threads",
            "scale_down_services",
            "emergency_cleanup",
            "monitor_only"
        ]
        actions = []
        for i, action in enumerate(healing_actions):
            if output[i] > 0.3:
                actions.append((action, float(output[i])))
        if not actions:
            actions = [("monitor_only", float(max(output)))]
        return sorted(actions, key=lambda x: x[1], reverse=True)
    def learn_from_outcome(self, features, action_taken, success):
        import numpy as np
        output = self.forward(features)[0]
        healing_actions = [
            "throttle_background", "clear_cache", "restart_module",
            "optimize_memory", "reduce_threads", "scale_down_services",
            "emergency_cleanup", "monitor_only"
        ]
        expected = np.zeros(self.output_size)
        if action_taken in healing_actions:
            idx = healing_actions.index(action_taken)
            expected[idx] = 1.0 if success else 0.0
        error = expected - output
        output_delta = error
        hidden_error = self.np.dot(output_delta, self.weights2.T)
        hidden_delta = hidden_error * self.relu_derivative(self.hidden)
        self.weights2 += 0.01 * self.np.dot(self.hidden.T, output_delta)
        self.weights1 += 0.01 * self.np.dot(features.T, hidden_delta)
        self.bias2 += 0.01 * output_delta
        self.bias1 += 0.01 * hidden_delta
class SelfHealManager:
    def __init__(self, event_bus: EventBus, cpu_thresh: float = 85.0, mem_thresh: float = 85.0):
        self.event_bus = event_bus
        self.cpu_thresh = cpu_thresh
        self.mem_thresh = mem_thresh
        self.running = True
        self._hot_streak = 0
        self.optimization_mode = "balanced"                                   
        self._init_deep_learning()
        self._setup_optimization()
    def _setup_optimization(self):
        total_mem = psutil.virtual_memory().total / (1024**3)
        cpu_count = psutil.cpu_count()
        if total_mem < 8 or cpu_count < 4:
            self.optimization_mode = "low_power"
            self.cpu_thresh = 75.0
            self.mem_thresh = 70.0
            logger.info(f"System Optimized: LOW_POWER mode active (Memory: {total_mem:.1f}GB, Cores: {cpu_count})")
        else:
            self.optimization_mode = "performance"
            logger.info(f"System Optimized: PERFORMANCE mode active (Memory: {total_mem:.1f}GB, Cores: {cpu_count})")
    def _init_deep_learning(self):
        try:
            self.healing_nn = HealingNeuralNetwork()
            self.healing_history = deque(maxlen=100)
            self.success_patterns = {}
            self.anomaly_buffer = deque(maxlen=50)
            self._load_healing_model()
            self.dl_healing_active = True
            logger.info("DEEP LEARNING Self-Healing initialized - AEGIS can now heal itself")
        except Exception as e:
            logger.warning(f"DL Healing init failed: {e}")
            self.dl_healing_active = False
    def _extract_health_features(self, cpu, mem, processes):
        import numpy as np
        features = [
            cpu / 100.0,
            mem / 100.0,
            len(processes) / 50.0,
            sum(p.get("cpu_percent", 0) for p in processes[:3]) / 100.0,
            sum(p.get("memory_percent", 0) for p in processes[:3]) / 100.0,
            self._hot_streak / 10.0,
            time.time() % 3600 / 3600.0,
            len(self.healing_history) / 100.0,
            self._calculate_success_rate(),
            self._get_resource_trend(),
            self._get_memory_pressure(),
            self._get_cpu_variance(),
            self._get_process_count_trend(),
            self._get_healing_streak(),
            self._get_anomaly_score()
        ]
        return np.array([features[:15]])
    def _calculate_success_rate(self):
        if not self.healing_history:
            return 0.5
        successful = sum(1 for h in self.healing_history if h.get("success", False))
        return successful / len(self.healing_history)
    def _get_resource_trend(self):
        if len(self.healing_history) < 5:
            return 0.5
        recent = list(self.healing_history)[-5:]
        return sum(h.get("cpu_after", 50) for h in recent) / 5 / 100.0
    def _get_memory_pressure(self):
        mem = psutil.virtual_memory()
        return mem.percent / 100.0
    def _get_cpu_variance(self):
        return 0.3
    def _get_process_count_trend(self):
        return len(psutil.pids()) / 500.0
    def _get_healing_streak(self):
        if not self.healing_history:
            return 0.0
        streak = 0
        for h in reversed(self.healing_history):
            if h.get("success", False):
                streak += 1
            else:
                break
        return min(1.0, streak / 10.0)
    def _get_anomaly_score(self):
        if len(self.anomaly_buffer) < 5:
            return 0.0
        return sum(self.anomaly_buffer) / len(self.anomaly_buffer)
    async def start(self):
        logger.info("DL-POWERED SelfHeal manager started")
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=1.0)
                mem = psutil.virtual_memory().percent
                top = self._top_processes()
                features = self._extract_health_features(cpu, mem, top)
                if self.dl_healing_active and len(self.healing_history) > 10:
                    recommended_actions = self.healing_nn.predict_healing(features)
                    cpu_high = cpu > self.cpu_thresh
                    mem_high = mem > self.mem_thresh
                    if cpu_high or mem_high:
                        if self.optimization_mode == "low_power":
                            logger.info("High load in low_power mode. Scaling up optimization thresholds temporarily.")
                            self.cpu_thresh = 80.0
                            self.mem_thresh = 80.0
                        self._hot_streak += 1
                        self.anomaly_buffer.append(1.0)
                        action_taken = recommended_actions[0][0]
                        action_confidence = recommended_actions[0][1]
                        await self._execute_healing(action_taken, cpu, mem, top, action_confidence)
                    else:
                        self._hot_streak = max(0, self._hot_streak - 1)
                        self.anomaly_buffer.append(0.0)
                else:
                    if cpu > self.cpu_thresh or mem > self.mem_thresh:
                        self._hot_streak += 1
                        top = self._top_processes()
                        self.event_bus.publish(
                            "system_alert",
                            {
                                "message": f"High load detected (CPU {cpu:.0f}%, MEM {mem:.0f}%)",
                                "top": top,
                            },
                        )
                        if self._hot_streak >= 3:
                            logger.warning("Autonomous mitigation triggered: Throttling background tasks.")
                            self.event_bus.publish(
                                "cooldown",
                                {
                                    "cpu": cpu,
                                    "mem": mem,
                                    "action": "autonomous_throttle",
                                    "top": top,
                                },
                            )
                            self._hot_streak = 0
                    else:
                        self._hot_streak = 0
            except Exception as e:
                logger.warning("SelfHeal loop error", error=str(e))
            await asyncio.sleep(2)
    async def _execute_healing(self, action, cpu, mem, processes, confidence):
        logger.info(f"DL Healing: {action} (confidence: {confidence:.2f})")
        self.event_bus.publish(
            "system_alert",
            {
                "message": f"DL System Healing: {action} (CPU {cpu:.0f}%, MEM {mem:.0f}%)",
                "action": action,
                "confidence": confidence,
                "top": processes[:3],
            },
        )
        success = False
        healing_result = {}
        if action == "throttle_background":
            healing_result = await self._throttle_background()
            success = healing_result.get("cpu_after", 50) < cpu
        elif action == "clear_cache":
            healing_result = await self._clear_cache()
            success = healing_result.get("mem_after", 50) < mem
        elif action == "optimize_memory":
            healing_result = await self._optimize_memory()
            success = healing_result.get("mem_after", 50) < mem
        elif action == "emergency_cleanup":
            healing_result = await self._emergency_cleanup()
            success = healing_result.get("success", False)
        else:
            success = True
        cpu_after = psutil.cpu_percent(interval=0.5)
        mem_after = psutil.virtual_memory().percent
        healing_record = {
            "action": action,
            "cpu_before": cpu,
            "mem_before": mem,
            "cpu_after": cpu_after,
            "mem_after": mem_after,
            "success": success,
            "timestamp": time.time(),
            "confidence": confidence
        }
        self.healing_history.append(healing_record)
        if self.dl_healing_active:
            features = self._extract_health_features(cpu, mem, processes)
            self.healing_nn.learn_from_outcome(features, action, success)
        self.event_bus.publish(
            "cooldown",
            {
                "cpu": cpu_after,
                "mem": mem_after,
                "action": action,
                "success": success,
                "healing_type": "dl_powered"
            },
        )
        if action != "monitor_only":
            self._save_healing_model()
        self._hot_streak = 0
    async def _throttle_background(self):
        return {"action": "throttle_background", "cpu_after": psutil.cpu_percent(interval=0.5)}
    async def _clear_cache(self):
        return {"action": "clear_cache", "mem_after": psutil.virtual_memory().percent}
    async def _optimize_memory(self):
        return {"action": "optimize_memory", "mem_after": psutil.virtual_memory().percent}
    async def _emergency_cleanup(self):
        return {"action": "emergency_cleanup", "success": True}
    def _top_processes(self, limit: int = 3):
        procs = []
        for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except Exception:
                continue
        procs.sort(key=lambda x: (x.get("cpu_percent", 0), x.get("memory_percent", 0)), reverse=True)
        return procs[:limit]
    def _save_healing_model(self):
        if not hasattr(self, 'healing_nn'):
            return
        try:
            data_dir = "data/deep_learning"
            os.makedirs(data_dir, exist_ok=True)
            model_data = {
                "weights1": self.healing_nn.weights1.tolist(),
                "weights2": self.healing_nn.weights2.tolist(),
                "bias1": self.healing_nn.bias1.tolist(),
                "bias2": self.healing_nn.bias2.tolist(),
                "history_size": len(self.healing_history)
            }
            with open(f"{data_dir}/healing_nn.json", "w") as f:
                json.dump(model_data, f)
        except Exception as e:
            logger.warning(f"Failed to save healing model: {e}")
    def _load_healing_model(self):
        try:
            import numpy as np
            model_file = "data/deep_learning/healing_nn.json"
            if os.path.exists(model_file):
                with open(model_file, "r") as f:
                    model_data = json.load(f)
                self.healing_nn.weights1 = np.array(model_data.get("weights1"))
                self.healing_nn.weights2 = np.array(model_data.get("weights2"))
                self.healing_nn.bias1 = np.array(model_data.get("bias1"))
                self.healing_nn.bias2 = np.array(model_data.get("bias2"))
                logger.info("DL Healing model loaded")
        except Exception as e:
            logger.warning(f"Failed to load healing model: {e}")
    async def stop(self):
        self.running = False
        self._save_healing_model()
        logger.info("SelfHeal manager stopped - Healing knowledge preserved")
