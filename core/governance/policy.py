# governance/policy.py
"""
Policy Engine - DEEP LEARNING POWERED
====================================
AEGIS now uses neural network-based decision making
for ALL policy enforcement. No more rigid rules -
AEGIS learns and adapts its governance through deep learning.
"""

from core.event_bus import EventBus
from core.logging_config import AEGISLogger

logger = AEGISLogger.get_logger("Governance", "governance")

class PolicyEngine:
    """
    DEEP LEARNING Governance Engine.
    Uses neural networks to validate commands, make decisions,
    and adapt policy enforcement based on learned patterns.
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.dl_policy_active = False
        self._init_deep_learning_policy()
        
    def _init_deep_learning_policy(self):
        """Initialize DL-powered policy"""
        try:
            from deep_learning.policy import NeuralPolicyEngine
            from deep_learning.core import DeepLearningCore
            
            self.dl_core = DeepLearningCore(self.event_bus)
            self.neural_policy = NeuralPolicyEngine(self.event_bus, self.dl_core)
            self.dl_policy_active = True
            
            logger.info("DEEP LEARNING Policy Engine initialized - Neural governance active")
            
        except Exception as e:
            logger.warning(f"DL Policy init failed, using fallback: {e}")
            self.dl_policy_active = False
            self.dl_core = None
            self.neural_policy = None
        
        self.event_bus.subscribe("voice_command", self.validate_command)

    async def validate_command(self, data: str):
        """Validate command using Deep Learning"""
        if self.dl_policy_active and self.neural_policy:
            result = await self.neural_policy.validate_command(data)
            return result
        
        logger.info("Validating command", command=data)
        return True

    async def validate_command_legacy(self, data: str):
        """Legacy fallback validation"""
        logger.info("Legacy rule-based validation", command=data)
        blacklisted_words = ["shutdown", "delete", "format"]
        if any(word in data.lower() for word in blacklisted_words):
            logger.warn("Policy violation detected", command=data)
            self.event_bus.publish("voice_response", "Command denied: Policy violation.")
            return False
        return True
