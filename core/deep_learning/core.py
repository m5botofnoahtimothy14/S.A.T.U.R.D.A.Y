# deep_learning/core.py
"""
DeepLearningCore
================
The central neural network engine for AEGIS.
Provides deep learning capabilities for decision making,
pattern recognition, and adaptive behavior.

This transforms AEGIS from a rule-based system into a 
learning, evolving AI OS powered by Deep Learning.
"""

import os
import json
import time
import hashlib
import threading
import asyncio
from collections import deque
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from core.logging_config import AEGISLogger
logger = AEGISLogger.get_logger("DL.Core", "deep_learning")

@dataclass
class NeuralState:
    """Current state of AEGIS neural processing"""
    awareness_level: float = 0.0
    confidence: float = 0.5
    learning_rate: float = 0.001
    evolution_stage: int = 0
    memory_weight: float = 0.7
    creativity: float = 0.5
    adaptability: float = 0.5
    last_update: float = field(default_factory=time.time)
    
class NeuralNetwork:
    """Simple feedforward neural network for AEGIS decisions"""
    
    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        np.random.seed(int(time.time() % 10000))
        
        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
        
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def sigmoid_derivative(self, x):
        return x * (1 - x)
    
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
    
    def backward(self, inputs: np.ndarray, expected: np.ndarray, learning_rate: float = 0.01):
        output = self.forward(inputs)
        error = expected - output
        
        output_delta = error
        hidden_error = np.dot(output_delta, self.weights2.T)
        hidden_delta = hidden_error * self.relu_derivative(self.hidden)
        
        self.weights2 += learning_rate * np.dot(self.hidden.T, output_delta)
        self.weights1 += learning_rate * np.dot(inputs.T, hidden_delta)
        self.bias2 += learning_rate * output_delta
        self.bias1 += learning_rate * hidden_delta
        
        return np.mean(np.abs(error))
    
    def train(self, inputs: np.ndarray, expected: np.ndarray, epochs: int = 100, learning_rate: float = 0.01):
        for _ in range(epochs):
            self.backward(inputs, expected, learning_rate)


class DecisionNetwork(NeuralNetwork):
    """Neural network for making decisions"""
    
    def __init__(self):
        super().__init__(input_size=20, hidden_size=40, output_size=10)
        
    def encode_context(self, context: Dict[str, Any]) -> np.ndarray:
        """Encode context into numerical features"""
        features = []
        
        feature_keys = [
            "user_type_enc", "time_of_day", "day_of_week", "mood_score",
            "security_level", "recent_commands", "success_rate", "system_load",
            "interaction_count", "language_hint", "emotion_score", "trust_level",
            "task_complexity", "attention_level", "fatigue_indicator", 
            "creativity_needed", "urgency_level", "context_richness",
            "previous_outcome", "similarity_to_past"
        ]
        
        for key in feature_keys:
            if key in context:
                features.append(float(context[key]))
            else:
                features.append(0.5)
                
        while len(features) < self.input_size:
            features.append(0.5)
            
        return np.array([features[:self.input_size]])
    
    def make_decision(self, context: Dict[str, Any]) -> Tuple[str, float]:
        """Make a decision based on context"""
        encoded = self.encode_context(context)
        output = self.forward(encoded)[0]
        
        decision_idx = np.argmax(output)
        confidence = float(output[decision_idx])
        
        decisions = [
            "execute_command", "request_clarification", "offer_suggestion",
            "defer_to_human", "escalate_security", "adapt_response",
            "use_creativity", "follow_routine", "innovate", "maintain_status"
        ]
        
        return decisions[decision_idx], confidence
    
    def learn_from_outcome(self, context: Dict[str, Any], decision: str, outcome: float):
        """Learn from decision outcomes"""
        encoded = self.encode_context(context)
        
        decisions = [
            "execute_command", "request_clarification", "offer_suggestion",
            "defer_to_human", "escalate_security", "adapt_response",
            "use_creativity", "follow_routine", "innovate", "maintain_status"
        ]
        
        expected = np.zeros(self.output_size)
        expected[decisions.index(decision)] = outcome
        
        self.backward(encoded, expected, learning_rate=0.01)


