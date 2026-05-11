               

import logging
import json
import os
from core.event_bus import EventBus
logger = logging.getLogger("SATURDAY.Core.Brain")
class LinkedBrain:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.memory_path = "data/memory.json"
        self._init_deep_learning()
        self.context = {
            "current_user_type": "Main",
            "user_name": "Sir",
            "system_hierarchy": "SATURDAY",
            "interface_mode": "SATURDAY",
            "sub_mode": "Normal",
            "mood_context": "Neutral",
            "security_level": "Standard"
        }
        self.load_memory()
        self.event_bus.subscribe("human_status", self._on_user_detected)
    def _init_deep_learning(self):
        try:
            from deep_learning.core import DeepLearningCore
            from deep_learning.patterns import PatternRecognition
            self.dl_core = DeepLearningCore(self.event_bus)
            self.pattern_recognition = PatternRecognition(self.event_bus, self.dl_core)
            self.dl_active = True
            logger.info("Deep Learning Brain initialized - SATURDAY is now truly intelligent")
        except Exception as e:
            logger.warning(f"DL Brain init failed: {e}")
            self.dl_core = None
            self.pattern_recognition = None
            self.dl_active = False
    def load_memory(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r") as f:
                    self.memory = json.load(f)
            except:
                self.memory = {"users": {}, "history": []}
        else:
            self.memory = {"users": {}, "history": []}
    def _on_user_detected(self, data):
        user_type = data.get("user_type", "Main")
        if self.dl_active and self.dl_core:
            result = self.dl_core.think(f"user_detected_{user_type}", {
                "user_type": user_type,
                "context": self.context
            })
            decision = result.get("decision", "execute_command")
            if decision == "execute_command":
                self.context["current_user_type"] = user_type
                if user_type in ["Guest", "Family"]:
                    self.context["interface_mode"] = "EDITH"
                else:
                    self.context["interface_mode"] = "SATURDAY"
            logger.info(f"DL Brain processed user detection: {decision}")
        else:
            self.context["current_user_type"] = user_type
            if user_type in ["Guest", "Family"]:
                self.context["interface_mode"] = "EDITH"
            else:
                self.context["interface_mode"] = "SATURDAY"
    def set_sub_mode(self, mode: str):
        valid_modes = ["Normal", "Doctor", "Traveling", "Public"]
        if mode in valid_modes:
            if self.dl_active and self.dl_core:
                result = self.dl_core.think(f"set_mode_{mode}", {
                    "current_mode": self.context["sub_mode"],
                    "requested_mode": mode
                })
                if result.get("confidence", 0) > 0.5:
                    self.context["sub_mode"] = mode
                    if mode != "Normal":
                        self.context["interface_mode"] = "EDITH"
                    logger.info(f"DL Brain set sub-mode: {mode}")
            else:
                self.context["sub_mode"] = mode
                if mode != "Normal":
                    self.context["interface_mode"] = "EDITH"
            logger.info(f"Sub-mode set to: {mode}. Interface: {self.context['interface_mode']}")
    def think(self, query: str) -> dict:
        if self.dl_active and self.dl_core:
            return self.dl_core.think(query, self.context)
        return {"decision": "fallback", "confidence": 0.0}
    def get_greeting(self):
        user_name = self.context["user_name"]
        interface = self.context["interface_mode"]
        sub_mode = self.context["sub_mode"]
        user_type = self.context["current_user_type"]
        if self.dl_active and self.dl_core:
            result = self.dl_core.think("generate_greeting", {
                "user_name": user_name,
                "interface": interface,
                "sub_mode": sub_mode,
                "user_type": user_type
            })
            if result.get("confidence", 0) > 0.6:
                return f"{user_name} - {result.get('reasoning', '')}"
        if user_type == "Guest":
            return f"Welcome to SATURDAY. I am EDITH, your guest interface. How can I assist you?"
        if interface == "EDITH":
            if sub_mode == "Doctor":
                return f"EDITH Doctor Mode active. Analyzing vitals for {user_name}."
            elif sub_mode == "Traveling":
                return f"EDITH Travel Mode engaged. Monitoring transit and local security."
            elif sub_mode == "Public":
                return f"EDITH Public Interface active. Minimal footprint maintained."
            return f"Hello, {user_name}. EDITH subdomain active for normal conversation."
        return f"SATURDAY OS: Main Core re-engaged. Welcome back, {user_name}."
    def get_status(self) -> dict:
        status = {
            "context": self.context,
            "dl_active": self.dl_active,
            "memory_items": len(self.memory.get("history", []))
        }
        if self.dl_active and self.dl_core:
            status["neural_status"] = self.dl_core.get_status()
        return status
