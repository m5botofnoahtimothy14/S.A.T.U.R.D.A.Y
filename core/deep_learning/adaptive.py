                           
import os
import json
import time
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass, field
import structlog

import numpy as np

logger = structlog.get_logger("AEGIS.DL.Adaptive")

@dataclass
class LearningEntry:
    
    input_data: Any
    output_data: Any
    outcome: float
    timestamp: float = field(default_factory=time.time)
    context: Dict = field(default_factory=dict)

class AdaptiveLearningEngine:
    
    def __init__(self, event_bus=None, deep_learning_core=None):
        self.event_bus = event_bus
        self.dl_core = deep_learning_core
        
        self.data_dir = "data/deep_learning"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.learning_buffer = deque(maxlen=500)
        self.success_patterns = defaultdict(list)
        self.failure_patterns = defaultdict(list)
        
        self.user_preferences = {}
        self.conversation_styles = {}
        self.response_history = deque(maxlen=200)
        
        self.learning_rate = 0.01
        self.adaptation_threshold = 0.6
        self.convergence_rate = 0.001
        
        self.knowledge_graph = {}
        self.concept_embeddings = {}
        
        self._load_knowledge()
        self._subscribe_to_events()
        
        logger.info("AdaptiveLearningEngine initialized - Continuous learning active")
        
    def _subscribe_to_events(self):
        
        if self.event_bus:
            self.event_bus.subscribe("voice_command", self._on_command)
            self.event_bus.subscribe("voice_response", self._on_response)
            self.event_bus.subscribe("task_completed", self._on_task_outcome)
            self.event_bus.subscribe("task_failed", self._on_task_outcome)
            self.event_bus.subscribe("user_feedback", self._on_feedback)
            self.event_bus.subscribe("search_results", self._on_search)
            
    def _on_command(self, data):
        
        command = str(data)
        
        entry = LearningEntry(
            input_data=command,
            output_data=None,
            outcome=0.5,
            context={"type": "command"}
        )
        self.learning_buffer.append(entry)
        
    def _on_response(self, data):
        
        response = str(data)
        
        if len(self.learning_buffer) > 0:
            last_entry = self.learning_buffer[-1]
            if last_entry.output_data is None:
                last_entry.output_data = response
                
        self.response_history.append({
            "response": response,
            "timestamp": time.time()
        })
        
    def _on_task_outcome(self, data):
        
        task_type = data.get("type", "unknown")
        success = "task_completed" in str(data)
        
        if len(self.learning_buffer) > 0:
            last_entry = self.learning_buffer[-1]
            last_entry.outcome = 1.0 if success else 0.0
            last_entry.context["task_type"] = task_type
            
        if success:
            self.success_patterns[task_type].append(time.time())
        else:
            self.failure_patterns[task_type].append(time.time())
            
        self._adapt_learning_rate(success)
        
    def _on_feedback(self, data):
        
        feedback = data.get("feedback", 0.5)
        
        if len(self.learning_buffer) > 0:
            last_entry = self.learning_buffer[-1]
            last_entry.outcome = feedback
            
        self._update_preferences(data.get("user", "default"), feedback)
        
    def _on_search(self, data):
        
        query = data.get("query", "")
        results = data.get("results", [])
        
        if results:
            entry = LearningEntry(
                input_data=query,
                output_data={"result_count": len(results), "top_result": results[0] if results else None},
                outcome=0.7,
                context={"type": "search"}
            )
            self.learning_buffer.append(entry)
            
    def _adapt_learning_rate(self, success: bool):
        
        if success:
            self.learning_rate = min(0.1, self.learning_rate * 1.05)
        else:
            self.learning_rate = max(0.0001, self.learning_rate * 0.95)
            
    def _update_preferences(self, user: str, feedback: float):
        
        if user not in self.user_preferences:
            self.user_preferences[user] = {
                "feedback_sum": 0.0,
                "interactions": 0,
                "preferred_style": "neutral",
                "topics": defaultdict(float)
            }
            
        prefs = self.user_preferences[user]
        prefs["feedback_sum"] += feedback
        prefs["interactions"] += 1
        
    def learn(self, input_data: Any, context: Dict = None) -> Dict[str, Any]:
        
        entry = LearningEntry(
            input_data=input_data,
            output_data=None,
            outcome=0.5,
            context=context or {}
        )
        self.learning_buffer.append(entry)
        
        knowledge_key = self._extract_key(input_data)
        if knowledge_key:
            self.knowledge_graph[knowledge_key] = {
                "last_accessed": time.time(),
                "access_count": self.knowledge_graph.get(knowledge_key, {}).get("access_count", 0) + 1,
                "context": context
            }
            
        insights = self._generate_insights(input_data, context)
        
        return {
            "learned": True,
            "insights": insights,
            "confidence": min(1.0, len(self.learning_buffer) / 100.0),
            "adaptation": {
                "learning_rate": self.learning_rate,
                "total_learned": len(self.learning_buffer),
                "success_rate": self._calculate_success_rate()
            }
        }
        
    def predict(self, input_data: Any, context: Dict = None) -> Dict[str, Any]:
        
        key = self._extract_key(input_data)
        
        if key in self.knowledge_graph:
            knowledge = self.knowledge_graph[key]
            recency = time.time() - knowledge.get("last_accessed", 0)
            access_count = knowledge.get("access_count", 0)
            
            confidence = min(1.0, access_count / 10.0) * (1.0 / (1.0 + recency / 86400))
            
            return {
                "prediction": knowledge.get("context", {}),
                "confidence": confidence,
                "based_on": access_count,
                "method": "knowledge_graph"
            }
            
        pattern_match = self._find_pattern_match(input_data)
        if pattern_match:
            return pattern_match
            
        return {
            "prediction": None,
            "confidence": 0.0,
            "method": "no_match"
        }
        
    def _extract_key(self, data: Any) -> str:
        
        data_str = str(data).lower().strip()
        words = data_str.split()
        if len(words) > 3:
            return "_".join(words[:3])
        return data_str
        
    def _find_pattern_match(self, input_data: Any) -> Optional[Dict]:
        
        input_str = str(input_data).lower()
        
        for entry in reversed(list(self.learning_buffer)):
            if entry.input_data and str(entry.input_data).lower() in input_str:
                return {
                    "prediction": entry.output_data,
                    "confidence": entry.outcome,
                    "based_on": "pattern_match",
                    "method": "similarity"
                }
                
        return None
        
    def _generate_insights(self, input_data: Any, context: Dict = None) -> List[str]:
        
        insights = []
        
        total_entries = len(self.learning_buffer)
        if total_entries > 10:
            insights.append(f"Learned from {total_entries} interactions")
            
        success_rate = self._calculate_success_rate()
        if success_rate > 0.8:
            insights.append(f"High success rate: {success_rate:.1%}")
        elif success_rate < 0.5:
            insights.append(f"Learning needed: {success_rate:.1%} success rate")
            
        if self.learning_rate > 0.05:
            insights.append(f"Rapid adaptation: {self.learning_rate:.4f} rate")
            
        return insights
        
    def _calculate_success_rate(self) -> float:
        
        if not self.learning_buffer:
            return 0.5
            
        completed = [e for e in self.learning_buffer if e.outcome != 0.5]
        if not completed:
            return 0.5
            
        return sum(e.outcome for e in completed) / len(completed)
        
    def adapt_response(self, response: str, user: str = "default") -> str:
        
        if user in self.user_preferences:
            prefs = self.user_preferences[user]
            avg_feedback = prefs["feedback_sum"] / max(1, prefs["interactions"])
            
            if avg_feedback > 0.8:
                return f"{response} [Adapted to your preferences]"
            elif avg_feedback < 0.4:
                return f"{response} [Adjusting based on feedback]"
                
        return response
        
    def get_user_model(self, user: str = "default") -> Dict[str, Any]:
        
        if user not in self.user_preferences:
            return {"interactions": 0, "style": "neutral"}
            
        prefs = self.user_preferences[user]
        return {
            "interactions": prefs["interactions"],
            "avg_feedback": prefs["feedback_sum"] / max(1, prefs["interactions"]),
            "preferred_style": prefs["preferred_style"],
            "topics": dict(prefs["topics"])
        }
        
    def _save_knowledge(self):
        
        knowledge = {
            "learning_buffer_size": len(self.learning_buffer),
            "knowledge_graph_size": len(self.knowledge_graph),
            "learning_rate": self.learning_rate,
            "user_preferences": {
                user: {
                    "feedback_sum": prefs["feedback_sum"],
                    "interactions": prefs["interactions"],
                    "preferred_style": prefs["preferred_style"]
                }
                for user, prefs in self.user_preferences.items()
            },
            "patterns": {
                "success": {k: len(v) for k, v in self.success_patterns.items()},
                "failure": {k: len(v) for k, v in self.failure_patterns.items()}
            }
        }
        
        with open(f"{self.data_dir}/adaptive_knowledge.json", "w") as f:
            json.dump(knowledge, f, indent=2)
            
    def _load_knowledge(self):
        
        knowledge_file = f"{self.data_dir}/adaptive_knowledge.json"
        
        if os.path.exists(knowledge_file):
            try:
                with open(knowledge_file, "r") as f:
                    knowledge = json.load(f)
                    
                self.learning_rate = knowledge.get("learning_rate", 0.01)
                
                user_prefs = knowledge.get("user_preferences", {})
                for user, prefs in user_prefs.items():
                    self.user_preferences[user] = {
                        "feedback_sum": prefs.get("feedback_sum", 0.0),
                        "interactions": prefs.get("interactions", 0),
                        "preferred_style": prefs.get("preferred_style", "neutral"),
                        "topics": defaultdict(float)
                    }
                    
                logger.info(f"Adaptive knowledge loaded: {len(user_prefs)} users")
                
            except Exception as e:
                logger.warning(f"Failed to load adaptive knowledge: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        
        return {
            "learning_entries": len(self.learning_buffer),
            "knowledge_nodes": len(self.knowledge_graph),
            "learning_rate": self.learning_rate,
            "success_rate": self._calculate_success_rate(),
            "users_learned": len(self.user_preferences),
            "patterns_identified": len(self.success_patterns) + len(self.failure_patterns)
        }
        
    def save(self):
        
        self._save_knowledge()
        logger.info("Adaptive learning knowledge saved")
