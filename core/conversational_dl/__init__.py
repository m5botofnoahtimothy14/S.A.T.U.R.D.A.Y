# conversational_dl/__init__.py
"""
ConversationalDL - AEGIS True Conversational AI
===============================================
AEGIS is now a true conversational DL AI that:
- Understands natural language deeply
- Does real tasks across all subsystems
- Mimics human intelligence
- Learns from conversations
- Has memory and context
- Thinks and reasons
"""

from .engine import ConversationalDLEngine
from .memory import ConversationMemory
from .tasks import TaskExecutor

__all__ = ["ConversationalDLEngine", "ConversationMemory", "TaskExecutor"]
