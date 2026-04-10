                             
from collections import deque
from typing import List, Dict

class ConversationMemory:
    
    def __init__(self, max_memory: int = 1000):
        self.max_memory = max_memory
        self.short_term = deque(maxlen=20)
        self.long_term = deque(maxlen=max_memory)
        self.user_profiles = {}
        self.facts_learned = {}
        
    def add_exchange(self, user_msg: str, aegis_msg: str, context: dict = None):
        exchange = {
            "user": user_msg,
            "aegis": aegis_msg,
            "context": context or {}
        }
        self.short_term.append(exchange)
        self.long_term.append(exchange)
        
    def get_recent(self, count: int = 10) -> List[Dict]:
        return list(self.short_term)[-count:]
    
    def get_context(self) -> str:
        recent = self.get_recent(5)
        if not recent:
            return ""
        return "\n".join([f"User: {ex['user']}\nAEGIS: {ex['aegis']}" for ex in recent])
    
    def learn_fact(self, fact: str):
        self.facts_learned[fact] = True
        
    def get_facts(self) -> List[str]:
        return list(self.facts_learned.keys())
