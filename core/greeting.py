                  

import logging
import asyncio
from core.event_bus import EventBus
from core.brain import LinkedBrain
from communication.speech import SpeechManager
logger = logging.getLogger("AEGIS.Core.Greeting")
class GreetingManager:
    def __init__(self, event_bus: EventBus, brain: LinkedBrain, speech: SpeechManager):
        self.event_bus = event_bus
        self.brain = brain
        self.speech = speech
        self.greeted_users = set()
        self.event_bus.subscribe("voice_response", self._on_voice_response)
    def _on_voice_response(self, text: str):
        pass
    async def greet_user(self, user_id: str):
        if user_id in self.greeted_users:
            return
        greeting_text = self.brain.get_greeting()
        logger.info(f"Greeting user sequence started via {self.brain.context['interface_mode']}.")
        self.speech.speak(greeting_text)
        self.greeted_users.add(user_id)
    def reset_greetings(self):
        self.greeted_users.clear()