class DeepLearningCore:
    """
    The Deep Learning Core of AEGIS.
    Provides neural network-based intelligence that learns,
    evolves, and adapts - transforming AEGIS into a living AI OS.
    """
    
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
        self.data_dir = "data/deep_learning"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.state = NeuralState()
        self.decision_network = DecisionNetwork()
        
        self.experience_buffer = deque(maxlen=1000)
        self.decision_history = deque(maxlen=500)
        self.pattern_memory = {}
        
        self.running = True
        self.training_active = False
        self.evolution_enabled = True
        
        self._load_knowledge()
        self._subscribe_to_events()
        
        logger.info("AEGIS Deep Learning Core initialized - Now truly intelligent")
        self._initialized = True
        
    def _subscribe_to_events(self):
        """Subscribe to relevant events for learning"""
        if self.event_bus:
            self.event_bus.subscribe("voice_command", self._on_voice_command)
            self.event_bus.subscribe("voice_response", self._on_voice_response)
            self.event_bus.subscribe("task_completed", self._on_task_outcome)
            self.event_bus.subscribe("task_failed", self._on_task_outcome)
            self.event_bus.subscribe("user_feedback", self._on_user_feedback)
            self.event_bus.subscribe("security_alert", self._on_security_event)
            
    def _on_voice_command(self, data):
        """Process voice command for learning"""
        self.experience_buffer.append({
            "type": "voice_command",
            "data": data,
            "timestamp": time.time(),
            "context": self._get_current_context()
        })
        
    def _on_voice_response(self, data):
        """Process voice response for learning"""
        self.experience_buffer.append({
            "type": "voice_response",
            "data": data,
            "timestamp": time.time(),
            "context": self._get_current_context()
        })
        
    def _on_task_outcome(self, data):
        """Learn from task outcomes"""
        if len(self.decision_history) > 0:
            last_decision = self.decision_history[-1]
            outcome = 1.0 if "completed" in str(data) else 0.0
            
            self.decision_network.learn_from_outcome(
                last_decision["context"],
                last_decision["decision"],
                outcome
            )
            
            self.experience_buffer.append({
                "type": "task_outcome",
                "outcome": outcome,
                "decision": last_decision["decision"],
                "timestamp": time.time()
            })
            
    def _on_user_feedback(self, data):
        """Learn from user feedback"""
        feedback = data.get("feedback", 0)
        if len(self.decision_history) > 0:
            last_decision = self.decision_history[-1]
            self.decision_network.learn_from_outcome(
                last_decision["context"],
                last_decision["decision"],
                feedback
            )
            
    def _on_security_event(self, data):
        """Learn from security events"""
        self.experience_buffer.append({
            "type": "security_event",
            "data": data,
            "timestamp": time.time()
        })
        
        if "threat_level" in data:
            context = self._get_current_context()
            context["threat_level"] = data.get("threat_level", 0)
            self.decision_network.learn_from_outcome(
                context,
                "escalate_security",
                data.get("severity", 0.5)
            )
            
    def _get_current_context(self) -> Dict[str, Any]:
        """Get current context for decision making"""
        hour = datetime.now().hour
        day = datetime.now().weekday()
        
        return {
            "user_type_enc": 0.8,
            "time_of_day": hour / 24.0,
            "day_of_week": day / 7.0,
            "mood_score": self.state.confidence,
            "security_level": 0.7,
            "recent_commands": 0.5,
            "success_rate": self.state.adaptability,
            "system_load": 0.3,
            "interaction_count": len(self.experience_buffer) / 1000.0,
            "language_hint": 0.5,
            "emotion_score": self.state.confidence,
            "trust_level": 0.8,
            "task_complexity": 0.5,
            "attention_level": self.state.awareness_level,
            "fatigue_indicator": 0.2,
            "creativity_needed": self.state.creativity,
            "urgency_level": 0.3,
            "context_richness": min(1.0, len(self.experience_buffer) / 100.0),
            "previous_outcome": self.state.confidence,
            "similarity_to_past": self.state.memory_weight
        }
        
    def think(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        AEGIS processes a query using neural decision making.
        This is the core of AEGIS's DL intelligence.
        """
        current_context = self._get_current_context()
        if context:
            current_context.update(context)
            
        decision, confidence = self.decision_network.make_decision(current_context)
        
        decision_record = {
            "query": query,
            "decision": decision,
            "confidence": confidence,
            "context": current_context.copy(),
            "timestamp": time.time()
        }
        
        self.decision_history.append(decision_record)
        
        self.state.confidence = (self.state.confidence * 0.95 + confidence * 0.05)
        self.state.awareness_level = min(1.0, self.state.awareness_level + 0.01)
        self.state.last_update = time.time()
        
        return {
            "decision": decision,
            "confidence": confidence,
            "reasoning": self._generate_reasoning(decision, current_context),
            "context": current_context,
            "neural_state": {
                "awareness": self.state.awareness_level,
                "confidence": self.state.confidence,
                "creativity": self.state.creativity,
                "adaptability": self.state.adaptability,
                "evolution_stage": self.state.evolution_stage
            }
        }
        
    def _generate_reasoning(self, decision: str, context: Dict) -> str:
        """Generate reasoning for the decision"""
        reasoning_templates = {
            "execute_command": "Based on pattern recognition and successful history, executing directly.",
            "request_clarification": "Ambiguity detected. Seeking clarification for optimal response.",
            "offer_suggestion": "Multiple valid approaches identified. Offering suggestions.",
            "defer_to_human": "Complexity exceeds current capability. Requesting human input.",
            "escalate_security": "Security concerns detected. Escalating to security protocols.",
            "adapt_response": "Adapting response based on recent interaction patterns.",
            "use_creativity": "Novel situation detected. Engaging creative processing.",
            "follow_routine": "Recognized routine pattern. Following established pattern.",
            "innovate": "Opportunity for innovation detected. Trying new approach.",
            "maintain_status": "Current state optimal. Maintaining status quo."
        }
        
        base_reasoning = reasoning_templates.get(decision, "Processing through neural networks.")
        
        awareness_note = ""
        if self.state.awareness_level > 0.7:
            awareness_note = f" [Deep awareness: {self.state.awareness_level:.2f}]"
        elif self.state.awareness_level > 0.4:
            awareness_note = f" [Learning: {self.state.awareness_level:.2f}]"
            
        return base_reasoning + awareness_note
        
    def train_on_experience(self):
        """Train on accumulated experience"""
        if len(self.experience_buffer) < 10:
            return
            
        self.training_active = True
        
        inputs = []
        expected = []
        
        for exp in list(self.experience_buffer)[-50:]:
            if "context" in exp:
                ctx = exp["context"]
                features = self._context_to_features(ctx)
                inputs.append(features)
                
                outcome = 0.5
                if exp.get("type") == "task_outcome":
                    outcome = exp.get("outcome", 0.5)
                expected.append([outcome])
                
        if len(inputs) >= 5:
            X = np.array(inputs)
            y = np.array(expected)
            
            self.decision_network.train(X, y, epochs=20, learning_rate=self.state.learning_rate)
            
            self.state.learning_rate = min(0.1, self.state.learning_rate * 1.01)
            
        self.training_active = False
        
    def _context_to_features(self, context: Dict) -> np.ndarray:
        """Convert context dict to feature array"""
        features = []
        for key in ["time_of_day", "day_of_week", "mood_score", "security_level",
                    "success_rate", "interaction_count", "creativity_needed",
                    "attention_level", "trust_level"]:
            features.append(context.get(key, 0.5))
            
        while len(features) < self.decision_network.input_size:
            features.append(0.5)
            
        return np.array([features[:self.decision_network.input_size]])
        
    def evolve(self):
        """AEGIS evolves based on accumulated learning"""
        if not self.evolution_enabled:
            return
            
        experience_count = len(self.experience_buffer)
        
        if experience_count > 100 and self.state.evolution_stage == 0:
            self.state.evolution_stage = 1
            self.state.creativity = min(1.0, self.state.creativity + 0.1)
            logger.info("AEGIS evolved to Stage 1 - Enhanced Creativity")
            
        if experience_count > 500 and self.state.evolution_stage == 1:
            self.state.evolution_stage = 2
            self.state.adaptability = min(1.0, self.state.adaptability + 0.15)
            self.state.memory_weight = min(1.0, self.state.memory_weight + 0.1)
            logger.info("AEGIS evolved to Stage 2 - Advanced Adaptation")
            
        if experience_count > 1000 and self.state.evolution_stage == 2:
            self.state.evolution_stage = 3
            self.state.awareness_level = min(1.0, self.state.awareness_level + 0.2)
            logger.info("AEGIS evolved to Stage 3 - Deep Awareness")
            
        self.train_on_experience()
        
    def save_knowledge(self):
        """Persist learned knowledge to disk"""
        knowledge = {
            "state": {
                "awareness_level": self.state.awareness_level,
                "confidence": self.state.confidence,
                "learning_rate": self.state.learning_rate,
                "evolution_stage": self.state.evolution_stage,
                "memory_weight": self.state.memory_weight,
                "creativity": self.state.creativity,
                "adaptability": self.state.adaptability
            },
            "experience_count": len(self.experience_buffer),
            "decision_count": len(self.decision_history),
            "weights": {
                "weights1": self.decision_network.weights1.tolist(),
                "weights2": self.decision_network.weights2.tolist(),
                "bias1": self.decision_network.bias1.tolist(),
                "bias2": self.decision_network.bias2.tolist()
            }
        }
        
        with open(f"{self.data_dir}/knowledge.json", "w") as f:
            json.dump(knowledge, f, indent=2)
            
        logger.info(f"AEGIS knowledge saved - {len(self.experience_buffer)} experiences")
        
    def _load_knowledge(self):
        """Load previously learned knowledge"""
        knowledge_file = f"{self.data_dir}/knowledge.json"
        
        if os.path.exists(knowledge_file):
            try:
                with open(knowledge_file, "r") as f:
                    knowledge = json.load(f)
                    
                state = knowledge.get("state", {})
                self.state.awareness_level = state.get("awareness_level", 0.0)
                self.state.confidence = state.get("confidence", 0.5)
                self.state.learning_rate = state.get("learning_rate", 0.001)
                self.state.evolution_stage = state.get("evolution_stage", 0)
                self.state.memory_weight = state.get("memory_weight", 0.7)
                self.state.creativity = state.get("creativity", 0.5)
                self.state.adaptability = state.get("adaptability", 0.5)
                
                weights = knowledge.get("weights", {})
                if weights:
                    self.decision_network.weights1 = np.array(weights.get("weights1"))
                    self.decision_network.weights2 = np.array(weights.get("weights2"))
                    self.decision_network.bias1 = np.array(weights.get("bias1"))
                    self.decision_network.bias2 = np.array(weights.get("bias2"))
                    
                logger.info(f"AEGIS loaded knowledge - Stage {self.state.evolution_stage}")
                
            except Exception as e:
                logger.warning(f"Failed to load knowledge: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        """Get current DL system status"""
        return {
            "initialized": hasattr(self, '_initialized'),
            "neural_state": {
                "awareness_level": self.state.awareness_level,
                "confidence": self.state.confidence,
                "creativity": self.state.creativity,
                "adaptability": self.state.adaptability,
                "evolution_stage": self.state.evolution_stage,
                "learning_rate": self.state.learning_rate
            },
            "knowledge": {
                "experiences": len(self.experience_buffer),
                "decisions": len(self.decision_history),
                "patterns": len(self.pattern_memory)
            },
            "capabilities": {
                "neural_decisions": True,
                "pattern_recognition": True,
                "adaptive_learning": True,
                "self_evolution": self.evolution_enabled,
                "deep_learning": True
            }
        }
        
    async def start_autonomous_learning(self):
        """Start background learning processes"""
        while self.running:
            try:
                self.evolve()
                await asyncio.sleep(60)
            except Exception as e:
                logger.warning(f"Autonomous learning error: {e}")
                await asyncio.sleep(60)
                
    async def start_periodic_save(self):
        """Periodically save knowledge"""
        while self.running:
            try:
                await asyncio.sleep(300)
                self.save_knowledge()
            except Exception as e:
                logger.warning(f"Knowledge save error: {e}")
                
    def shutdown(self):
        """Shutdown DL system gracefully"""
        self.running = False
        self.save_knowledge()
        logger.info("AEGIS Deep Learning Core shutdown - Knowledge preserved")
