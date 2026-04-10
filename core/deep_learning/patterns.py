                           
import os
import json
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass, field
import structlog

import numpy as np

logger = structlog.get_logger("AEGIS.DL.Patterns")

class PatternMatcher:
    
    def __init__(self, pattern_size: int = 10):
        self.pattern_size = pattern_size
        self.patterns = {}
        self.weights = {}
        
    def hash_pattern(self, data: Any) -> str:
        
        data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
        
    def learn_pattern(self, sequence: List[Any], label: str):
        
        pattern_hash = self.hash_pattern(sequence)
        
        if pattern_hash not in self.patterns:
            self.patterns[pattern_hash] = {
                "sequence": sequence[-self.pattern_size:],
                "label": label,
                "count": 0,
                "confidence": 0.0
            }
            
        self.patterns[pattern_hash]["count"] += 1
        self.patterns[pattern_hash]["confidence"] = min(1.0, self.patterns[pattern_hash]["count"] / 10.0)
        
    def match(self, sequence: List[Any]) -> Optional[Tuple[str, float]]:
        
        pattern_hash = self.hash_pattern(sequence)
        
        if pattern_hash in self.patterns:
            pattern = self.patterns[pattern_hash]
            return pattern["label"], pattern["confidence"]
            
        for stored_hash, pattern in self.patterns.items():
            if self._similarity(sequence, pattern["sequence"]) > 0.7:
                return pattern["label"], pattern["confidence"] * 0.8
                
        return None
        
    def _similarity(self, seq1: List[Any], seq2: List[Any]) -> float:
        
        if not seq1 or not seq2:
            return 0.0
            
        matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
        return matches / max(len(seq1), len(seq2))

