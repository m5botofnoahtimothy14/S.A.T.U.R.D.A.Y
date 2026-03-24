# deep_learning/__init__.py
"""
AEGIS Deep Learning Core
=======================
AEGIS now possesses true Deep Learning capabilities.
This module provides neural network-based decision making,
pattern recognition, and adaptive learning - transforming
AEGIS from a rule-based system into an evolving AI OS.

DL Capabilities:
- Neural Decision Engine
- Pattern Recognition Network  
- Adaptive Learning System
- Self-Evolution Framework
- Neural Policy Governance
"""

from .core import DeepLearningCore
from .policy import NeuralPolicyEngine
from .adaptive import AdaptiveLearningEngine
from .patterns import PatternRecognition
from .evolution import SelfEvolution

__all__ = [
    "DeepLearningCore",
    "NeuralPolicyEngine", 
    "AdaptiveLearningEngine",
    "PatternRecognition",
    "SelfEvolution"
]
