# ml_integration/__init__.py
"""
ML Integration - Unified Machine Learning & Deep Learning for ALL AEGIS Subsystems
================================================================================
This module provides DL/ML capabilities to EVERY subsystem in AEGIS:
- Health Monitoring
- Identity & Security  
- Communication
- Embodied AI (Vision, Voice, Gestures)
- Services
- UI
- Christianity Core
- And all other modules

Every subsystem now thinks, learns, and evolves through neural networks.
"""

from .core import MLIntegrationCore
from .predictor import PredictiveEngine
from .classifier import NeuralClassifier

__all__ = ["MLIntegrationCore", "PredictiveEngine", "NeuralClassifier"]