class PatternRecognition:
    
    def __init__(self, event_bus=None, deep_learning_core=None):
        self.event_bus = event_bus
        self.dl_core = deep_learning_core
        
        self.data_dir = "data/deep_learning"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.command_patterns = PatternMatcher(pattern_size=5)
        self.time_patterns = PatternMatcher(pattern_size=3)
        self.behavior_patterns = PatternMatcher(pattern_size=10)
        
        self.sequence_buffer = deque(maxlen=20)
        self.time_buffer = deque(maxlen=50)
        self.behavior_buffer = deque(maxlen=100)
        
        self.user_profiles = defaultdict(lambda: {
            "commands": [],
            "times": [],
            "patterns": [],
            "anomaly_score": 0.0
        })
        
        self.baseline_behavior = {
            "typical_commands": [],
            "typical_times": [],
            "typical_duration": 0
        }
        
        self._load_patterns()
        self._subscribe_to_events()
        
        logger.info("PatternRecognition initialized - Neural pattern matching active")
        
    def _subscribe_to_events(self):
        
        if self.event_bus:
            self.event_bus.subscribe("voice_command", self._on_command)
            self.event_bus.subscribe("task_request", self._on_task)
            self.event_bus.subscribe("user_detected", self._on_user)
            
    def _on_command(self, data):
        
        command = str(data)
        self.sequence_buffer.append(command)
        
        if len(self.sequence_buffer) >= 3:
            self.command_patterns.learn_pattern(list(self.sequence_buffer), "command_sequence")
            
        self.behavior_buffer.append({
            "type": "command",
            "data": command,
            "timestamp": time.time()
        })
        
    def _on_task(self, data):
        
        self.behavior_buffer.append({
            "type": "task",
            "data": data,
            "timestamp": time.time()
        })
        
    def _on_user(self, data):
        
        user_id = data.get("user_id", "default")
        
        self.user_profiles[user_id]["times"].append(time.time())
        
        if len(self.user_profiles[user_id]["times"]) >= 5:
            times = self.user_profiles[user_id]["times"][-5:]
            avg_time = np.mean(times)
            
            hour = time.localtime(avg_time).tm_hour
            self.time_patterns.learn_pattern([hour], f"user_{user_id}")
            
    def recognize_command_pattern(self, command: str) -> Dict[str, Any]:
        
        recent = list(self.sequence_buffer)[-5:]
        recent.append(command)
        
        match = self.command_patterns.match(recent)
        
        if match:
            label, confidence = match
            return {
                "pattern_detected": True,
                "pattern_type": label,
                "confidence": confidence,
                "suggestion": self._generate_suggestion(command)
            }
            
        return {
            "pattern_detected": False,
            "confidence": 0.0,
            "suggestion": None
        }
        
    def recognize_time_pattern(self) -> Dict[str, Any]:
        
        current_hour = time.localtime().tm_hour
        current_minute = time.localtime().tm_min
        
        time_window = current_hour * 60 + current_minute
        
        match = self.time_patterns.match([time_window])
        
        if match:
            return {
                "pattern": match[0],
                "confidence": match[1],
                "time_context": self._get_time_context()
            }
            
        return {
            "pattern": None,
            "confidence": 0.0,
            "time_context": self._get_time_context()
        }
        
    def recognize_behavior(self, user: str = "default") -> Dict[str, Any]:
        
        profile = self.user_profiles[user]
        
        recent_behavior = list(self.behavior_buffer)[-10:]
        
        if len(recent_behavior) < 3:
            return {
                "status": "insufficient_data",
                "anomaly_score": 0.0
            }
            
        behavior_types = [b.get("type") for b in recent_behavior]
        type_counts = defaultdict(int)
        for bt in behavior_types:
            type_counts[bt] += 1
            
        dominant_type = max(type_counts.items(), key=lambda x: x[1])
        
        anomaly_score = self._calculate_anomaly_score(user, recent_behavior)
        profile["anomaly_score"] = anomaly_score
        
        return {
            "dominant_behavior": dominant_type[0],
            "behavior_distribution": dict(type_counts),
            "anomaly_score": anomaly_score,
            "pattern_count": len(profile["patterns"])
        }
        
    def _calculate_anomaly_score(self, user: str, behavior: List[Dict]) -> float:
        
        if user not in self.user_profiles:
            return 0.0
            
        profile = self.user_profiles[user]
        
        if not profile["commands"]:
            return 0.0
            
        recent_commands = [b.get("data") for b in behavior if b.get("type") == "command"]
        
        if not recent_commands:
            return 0.0
            
        typical = set(profile["commands"][-20:] if len(profile["commands"]) > 20 else profile["commands"])
        recent_set = set(recent_commands)
        
        overlap = len(typical & recent_set)
        total = len(recent_set)
        
        if total == 0:
            return 0.0
            
        similarity = overlap / total
        
        return max(0.0, 1.0 - similarity)
        
    def _generate_suggestion(self, command: str) -> Optional[str]:
        
        suggestions = {
            "music": "Would you like to play some music?",
            "search": "I can search for more information.",
            "weather": "Would you like the weather forecast?",
            "call": "Should I call someone?",
            "message": "Would you like to send a message?"
        }
        
        command_lower = command.lower()
        for key, suggestion in suggestions.items():
            if key in command_lower:
                return suggestion
                
        return None
        
    def _get_time_context(self) -> str:
        
        hour = time.localtime().tm_hour
        
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
            
    def predict_next_command(self, user: str = "default") -> Dict[str, Any]:
        
        profile = self.user_profiles[user]
        
        recent = list(self.sequence_buffer)[-3:]
        
        match = self.command_patterns.match(recent)
        
        if match:
            return {
                "prediction": match[0],
                "confidence": match[1] * 0.8,
                "method": "pattern_matching"
            }
            
        if profile["commands"]:
            most_common = defaultdict(int)
            for cmd in profile["commands"]:
                most_common[cmd] += 1
                
            if most_common:
                predicted = max(most_common.items(), key=lambda x: x[1])
                return {
                    "prediction": predicted[0],
                    "confidence": predicted[1] / len(profile["commands"]),
                    "method": "frequency"
                }
                
        return {
            "prediction": None,
            "confidence": 0.0
        }
        
    def learn_from_outcome(self, command: str, success: bool):
        
        user = "default"
        self.user_profiles[user]["commands"].append(command)
        
        if success:
            self.behavior_patterns.learn_pattern([command], "successful_command")
        else:
            self.behavior_patterns.learn_pattern([command], "failed_command")
            
    def _save_patterns(self):
        
        patterns_data = {
            "command_patterns": len(self.command_patterns.patterns),
            "time_patterns": len(self.time_patterns.patterns),
            "behavior_patterns": len(self.behavior_patterns.patterns),
            "user_profiles": dict(self.user_profiles)
        }
        
        with open(f"{self.data_dir}/patterns.json", "w") as f:
            json.dump(patterns_data, f, indent=2)
            
    def _load_patterns(self):
        
        patterns_file = f"{self.data_dir}/patterns.json"
        
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, "r") as f:
                    data = json.load(f)
                    
                user_profiles = data.get("user_profiles", {})
                for user, profile in user_profiles.items():
                    self.user_profiles[user] = profile
                    
                logger.info(f"Loaded patterns for {len(user_profiles)} users")
                
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        
        return {
            "command_patterns": len(self.command_patterns.patterns),
            "time_patterns": len(self.time_patterns.patterns),
            "behavior_patterns": len(self.behavior_patterns.patterns),
            "users_profiled": len(self.user_profiles),
            "sequence_buffer_size": len(self.sequence_buffer),
            "behavior_buffer_size": len(self.behavior_buffer)
        }
