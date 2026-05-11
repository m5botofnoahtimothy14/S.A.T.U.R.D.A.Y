                         
import os
import json
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
import structlog

import numpy as np

logger = structlog.get_logger("SATURDAY.DL.Policy")

class PolicyNeuralNetwork:
    
    def __init__(self, input_size: int = 15, hidden_size: int = 30, output_size: int = 4):
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
    
    def relu_derivative(self, x):
        return (x > 0).astype(float)
    
    def forward(self, inputs: np.ndarray) -> np.ndarray:
        self.hidden = self.relu(np.dot(inputs, self.weights1) + self.bias1)
        output = self.sigmoid(np.dot(self.hidden, self.weights2) + self.bias2)
        return output
    
    def predict(self, features: np.ndarray) -> Tuple[List[str], List[float]]:
        
        output = self.forward(features)[0]
        
        actions = ["allow", "deny", "review", "escalate"]
        decisions = []
        confidences = []
        
        for i, action in enumerate(actions):
            if output[i] > 0.3:
                decisions.append(action)
                confidences.append(float(output[i]))
                
        if not decisions:
            decisions = ["allow"]
            confidences = [float(max(output))]
            
        return decisions, confidences

class NeuralPolicyEngine:
    
    def __init__(self, event_bus, deep_learning_core=None):
        self.event_bus = event_bus
        self.dl_core = deep_learning_core
        
        self.policy_nn = PolicyNeuralNetwork()
        
        self.trusted_commands = [
            "status", "help", "music", "play", "stop", "pause",
            "weather", "time", "date", "search", "open", "close"
        ]
        
        self.sensitive_commands = [
            "delete", "format", "shutdown", "restart", "reset",
            "admin", "root", "sudo", "install", "uninstall"
        ]
        
        self.command_history = deque(maxlen=100)
        self.denial_history = deque(maxlen=50)
        self.approval_history = deque(maxlen=200)
        self._last_security_escalation_log = 0.0
        
        self.data_dir = "data/deep_learning"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self._load_model()
        self._subscribe_to_events()
        
        logger.info("NeuralPolicyEngine initialized - AI-driven governance active")
        
    def _subscribe_to_events(self):
        
        if self.event_bus:
            self.event_bus.subscribe("voice_command", self.validate_command)
            self.event_bus.subscribe("task_request", self.validate_task)
            self.event_bus.subscribe("security_alert", self.on_security_alert)
            
    def _extract_command_features(self, command: str, context: Dict = None) -> np.ndarray:
        
        command_lower = command.lower()
        
        features = []
        
        features.append(1.0 if any(cmd in command_lower for cmd in self.sensitive_commands) else 0.0)
        
        features.append(1.0 if any(cmd in command_lower for cmd in self.trusted_commands) else 0.0)
        
        features.append(len(command) / 100.0)
        
        words = command.split()
        features.append(len(words) / 20.0)
        
        features.append(sum(1 for c in command if c.isupper()) / max(1, len(command)))
        
        if context:
            features.append(context.get("user_trust", 0.5))
            features.append(context.get("time_weight", 0.5))
            features.append(context.get("reliability", 0.7))
            features.append(context.get("anomaly_score", 0.0))
        else:
            features.extend([0.5, 0.5, 0.7, 0.0])
            
        cmd_count = len(self.command_history)
        features.append(min(1.0, cmd_count / 100.0))
        
        recent_denials = sum(1 for h in list(self.denial_history)[-10:] if h.get("denied", False))
        features.append(recent_denials / 10.0)
        
        success_rate = 0.8
        if len(self.approval_history) > 0:
            success_rate = sum(1 for h in self.approval_history if h.get("success", False)) / len(self.approval_history)
        features.append(success_rate)
        
        features.append(time.time() % 86400 / 86400.0)
        
        while len(features) < self.policy_nn.input_size:
            features.append(0.5)
            
        return np.array([features[:self.policy_nn.input_size]])
        
    async def validate_command(self, data: str) -> bool:
        
        command = str(data)
        
        self.command_history.append({
            "command": command,
            "timestamp": time.time()
        })
        
        context = self._get_context()
        
        features = self._extract_command_features(command, context)
        
        decisions, confidences = self.policy_nn.predict(features)
        
        decision = decisions[0]
        confidence = confidences[0] if confidences else 0.5
        
        if self.dl_core:
            dl_result = self.dl_core.think(command, context)
            if dl_result["confidence"] > confidence:
                decision = dl_result["decision"]
                confidence = dl_result["confidence"]
        
        if decision == "deny":
            self.denial_history.append({
                "command": command,
                "denied": True,
                "timestamp": time.time(),
                "reason": "Neural policy enforcement"
            })
            
            if self.event_bus:
                self.event_bus.publish("voice_response", "Command denied: Policy violation detected by AI analysis.")
                self.event_bus.publish("policy_denial", {"command": command, "confidence": confidence})
                
            logger.info("Command denied by neural policy", command=command, confidence=confidence)
            return False
            
        elif decision == "review":
            self.denial_history.append({
                "command": command,
                "denied": True,
                "review_required": True,
                "timestamp": time.time()
            })
            
            if self.event_bus:
                self.event_bus.publish("voice_response", "This command requires additional review. Please confirm.")
                self.event_bus.publish("policy_review", {"command": command})
                
            logger.info("Command flagged for review", command=command)
            return False
            
        elif decision == "escalate":
            if self.event_bus:
                self.event_bus.publish("security_alert", {
                    "type": "policy_escalation",
                    "command": command,
                    "severity": confidence
                })
                
            logger.warning("Command escalated to security", command=command)
            
        self.approval_history.append({
            "command": command,
            "success": True,
            "timestamp": time.time()
        })
        
        logger.info("Command approved by neural policy", command=command, confidence=confidence)
        return True
        
    async def validate_task(self, data: Dict) -> bool:
        
        task_type = data.get("type", "")
        task_data = data.get("data", {})
        
        command = f"task {task_type}"
        return await self.validate_command(command)
        
    def _get_context(self) -> Dict[str, float]:
        
        now = time.time()
        
        recent_commands = list(self.command_history)[-5:]
        time_variance = 0.5
        if len(recent_commands) > 1:
            times = [c.get("timestamp", 0) for c in recent_commands]
            if len(times) > 1:
                time_variance = np.std(times) / 60.0
                
        success_rate = 0.8
        if len(self.approval_history) > 0:
            success_rate = sum(1 for h in self.approval_history if h.get("success", False)) / len(self.approval_history)
            
        return {
            "user_trust": 0.8,
            "time_weight": 1.0 - min(1.0, time_variance),
            "reliability": success_rate,
            "anomaly_score": min(1.0, len(self.denial_history) / 50.0)
        }
        
    def on_security_alert(self, data: Dict):
        
        if not isinstance(data, dict):
            return

        features = self._extract_command_features("security_alert", {"anomaly_score": data.get("severity", 0.5)})
        
        output = self.policy_nn.forward(features)[0]
        
        now = time.time()
        if output[3] > 0.5 and (now - self._last_security_escalation_log) >= 30:
            self._last_security_escalation_log = now
            logger.warning("Security escalation detected by neural policy")
            
    def learn_from_outcome(self, command: str, approved: bool, actually_executed: bool):
        
        features = self._extract_command_features(command)
        
        expected = np.array([[0.0, 0.0, 0.0, 0.0]])
        
        if approved and actually_executed:
            expected[0][0] = 1.0
        elif approved and not actually_executed:
            expected[0][2] = 1.0
        elif not approved:
            expected[0][1] = 1.0
            
        self.policy_nn.forward(features)
        
        logger.debug("Policy learned from outcome", command=command, approved=approved)
        
    def _save_model(self):
        
        model_data = {
            "weights1": self.policy_nn.weights1.tolist(),
            "weights2": self.policy_nn.weights2.tolist(),
            "bias1": self.policy_nn.bias1.tolist(),
            "bias2": self.policy_nn.bias2.tolist()
        }
        
        with open(f"{self.data_dir}/policy_nn.json", "w") as f:
            json.dump(model_data, f)
            
    def _load_model(self):
        
        model_file = f"{self.data_dir}/policy_nn.json"
        
        if os.path.exists(model_file):
            try:
                with open(model_file, "r") as f:
                    model_data = json.load(f)
                    
                self.policy_nn.weights1 = np.array(model_data.get("weights1"))
                self.policy_nn.weights2 = np.array(model_data.get("weights2"))
                self.policy_nn.bias1 = np.array(model_data.get("bias1"))
                self.policy_nn.bias2 = np.array(model_data.get("bias2"))
                
                logger.info("Neural policy model loaded")
                
            except Exception as e:
                logger.warning(f"Failed to load policy model: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        
        return {
            "neural_policy_active": True,
            "commands_analyzed": len(self.command_history),
            "denials": len(self.denial_history),
            "approvals": len(self.approval_history),
            "model_loaded": os.path.exists(f"{self.data_dir}/policy_nn.json")
        }
